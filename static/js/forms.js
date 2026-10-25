(function () {
    "use strict";

    // Messages follow the page language (<html lang>); Uzbek is the source text, including the
    // messages the /api/register function returns.
    var LANG = (document.documentElement.getAttribute("lang") || "uz").slice(0, 2);
    var MESSAGES = {
        ru: {
            "Ism va familiyangizni kiriting.": "Введите имя и фамилию.",
            "Telefon raqamingizni tekshiring.": "Проверьте номер телефона.",
            "Dastur tanlang.": "Выберите программу.",
            "Filial tanlang.": "Выберите филиал.",
            "Sinfni tanlang.": "Выберите класс.",
            "Bog'lanishimizga rozilik bering.": "Дайте согласие на связь с вами.",
            "Yuborilmoqda...": "Отправляем...",
            "Arizani yuborib bo'lmadi.": "Не удалось отправить заявку.",
            "Internet aloqasini tekshiring va qayta urinib ko'ring.": "Проверьте подключение к интернету и попробуйте ещё раз.",
            "Xatolik yuz berdi. Qayta urinib ko'ring.": "Произошла ошибка. Попробуйте ещё раз.",
            "Ism va telefon raqamingizni tekshiring.": "Проверьте имя и номер телефона.",
            "Tilni qayta tanlang.": "Выберите язык ещё раз.",
            "Tug'ilgan sanani tekshiring.": "Проверьте дату рождения.",
            "Dastur va filialni qayta tanlang.": "Выберите программу и филиал ещё раз.",
            "Xavfsizlik tekshiruvidan qayta o'ting.": "Пройдите проверку безопасности ещё раз.",
            "Xato kodi": "Код ошибки"
        },
        en: {
            "Ism va familiyangizni kiriting.": "Please enter your full name.",
            "Telefon raqamingizni tekshiring.": "Please check your phone number.",
            "Dastur tanlang.": "Please choose a programme.",
            "Filial tanlang.": "Please choose a branch.",
            "Sinfni tanlang.": "Please choose a grade.",
            "Bog'lanishimizga rozilik bering.": "Please agree that we may contact you.",
            "Yuborilmoqda...": "Sending...",
            "Arizani yuborib bo'lmadi.": "We couldn't send your application.",
            "Internet aloqasini tekshiring va qayta urinib ko'ring.": "Check your internet connection and try again.",
            "Xatolik yuz berdi. Qayta urinib ko'ring.": "Something went wrong. Please try again.",
            "Ism va telefon raqamingizni tekshiring.": "Please check your name and phone number.",
            "Tilni qayta tanlang.": "Please choose the language again.",
            "Tug'ilgan sanani tekshiring.": "Please check the date of birth.",
            "Dastur va filialni qayta tanlang.": "Please choose the programme and branch again.",
            "Xavfsizlik tekshiruvidan qayta o'ting.": "Please complete the security check again.",
            "Xato kodi": "Error code"
        }
    };

    function t(text) {
        var table = MESSAGES[LANG];
        return (table && table[text]) || text;
    }

    // Server messages: known ones are translated; others become a generic message plus the error code.
    function serverMessage(result) {
        var message = (result && result.message) || "";
        if (LANG === "uz" || !message) return message || t("Arizani yuborib bo'lmadi.");
        if (MESSAGES[LANG][message]) return MESSAGES[LANG][message];
        return t("Xatolik yuz berdi. Qayta urinib ko'ring.") + (result.reference ? " " + t("Xato kodi") + ": " + result.reference : "");
    }

    function fieldValue(form, name) {
        var field = form.elements.namedItem(name);
        return field && typeof field.value === "string" ? field.value.trim() : "";
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

    function utm(name) {
        return (new URLSearchParams(window.location.search).get(name) || "").slice(0, 150);
    }

    function statusElement(form) {
        var status = form.querySelector("[data-form-status]");
        if (!status) {
            status = document.createElement("p");
            status.setAttribute("data-form-status", "");
            status.setAttribute("role", "status");
            status.setAttribute("aria-live", "polite");
            status.className = "form-status";
            form.appendChild(status);
        }
        return status;
    }

    // crypto.randomUUID is missing on older phones (iOS before 15.4); the server accepts any hex id.
    function newSubmissionId() {
        if (window.crypto && typeof window.crypto.randomUUID === "function") {
            return window.crypto.randomUUID();
        }
        var bytes = new Uint8Array(16);
        window.crypto.getRandomValues(bytes);
        var id = "";
        for (var i = 0; i < bytes.length; i += 1) {
            id += ("0" + bytes[i].toString(16)).slice(-2);
        }
        return id;
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
        if (error) error.textContent = message || "";
    }

    function validateRegistration(form) {
        var valid = true;
        var name = fieldValue(form, "student_name");
        var phone = normalizeUzPhone(fieldValue(form, "student_phone"));
        var program = fieldValue(form, "course");
        var branch = fieldValue(form, "preferred_branch");
        setFieldError(form, "student_name", name.length >= 2 ? "" : t("Ism va familiyangizni kiriting."));
        setFieldError(form, "student_phone", /^\d{9}$/.test(phone) ? "" : t("Telefon raqamingizni tekshiring."));
        setFieldError(form, "course", program ? "" : t("Dastur tanlang."));
        setFieldError(form, "preferred_branch", branch ? "" : t("Filial tanlang."));
        valid = name.length >= 2 && /^\d{9}$/.test(phone) && Boolean(program) && Boolean(branch);
        return valid;
    }

    async function submitRegistration(form) {
        if (form.dataset.submitting === "true") return;
        var button = form.querySelector('button[type="submit"]');
        var status = statusElement(form);
        var originalLabel = button ? button.textContent : "";
        var submissionId = form.dataset.submissionId || newSubmissionId();
        form.dataset.submissionId = submissionId;
        var payload = {
            submission_id: submissionId,
            student_name: fieldValue(form, "student_name"),
            student_phone: normalizeUzPhone(fieldValue(form, "student_phone")),
            program: fieldValue(form, "course"),
            branch: fieldValue(form, "preferred_branch"),
            utm_source: utm("utm_source"),
            utm_medium: utm("utm_medium"),
            utm_campaign: utm("utm_campaign"),
            turnstile_token: fieldValue(form, "cf-turnstile-response"),
            website: fieldValue(form, "website"),
            page_url: window.location.href,
            referrer: document.referrer
        };

        status.textContent = "";
        form.dataset.submitting = "true";
        if (button) {
            button.disabled = true;
            button.textContent = t("Yuborilmoqda...");
        }

        try {
            var response = await fetch(form.action, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload)
            });
            var result = await response.json().catch(function () { return {}; });
            if (!response.ok || !result.ok) {
                throw new Error(serverMessage(result));
            }

            showRegistrationSuccess(form);
        } catch (error) {
            status.className = "form-status";
            var rawMessage = error && error.message ? error.message : "";
            status.textContent = /failed to fetch|networkerror|load failed/i.test(rawMessage)
                ? t("Internet aloqasini tekshiring va qayta urinib ko'ring.")
                : (rawMessage || t("Xatolik yuz berdi. Qayta urinib ko'ring."));
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

    var SCHOOL_GRADES = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11"];

    function validateSchoolEnquiry(form) {
        var name = fieldValue(form, "parent_name");
        var phone = normalizeUzPhone(fieldValue(form, "parent_phone"));
        var grade = fieldValue(form, "grade");
        var consent = form.elements.namedItem("consent");
        var checks = {
            parent_name: name.length >= 2 ? "" : t("Ism va familiyangizni kiriting."),
            parent_phone: /^\d{9}$/.test(phone) ? "" : t("Telefon raqamingizni tekshiring."),
            grade: SCHOOL_GRADES.indexOf(grade) !== -1 ? "" : t("Sinfni tanlang."),
            consent: consent && consent.checked ? "" : t("Bog'lanishimizga rozilik bering.")
        };
        var valid = true;
        Object.keys(checks).forEach(function (key) {
            setFieldError(form, key, checks[key]);
            if (checks[key]) valid = false;
        });
        return valid;
    }

    async function submitSchoolEnquiry(form) {
        if (form.dataset.submitting === "true") return;
        var button = form.querySelector('button[type="submit"]');
        var status = statusElement(form);
        var originalLabel = button ? button.innerHTML : "";
        var submissionId = form.dataset.submissionId || newSubmissionId();
        form.dataset.submissionId = submissionId;
        var payload = {
            form_type: "school-enquiry",
            submission_id: submissionId,
            parent_name: fieldValue(form, "parent_name"),
            parent_phone: normalizeUzPhone(fieldValue(form, "parent_phone")),
            child_name: fieldValue(form, "child_name"),
            child_birth_date: fieldValue(form, "child_birth_date"),
            grade: fieldValue(form, "grade"),
            language: fieldValue(form, "language"),
            message: fieldValue(form, "message"),
            consent: true,
            utm_source: utm("utm_source"),
            utm_medium: utm("utm_medium"),
            utm_campaign: utm("utm_campaign"),
            turnstile_token: fieldValue(form, "cf-turnstile-response"),
            website: fieldValue(form, "website"),
            page_url: window.location.href,
            referrer: document.referrer
        };
        status.textContent = "";
        form.dataset.submitting = "true";
        if (button) {
            button.disabled = true;
            button.textContent = t("Yuborilmoqda...");
        }
        try {
            var response = await fetch(form.action, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload)
            });
            var result = await response.json().catch(function () { return {}; });
            if (!response.ok || !result.ok) {
                throw new Error(serverMessage(result));
            }
            window.location.assign(form.getAttribute("data-thanks-url") || "/admissions/thanks");
            return;
        } catch (error) {
            var rawMessage = error && error.message ? error.message : "";
            status.textContent = /failed to fetch|networkerror|load failed/i.test(rawMessage)
                ? t("Internet aloqasini tekshiring va qayta urinib ko'ring.")
                : (rawMessage || t("Xatolik yuz berdi. Qayta urinib ko'ring."));
        }
        if (window.turnstile) {
            window.turnstile.reset();
        }
        if (button) {
            button.disabled = false;
            button.innerHTML = originalLabel;
        }
        form.dataset.submitting = "false";
    }

    // Phone fields format as "90 123 45 67" while typing; errors clear as soon as a field changes.
    function configureFields(form, phoneName, fieldNames) {
        var phone = form.elements.namedItem(phoneName);
        if (phone) {
            phone.value = formatUzPhoneInput(phone.value);
            phone.addEventListener("input", function () {
                phone.value = formatUzPhoneInput(phone.value);
                setFieldError(form, phoneName, "");
            });
        }
        fieldNames.forEach(function (name) {
            var field = form.elements.namedItem(name);
            if (!field) return;
            ["input", "change"].forEach(function (type) {
                field.addEventListener(type, function () { setFieldError(form, name, ""); });
            });
        });
    }

    // Course links (/register?program=ielts&branch=main) preselect the programme and branch.
    function preselectFromUrl(form) {
        var params = new URLSearchParams(window.location.search);
        [["course", params.get("program")], ["preferred_branch", params.get("branch")]].forEach(function (pair) {
            var select = form.elements.namedItem(pair[0]);
            if (select && pair[1] && select.querySelector('option[value="' + CSS.escape(pair[1]) + '"]')) {
                select.value = pair[1];
            }
        });
    }

    function focusFirstError(form) {
        var firstInvalid = form.querySelector('[aria-invalid="true"]');
        if (firstInvalid) firstInvalid.focus();
    }

    document.addEventListener("DOMContentLoaded", function () {
        document.querySelectorAll("form[data-static-lead-form]").forEach(function (form) {
            var isSchool = form.getAttribute("data-static-lead-form") === "school-enquiry";
            if (isSchool) {
                configureFields(form, "parent_phone", ["parent_name", "grade", "consent"]);
            } else {
                preselectFromUrl(form);
                configureFields(form, "student_phone", ["student_name", "course", "preferred_branch"]);
            }
            loadTurnstile(form);
            form.addEventListener("submit", function (event) {
                event.preventDefault();
                if (!(isSchool ? validateSchoolEnquiry(form) : validateRegistration(form))) {
                    focusFirstError(form);
                    return;
                }
                if (isSchool) {
                    submitSchoolEnquiry(form);
                } else {
                    submitRegistration(form);
                }
            });
        });
    });
}());
