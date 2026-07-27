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

    function registrationMessage(form) {
        var query = new URLSearchParams(window.location.search);
        var lines = [
            "ICEBERG kursiga yangi ro'yxatdan o'tish",
            "",
            "O'quvchi: " + fieldValue(form, "student_name"),
            "Telefon: +998" + fieldValue(form, "student_phone")
        ];
        ["utm_source", "utm_medium", "utm_campaign"].forEach(function (name) {
            var value = fieldValue(form, name) || query.get(name) || "";
            if (value) {
                lines.push(name + ": " + value);
            }
        });
        return lines.join("\n");
    }

    document.addEventListener("DOMContentLoaded", function () {
        document.querySelectorAll("form[data-static-lead-form]").forEach(function (form) {
            form.addEventListener("submit", function (event) {
                event.preventDefault();
                if (!form.reportValidity()) {
                    return;
                }

                var kind = form.getAttribute("data-static-lead-form");
                var message = kind === "register"
                    ? registrationMessage(form)
                    : contactMessage(form);
                var number = new URL(form.action).pathname.replace(/\D/g, "");
                window.location.assign(
                    "https://wa.me/" + number + "?text=" + encodeURIComponent(message)
                );
            });
        });
    });
}());
