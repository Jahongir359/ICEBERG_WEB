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
            body: JSON.stringify({
                full_name: lead.student_name,
                phone: lead.student_phone,
                program: options.programNames.get(lead.program) || lead.program,
                branch: erpBranchName(lead.branch, options),
                source: "website",
                submission_id: lead.id,
                utm_source: lead.utm_source,
                utm_medium: lead.utm_medium,
                utm_campaign: lead.utm_campaign,
                referrer: lead.page_url || lead.referrer
            }),
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

    const studentName = cleanText(input.student_name, 100);
    let localPhone = cleanText(input.student_phone, 30).replace(/\D/g, "");
    if (localPhone.length === 12 && localPhone.startsWith("998")) {
        localPhone = localPhone.slice(3);
    }
    const program = cleanText(input.program, 60);
    const branch = cleanText(input.branch, 60);
    if (studentName.length < 2 || !/^\d{9}$/.test(localPhone)) {
        return jsonResponse(
            { ok: false, message: "Ism va telefon raqamingizni tekshiring." },
            422
        );
    }

    let options;
    try {
        options = await loadRegistrationOptions(env);
    } catch (error) {
        console.error("Registration configuration failed", error.message);
        return jsonResponse({ ok: false, message: "Ro'yxatdan o'tish xizmati vaqtincha ishlamayapti." }, 503);
    }
    if (!options.programs.has(program) || !options.branches.has(branch)) {
        return jsonResponse({ ok: false, message: "Dastur va filialni qayta tanlang." }, 422);
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
        student_name: studentName,
        student_phone: `+998${localPhone}`,
        program,
        branch,
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
        const forwarding = forwardLeadToErp(lead, options, env, reference);
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
