(function () {
    "use strict";
    var english = document.documentElement.lang === "en";
    var translations = {
        "Ism va familiyangizni kiriting.": "Enter your full name.",
        "Telefon raqamingizni tekshiring.": "Check your phone number.",
        "Dastur tanlang.": "Choose a program.",
        "Filial tanlang.": "Choose a branch.",
        "Yuborilmoqda...": "Sending...",
        "Arizani yuborib bo'lmadi.": "Your request could not be submitted.",
        "Internet aloqasini tekshiring va qayta urinib ko'ring.": "Check your connection and try again.",
        "Xatolik yuz berdi. Qayta urinib ko'ring.": "Something went wrong. Please try again."
    };
    function translated(message) { return english ? (translations[message] || message) : message; }

    function fieldValue(form, name) {
        var field = form.elements.namedItem(name);
        return field && typeof field.value === "string" ? field.value.trim() : "";
    }

    function contactMessage(form) {
        return [
            english ? "New inquiry from the ICEBERG website" : "ICEBERG saytidan yangi xabar",
            "",
            (english ? "Name: " : "Ism: ") + fieldValue(form, "name"),
            (english ? "Phone: +998" : "Telefon: +998") + fieldValue(form, "phone"),
            (english ? "Message: " : "Xabar: ") + fieldValue(form, "message")
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
        // Uzbek is not a supported Turnstile locale; use its browser fallback.
        widget.setAttribute("data-language", english ? "en" : "auto");
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

    function normalizeUzPhone(value) {
        var digits = String(value || "").replace(/\D/g, "");
        if (digits.length === 12 && digits.indexOf("998") === 0) {
            digits = digits.slice(3);
        }
        return digits;
    }

    function formatUzPhoneInput(value) {
        var digits = normalizeUzPhone(value).slice(0, 9);
        return [
            digits.slice(0, 2),
            digits.slice(2, 5),
            digits.slice(5, 7),
            digits.slice(7, 9)
        ].filter(Boolean).join(" ");
    }

    function showRegistrationSuccess(form) {
        var success = document.querySelector("[data-registration-success]");
        form.reset();
        form.hidden = true;
        if (success) {
            success.hidden = false;
            success.focus();
        }
    }

    function setFieldError(form, name, message) {
        var field = form.elements.namedItem(name);
        var error = form.querySelector('[data-error-for="' + name + '"]');
        if (field) field.setAttribute("aria-invalid", message ? "true" : "false");
        if (error) error.textContent = translated(message) || "";
    }

    function validateRegistration(form) {
        var valid = true;
        var name = fieldValue(form, "student_name");
        var phone = normalizeUzPhone(fieldValue(form, "student_phone"));
        var program = fieldValue(form, "course");
        var branch = fieldValue(form, "preferred_branch");
        setFieldError(form, "student_name", name.length >= 2 ? "" : "Ism va familiyangizni kiriting.");
        setFieldError(form, "student_phone", /^\d{9}$/.test(phone) ? "" : "Telefon raqamingizni tekshiring.");
        setFieldError(form, "course", program ? "" : "Dastur tanlang.");
        setFieldError(form, "preferred_branch", branch ? "" : "Filial tanlang.");
        valid = name.length >= 2 && /^\d{9}$/.test(phone) && Boolean(program) && Boolean(branch);
        return valid;
    }

    async function submitRegistration(form) {
        if (form.dataset.submitting === "true") return;
        var button = form.querySelector('button[type="submit"]');
        var status = statusElement(form);
        var originalLabel = button ? button.textContent : "";
        var submissionId = form.dataset.submissionId || fieldValue(form, 'submission_id') || crypto.randomUUID();
        form.dataset.submissionId = submissionId;
        var payload = {
            submission_id: submissionId,
            student_name: fieldValue(form, "student_name"),
            student_phone: normalizeUzPhone(fieldValue(form, "student_phone")),
            program: fieldValue(form, "course"),
            branch: fieldValue(form, "preferred_branch"),
            utm_source: fieldValue(form, "utm_source"),
            utm_medium: fieldValue(form, "utm_medium"),
            utm_campaign: fieldValue(form, "utm_campaign"),
            turnstile_token: fieldValue(form, "cf-turnstile-response"),
            website: fieldValue(form, "website"),
            page_url: window.location.href,
            referrer: document.referrer
        };

        status.textContent = "";
        form.dataset.submitting = "true";
        if (button) {
            button.disabled = true;
            button.textContent = translated("Yuborilmoqda...");
        }

        try {
            var response = await fetch(form.action, {
                method: "POST",
                signal: AbortSignal.timeout(20000),
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload)
            });
            var result = await response.json().catch(function () { return {}; });
            if (!response.ok || !result.ok) {
                throw new Error(result.message || "Arizani yuborib bo'lmadi.");
            }

            showRegistrationSuccess(form);
        } catch (error) {
            status.className = "mt-3 text-sm font-semibold text-red-700";
            var rawMessage = error && error.message ? error.message : "";
            status.textContent = english
                ? "Your request could not be confirmed. Please retry or contact admissions by phone or Telegram."
                : (/failed to fetch|networkerror|load failed|timeout|aborted/i.test(rawMessage)
                    ? "Internet aloqasini tekshiring va qayta urinib ko'ring."
                    : (rawMessage || "Xatolik yuz berdi. Qayta urinib ko'ring."));
        } finally {
            if (window.turnstile) {
                window.turnstile.reset();
            }
            if (button) {
                button.disabled = false;
                button.textContent = originalLabel;
            }
            form.dataset.submitting = "false";
        }
    }

    function configureRegistration(form) {
        var params = new URLSearchParams(window.location.search);
        var program = params.get("program");
        var branch = params.get("branch");
        var programSelect = form.elements.namedItem("course");
        var branchSelect = form.elements.namedItem("preferred_branch");
        var phone = form.elements.namedItem("student_phone");
        if (programSelect && program && programSelect.querySelector('option[value="' + CSS.escape(program) + '"]')) {
            programSelect.value = program;
        }
        if (branchSelect && branch && branchSelect.querySelector('option[value="' + CSS.escape(branch) + '"]')) {
            branchSelect.value = branch;
        }
        if (phone) {
            phone.value = formatUzPhoneInput(phone.value);
            phone.addEventListener("input", function () {
                phone.value = formatUzPhoneInput(phone.value);
                setFieldError(form, "student_phone", "");
            });
        }
        ["student_name", "course", "preferred_branch"].forEach(function (name) {
            var field = form.elements.namedItem(name);
            if (field) field.addEventListener("input", function () { setFieldError(form, name, ""); });
        });
        if (!form.hasAttribute("data-static-lead-form")) {
            form.addEventListener("submit", function (event) {
                if (!validateRegistration(form)) {
                    event.preventDefault();
                    var firstInvalid = form.querySelector('[aria-invalid="true"]');
                    if (firstInvalid) firstInvalid.focus();
                    return;
                }
                var button = form.querySelector('button[type="submit"]');
                if (button) {
                    button.disabled = true;
                    button.textContent = translated("Yuborilmoqda...");
                }
            });
        }
    }

    document.addEventListener("DOMContentLoaded", function () {
        document.querySelectorAll("form[data-registration-form]").forEach(configureRegistration);
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
                    if (!validateRegistration(form)) {
                        var firstInvalid = form.querySelector('[aria-invalid="true"]');
                        if (firstInvalid) firstInvalid.focus();
                        return;
                    }
                    submitRegistration(form);
                    return;
                }
                var message = contactMessage(form);
                var chat = new URL(form.action);
                chat.searchParams.set("text", message);
                window.location.assign(chat.toString());
            });
        });
    });
}());
