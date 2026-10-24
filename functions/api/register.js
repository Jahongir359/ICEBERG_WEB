const JSON_HEADERS = {
    "Content-Type": "application/json; charset=utf-8",
    "Cache-Control": "no-store",
    "X-Content-Type-Options": "nosniff"
};

function jsonResponse(body, status = 200) {
    return new Response(JSON.stringify(body), { status, headers: JSON_HEADERS });
}

function cleanText(value, maxLength) {
    return typeof value === "string"
        ? value.trim().replace(/[\u0000-\u001f\u007f]/g, "").slice(0, maxLength)
        : "";
}

function requestReference(request) {
    return cleanText(request.headers.get("CF-Ray"), 64) || crypto.randomUUID();
}

function validGoogleScriptUrl(value) {
    try {
        const url = new URL(value);
        return url.protocol === "https:"
            && url.hostname === "script.google.com"
            && /^\/macros\/s\/[^/]+\/exec$/.test(url.pathname);
    } catch (_error) {
        return false;
    }
}

async function loadRegistrationOptions(env) {
    if (!env.ASSETS || typeof env.ASSETS.fetch !== "function") {
        throw new Error("Registration options binding is unavailable");
    }
    const response = await env.ASSETS.fetch("https://iceberglc.com/registration-options.json");
    if (!response.ok) {
        throw new Error("Registration options could not be loaded");
    }
    const config = await response.json();
    const programs = (config.programs || []).filter(item => item.active);
    const branches = (config.branches || []).filter(item => item.active);
    return {
        programs: new Set(programs.map(item => item.id)),
        branches: new Set(branches.map(item => item.id)),
        programNames: new Map(programs.map(item => [item.id, item.name || item.id])),
        branchNames: new Map(branches.map(item => [item.id, item.name || item.id])),
        // The ERP shows a lead to a branch admin only when its branch text equals
        // that admin's ERP branch name, so send the configured ERP name when set.
        erpBranchNames: new Map(branches.map(item => [item.id, cleanText(item.erp_branch_name, 100)]))
    };
}

function validErpLeadsUrl(value) {
    try {
        return new URL(value).protocol === "https:";
    } catch (_error) {
        return false;
    }
}

function erpBranchName(branch, options) {
    if (branch === "unknown") {
        return "";
    }
    return options.erpBranchNames.get(branch) || branch;
}

const SCHOOL_GRADES = new Set(["1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11"]);
const SCHOOL_LANGUAGES = { uz: "O'zbek", ru: "Rus", en: "Ingliz" };

function localUzPhone(value) {
    let digits = cleanText(value, 30).replace(/\D/g, "");
    if (digits.length === 12 && digits.startsWith("998")) {
        digits = digits.slice(3);
    }
    return digits;
}

function validBirthDate(value) {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
    const date = new Date(`${value}T00:00:00Z`);
    return !Number.isNaN(date.getTime()) && date.toISOString().slice(0, 10) === value && date <= new Date();
}

// Iceberg School admissions enquiry: returns the Sheets fields or an error message.
function schoolEnquiryFields(input) {
    const parentName = cleanText(input.parent_name, 100);
    const phone = localUzPhone(input.parent_phone);
    const grade = cleanText(input.grade, 2);
    const language = cleanText(input.language, 2);
    const childBirthDate = cleanText(input.child_birth_date, 10);
    if (parentName.length < 2 || !/^\d{9}$/.test(phone)) {
        return { error: "Ism va telefon raqamingizni tekshiring." };
    }
    if (!SCHOOL_GRADES.has(grade)) {
        return { error: "Sinfni tanlang." };
    }
    if (language && !SCHOOL_LANGUAGES[language]) {
        return { error: "Tilni qayta tanlang." };
    }
    if (childBirthDate && !validBirthDate(childBirthDate)) {
        return { error: "Tug'ilgan sanani tekshiring." };
    }
    if (input.consent !== true) {
        return { error: "Bog'lanishimizga rozilik bering." };
    }
    return {
        fields: {
            form_type: "school-enquiry",
            student_name: parentName,
            student_phone: `+998${phone}`,
            program: `grade-${grade}`,
            branch: "school",
            child_name: cleanText(input.child_name, 100),
            child_birth_date: childBirthDate,
            language,
            message: cleanText(input.message, 1000)
        }
    };
}

function schoolEnquiryMessage(lead) {
    const details = [`Farzand: ${lead.child_name || "-"}`];
    if (lead.child_birth_date) details.push(`Tug'ilgan sana: ${lead.child_birth_date}`);
    if (lead.language) details.push(`Til: ${SCHOOL_LANGUAGES[lead.language]}`);
    return details.join(" · ") + (lead.message ? `\n${lead.message}` : "");
}

