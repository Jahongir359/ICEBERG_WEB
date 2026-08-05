(function () {
    "use strict";

    function fieldValue(form, name) {
        var field = form.elements.namedItem(name);
        return field && typeof field.value === "string" ? field.value.trim() : "";
    }

    function contactMessage(form) {
        return [
            "ICEBERG saytidan yangi xabar",
            "",
            "Ism: " + fieldValue(form, "name"),
            "Telefon: +998" + fieldValue(form, "phone"),
            "Xabar: " + fieldValue(form, "message")
        ].join("\n");
    }

    function loadTurnstile(form) {
        var siteKey = form.getAttribute("data-turnstile-sitekey");
        if (!siteKey) {
            return;
        }

        var button = form.querySelector('button[type="submit"]');
        var widget = document.createElement("div");
        widget.className = "cf-turnstile";
        widget.setAttribute("data-sitekey", siteKey);
        widget.setAttribute("data-action", "register");
        if (button) {
            button.parentNode.insertBefore(widget, button);
        } else {
            form.appendChild(widget);
        }

        if (!document.querySelector('script[src*="challenges.cloudflare.com/turnstile"]')) {
            var script = document.createElement("script");
            script.src = "https://challenges.cloudflare.com/turnstile/v0/api.js";
            script.async = true;
            script.defer = true;
            document.head.appendChild(script);
        }
    }

    function statusElement(form) {
        var status = form.querySelector("[data-form-status]");
        if (!status) {
            status = document.createElement("p");
            status.setAttribute("data-form-status", "");
            status.setAttribute("role", "status");
            status.setAttribute("aria-live", "polite");
            status.className = "mt-3 text-sm font-semibold";
            form.appendChild(status);
        }
        return status;
    }

    function showAdminContactChoice(form, status) {
        var previousChoice = form.querySelector("[data-admin-contact-choice]");
        if (previousChoice) {
            previousChoice.remove();
        }

        var choice = document.createElement("div");
        choice.setAttribute("data-admin-contact-choice", "");
        choice.className = "mt-4 rounded-2xl border border-sky-200 bg-sky-50 p-4";

        var question = document.createElement("p");
        question.className = "font-semibold text-slate-800";
        question.textContent = "Administrator bilan hozir Telegram orqali bog'lanishni xohlaysizmi?";

        var actions = document.createElement("div");
        actions.className = "mt-3 flex flex-wrap gap-3";

        var yesLink = document.createElement("a");
        yesLink.href = "https://t.me/iceberg_qabulxona";
        yesLink.target = "_blank";
        yesLink.rel = "noopener noreferrer";
        yesLink.className = "btn-main inline-flex items-center justify-center";
        yesLink.textContent = "Ha, Telegram orqali";

        var noButton = document.createElement("button");
        noButton.type = "button";
        noButton.className = "rounded-xl border border-slate-300 bg-white px-5 py-3 font-semibold text-slate-700";
        noButton.textContent = "Yo'q";
        noButton.addEventListener("click", function () {
            choice.remove();
            status.textContent = "Ma'lumotlaringiz saqlandi. Tez orada siz bilan bog'lanamiz.";
            status.focus();
        });

        actions.appendChild(yesLink);
        actions.appendChild(noButton);
        choice.appendChild(question);
        choice.appendChild(actions);
        form.appendChild(choice);
    }

    async function submitRegistration(form) {
        var button = form.querySelector('button[type="submit"]');
        var status = statusElement(form);
        var originalLabel = button ? button.textContent : "";
        var payload = {
            student_name: fieldValue(form, "student_name"),
            student_phone: fieldValue(form, "student_phone"),
            utm_source: fieldValue(form, "utm_source"),
            utm_medium: fieldValue(form, "utm_medium"),
            utm_campaign: fieldValue(form, "utm_campaign"),
            turnstile_token: fieldValue(form, "cf-turnstile-response"),
            website: fieldValue(form, "website"),
            page_url: window.location.href,
            referrer: document.referrer
        };

        status.textContent = "";
        if (button) {
            button.disabled = true;
            button.textContent = "Yuborilmoqda...";
        }

        try {
            var response = await fetch(form.action, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload)
            });
            var result = await response.json().catch(function () { return {}; });
            if (!response.ok || !result.ok) {
                throw new Error(result.message || "Arizani yuborib bo'lmadi.");
            }

            form.reset();
            status.className = "mt-3 text-sm font-semibold text-emerald-700";
            status.tabIndex = -1;
            status.textContent = "Ma'lumotlaringiz muvaffaqiyatli saqlandi.";
            showAdminContactChoice(form, status);
            status.focus();
        } catch (error) {
            status.className = "mt-3 text-sm font-semibold text-red-700";
            status.textContent = error.message || "Xatolik yuz berdi. Qayta urinib ko'ring.";
        } finally {
            if (window.turnstile) {
                window.turnstile.reset();
            }
            if (button) {
                button.disabled = false;
                button.textContent = originalLabel;
            }
        }
    }

    document.addEventListener("DOMContentLoaded", function () {
        document.querySelectorAll("form[data-static-lead-form]").forEach(function (form) {
            if (form.getAttribute("data-static-lead-form") === "register") {
                loadTurnstile(form);

                var honeypot = document.createElement("input");
                honeypot.type = "text";
                honeypot.name = "website";
                honeypot.tabIndex = -1;
                honeypot.autocomplete = "off";
                honeypot.setAttribute("aria-hidden", "true");
                honeypot.style.cssText = "position:absolute;left:-10000px;width:1px;height:1px;overflow:hidden";
                form.appendChild(honeypot);
            }

            form.addEventListener("submit", function (event) {
                event.preventDefault();
                if (!form.reportValidity()) {
                    return;
                }

                var kind = form.getAttribute("data-static-lead-form");
                if (kind === "register") {
                    submitRegistration(form);
                    return;
                }
                var message = contactMessage(form);
                var number = new URL(form.action).pathname.replace(/\D/g, "");
                window.location.assign(
                    "https://wa.me/" + number + "?text=" + encodeURIComponent(message)
                );
            });
        });
    });
}());
