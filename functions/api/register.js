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
    if (!env.GOOGLE_SCRIPT_URL || !env.GOOGLE_SCRIPT_SECRET) {
        return jsonResponse(
            { ok: false, message: "Ro'yxatdan o'tish xizmati hali sozlanmagan." },
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
    const localPhone = cleanText(input.student_phone, 30).replace(/\D/g, "");
    if (studentName.length < 2 || !/^\d{9}$/.test(localPhone)) {
        return jsonResponse(
            { ok: false, message: "Ism va 9 xonali telefon raqamini tekshiring." },
            422
        );
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
        id: crypto.randomUUID(),
        submitted_at: new Date().toISOString(),
        student_name: studentName,
        student_phone: `+998${localPhone}`,
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
        const result = await response.json();
        if (!response.ok || !result.ok) {
            throw new Error("Google Sheets rejected the submission");
        }
    } catch (error) {
        console.error("Registration forwarding failed", error.message);
        return jsonResponse(
            { ok: false, message: "Arizani saqlab bo'lmadi. Qayta urinib ko'ring." },
            502
        );
    }

    return jsonResponse({ ok: true, id: lead.id }, 201);
}

export function onRequest(context) {
    if (context.request.method !== "POST") {
        return jsonResponse({ ok: false, message: "Method not allowed" }, 405);
    }
    return onRequestPost(context);
}