function erpLeadPayload(lead, options, env) {
    const shared = {
        full_name: lead.student_name,
        phone: lead.student_phone,
        submission_id: lead.id,
        utm_source: lead.utm_source,
        utm_medium: lead.utm_medium,
        utm_campaign: lead.utm_campaign,
        referrer: lead.page_url || lead.referrer
    };
    if (lead.form_type === "school-enquiry") {
        return {
            ...shared,
            program: `Grade ${lead.program.replace("grade-", "")}`,
            branch: cleanText(env.SCHOOL_BRANCH_NAME, 100) || "Iceberg School",
            source: "school-website",
            message: schoolEnquiryMessage(lead)
        };
    }
    return {
        ...shared,
        program: options.programNames.get(lead.program) || lead.program,
        branch: erpBranchName(lead.branch, options),
        source: "website"
    };
}

// Best-effort copy of a stored lead into the ERP's Registration leads screen.
// Google Sheets stays the primary store, so failures are logged, never shown.
async function forwardLeadToErp(lead, options, env, reference) {
    if (!env.REGISTRATION_LEADS_API_URL || !env.REGISTRATION_LEADS_API_TOKEN) {
        return;
    }
    if (!validErpLeadsUrl(env.REGISTRATION_LEADS_API_URL)) {
        console.error("ERP lead forwarding URL is invalid", reference);
        return;
    }
    try {
        const response = await fetch(env.REGISTRATION_LEADS_API_URL, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Authorization": `Bearer ${env.REGISTRATION_LEADS_API_TOKEN}`
            },
            body: JSON.stringify(erpLeadPayload(lead, options, env)),
            redirect: "manual",
            signal: AbortSignal.timeout(8000)
        });
        if (response.status < 200 || response.status >= 300) {
            console.error("ERP lead forwarding rejected", reference, response.status);
        }
    } catch (error) {
        console.error("ERP lead forwarding failed", reference, error.name);
    }
}

function telegramLeadText(lead, options) {
    const lines = [];
    if (lead.form_type === "school-enquiry") {
        lines.push(
            "🏫 Iceberg School — yangi so'rov",
            "",
            `Ota-ona: ${lead.student_name}`,
            `Telefon: ${lead.student_phone}`,
            `Sinf: ${lead.program.replace("grade-", "")}`
        );
        if (lead.child_name) lines.push(`Farzand: ${lead.child_name}`);
        if (lead.child_birth_date) lines.push(`Tug'ilgan sana: ${lead.child_birth_date}`);
        if (lead.language) lines.push(`Til: ${SCHOOL_LANGUAGES[lead.language]}`);
        if (lead.message) lines.push("", `Xabar: ${lead.message}`);
    } else {
        lines.push(
            "📝 Iceberg Courses — yangi ariza",
            "",
            `Ism: ${lead.student_name}`,
            `Telefon: ${lead.student_phone}`,
            `Dastur: ${options.programNames.get(lead.program) || lead.program}`,
            `Filial: ${options.branchNames.get(lead.branch) || lead.branch}`
        );
    }
    const utm = [lead.utm_source, lead.utm_medium, lead.utm_campaign].filter(Boolean).join(" / ");
    lines.push("");
    if (lead.page_url) lines.push(`Sahifa: ${lead.page_url}`);
    if (utm) lines.push(`UTM: ${utm}`);
    lines.push(`Vaqt: ${lead.submitted_at}`, `ID: ${lead.id}`);
    return lines.join("\n");
}

