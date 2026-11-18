// Sends website submissions straight to the support inbox through Resend
// (https://resend.com). Shared by the Cloudflare Pages Functions in functions/api.
// This file lives outside functions/ so Cloudflare does not expose it as a route.

const RESEND_URL = "https://api.resend.com/emails";
export const DEFAULT_SUPPORT_EMAIL = "support@iceberglc.com";
export const DEFAULT_EMAIL_FROM = "ICEBERG Website <website@iceberglc.com>";

export function supportEmailConfigured(env) {
    return Boolean(env.RESEND_API_KEY);
}

function oneLine(value, maxLength) {
    return String(value || "").replace(/[\r\n]+/g, " ").trim().slice(0, maxLength);
}

// Returns true only when Resend accepted the email. Never throws: a mail failure
// must not hide a submission that was stored elsewhere.
export async function sendSupportEmail(env, { subject, lines, idempotencyKey }) {
    if (!supportEmailConfigured(env)) {
        return false;
    }
    try {
        const response = await fetch(RESEND_URL, {
            method: "POST",
            headers: {
                "Authorization": `Bearer ${env.RESEND_API_KEY}`,
                "Content-Type": "application/json",
                // Resend drops repeats of the same key for 24 hours, so a retried
                // submission with the same ID does not email support twice.
                "Idempotency-Key": oneLine(idempotencyKey, 256)
            },
            body: JSON.stringify({
                from: oneLine(env.EMAIL_FROM, 200) || DEFAULT_EMAIL_FROM,
                to: [oneLine(env.SUPPORT_EMAIL, 200) || DEFAULT_SUPPORT_EMAIL],
                subject: oneLine(subject, 200),
                text: lines.map(line => String(line ?? "").slice(0, 2500)).join("\n")
            }),
            signal: AbortSignal.timeout(8000)
        });
        if (!response.ok) {
            console.error("Support email rejected", response.status, (await response.text()).slice(0, 300));
            return false;
        }
        return true;
    } catch (error) {
        console.error("Support email failed", error.message);
        return false;
    }
}