// Best-effort message to the support Telegram chat, sent by the server through the
// bot, so the visitor never has to open Telegram. Sheets stays the primary store.
async function notifyTelegram(lead, options, env, reference) {
    if (!env.TELEGRAM_BOT_TOKEN || !env.TELEGRAM_CHAT_ID) {
        return;
    }
    try {
        const response = await fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/sendMessage`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                chat_id: env.TELEGRAM_CHAT_ID,
                text: telegramLeadText(lead, options),
                disable_web_page_preview: true
            }),
            signal: AbortSignal.timeout(8000)
        });
        if (!response.ok) {
            console.error("Telegram notification rejected", reference, response.status);
        }
    } catch (error) {
        console.error("Telegram notification failed", reference, error.name);
    }
}

async function validateTurnstile(token, request, secret) {
    if (!secret) {
        return { success: false, configurationError: true };
    }

    const body = new FormData();
    body.append("secret", secret);
    body.append("response", token);
    body.append("remoteip", request.headers.get("CF-Connecting-IP") || "");

    const response = await fetch(
        "https://challenges.cloudflare.com/turnstile/v0/siteverify",
        { method: "POST", body }
    );
    if (!response.ok) {
        return { success: false };
    }
    return response.json();
}

export async function onRequestPost(context) {
    const { request, env } = context;
    let storedResult;
    const reference = requestReference(request);
    if (!validGoogleScriptUrl(env.GOOGLE_SCRIPT_URL) || !env.GOOGLE_SCRIPT_SECRET) {
        console.error("Registration storage is not configured", reference);
        return jsonResponse(
            {
                ok: false,
                message: "Ro'yxatdan o'tish xizmati hali sozlanmagan.",
                reference
            },
            503
        );
    }

    const contentLength = Number(request.headers.get("Content-Length") || 0);
    if (contentLength > 16_384) {
        return jsonResponse({ ok: false, message: "So'rov juda katta." }, 413);
    }

    let input;
    try {
        input = await request.json();
    } catch (_error) {
        return jsonResponse({ ok: false, message: "Noto'g'ri so'rov." }, 400);
    }

    if (cleanText(input.website, 100)) {
        return jsonResponse({ ok: true });
    }

    let leadFields;
    let options = null;
    if (input.form_type === "school-enquiry") {
        const enquiry = schoolEnquiryFields(input);
        if (enquiry.error) {
            return jsonResponse({ ok: false, message: enquiry.error }, 422);
        }
        leadFields = enquiry.fields;
    } else {
        const studentName = cleanText(input.student_name, 100);
        const localPhone = localUzPhone(input.student_phone);
        const program = cleanText(input.program, 60);
        const branch = cleanText(input.branch, 60);
        if (studentName.length < 2 || !/^\d{9}$/.test(localPhone)) {
            return jsonResponse(
                { ok: false, message: "Ism va telefon raqamingizni tekshiring." },
                422
            );
        }

        try {
            options = await loadRegistrationOptions(env);
        } catch (error) {
            console.error("Registration configuration failed", error.message);
            return jsonResponse({ ok: false, message: "Ro'yxatdan o'tish xizmati vaqtincha ishlamayapti." }, 503);
        }
        if (!options.programs.has(program) || !options.branches.has(branch)) {
            return jsonResponse({ ok: false, message: "Dastur va filialni qayta tanlang." }, 422);
        }
        leadFields = {
            student_name: studentName,
            student_phone: `+998${localPhone}`,
            program,
            branch
        };
    }

    let turnstile;
    try {
        turnstile = await validateTurnstile(
            cleanText(input.turnstile_token, 2048),
            request,
            env.TURNSTILE_SECRET_KEY
        );
    } catch (_error) {
        return jsonResponse(
            { ok: false, message: "Tekshiruv xizmati vaqtincha ishlamayapti." },
            502
        );
    }
    if (turnstile.configurationError) {
        return jsonResponse(
            { ok: false, message: "Xavfsizlik tekshiruvi hali sozlanmagan." },
            503
        );
    }
    if (!turnstile.success || (turnstile.action && turnstile.action !== "register")) {
        return jsonResponse(
            { ok: false, message: "Xavfsizlik tekshiruvidan qayta o'ting." },
            403
        );
    }

    const lead = {
        secret: env.GOOGLE_SCRIPT_SECRET,
        id: /^[a-f0-9-]{20,64}$/i.test(cleanText(input.submission_id, 64))
            ? cleanText(input.submission_id, 64)
            : crypto.randomUUID(),
        submitted_at: new Date().toISOString(),
        ...leadFields,
        utm_source: cleanText(input.utm_source, 100),
        utm_medium: cleanText(input.utm_medium, 100),
        utm_campaign: cleanText(input.utm_campaign, 150),
        page_url: cleanText(input.page_url, 500),
        referrer: cleanText(input.referrer, 500)
    };

    try {
        const response = await fetch(env.GOOGLE_SCRIPT_URL, {
            method: "POST",
            headers: { "Content-Type": "text/plain;charset=UTF-8" },
            body: JSON.stringify(lead),
            redirect: "follow"
        });
        const responseText = await response.text();
        let result;
        try {
            result = JSON.parse(responseText);
        } catch (_error) {
            throw new Error(`non_json_response:${response.status}`);
        }
        if (!response.ok || !result.ok) {
            throw new Error(`receiver_rejected:${cleanText(result.error, 80) || response.status}`);
        }
        storedResult = result;
    } catch (error) {
        console.error("Registration forwarding failed", reference, error.message);
        return jsonResponse(
            {
                ok: false,
                message: `Arizani saqlab bo'lmadi. Qayta urinib ko'ring. Xato kodi: ${reference}`,
                reference
            },
            502
        );
    }

    // A repeated submission ID was already stored (and forwarded) the first time.
    if (storedResult.duplicate !== true) {
        const forwarding = Promise.all([
            forwardLeadToErp(lead, options, env, reference),
            notifyTelegram(lead, options, env, reference)
        ]);
        if (typeof context.waitUntil === "function") {
            context.waitUntil(forwarding);
        } else {
            await forwarding;
        }
    }

    return jsonResponse({ ok: true, id: lead.id }, 201);
}

export function onRequest(context) {
    if (context.request.method !== "POST") {
        return jsonResponse({ ok: false, message: "Method not allowed" }, 405);
    }
    return onRequestPost(context).catch(error => {
        const reference = requestReference(context.request);
        console.error("Unhandled registration error", reference, error.message);
        return jsonResponse(
            {
                ok: false,
                message: `Arizani yuborishda server xatosi yuz berdi. Xato kodi: ${reference}`,
                reference
            },
            500
        );
    });
}
