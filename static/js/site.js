(function () {
    "use strict";

    var root = document.documentElement;
    root.classList.add("js");

    // Language: Uzbek pages are the real content; RU/EN use the Google Translate widget for now.
    var LANG_COOKIE = "googtrans";

    function currentLanguage() {
        var match = document.cookie.match(/(?:^|;\s*)googtrans=\/uz\/(ru|en)/);
        return match ? match[1] : "uz";
    }

    function setLanguage(lang) {
        var host = window.location.hostname;
        var domains = ["", ";domain=" + host, ";domain=." + host];
        domains.forEach(function (domain) {
            if (lang === "uz") {
                document.cookie = LANG_COOKIE + "=;expires=Thu, 01 Jan 1970 00:00:00 GMT;path=/" + domain;
            } else {
                document.cookie = LANG_COOKIE + "=/uz/" + lang + ";path=/" + domain;
            }
        });
        window.location.reload();
    }

    function loadTranslate() {
        window.googleTranslateElementInit = function () {
            new window.google.translate.TranslateElement(
                { pageLanguage: "uz", includedLanguages: "uz,ru,en", autoDisplay: false },
                "google_translate_element"
            );
        };
        var script = document.createElement("script");
        script.src = "https://translate.google.com/translate_a/element.js?cb=googleTranslateElementInit";
        script.async = true;
        document.body.appendChild(script);
    }

    document.addEventListener("DOMContentLoaded", function () {
        var lang = currentLanguage();
        document.querySelectorAll("[data-lang-select]").forEach(function (select) {
            select.value = lang;
            select.addEventListener("change", function () { setLanguage(select.value); });
        });
        if (lang !== "uz") loadTranslate();

        // Header shadow once the page scrolls.
        var header = document.querySelector("[data-header]");
        var dock = document.querySelector("[data-dock]");
        var hero = document.querySelector("[data-hero]");
        function onScroll() {
            var y = window.scrollY || 0;
            if (header) header.classList.toggle("is-scrolled", y > 8);
            if (dock) {
                var threshold = hero ? hero.offsetTop + hero.offsetHeight * 0.6 : 320;
                dock.classList.toggle("is-visible", y > threshold && !root.classList.contains("menu-open"));
            }
        }
        window.addEventListener("scroll", onScroll, { passive: true });
        onScroll();

        // Mobile menu sheet.
        var menuButton = document.querySelector("[data-menu-button]");
        var sheet = document.getElementById("site-menu");
        function setMenu(open) {
            root.classList.toggle("menu-open", open);
            if (menuButton) {
                menuButton.setAttribute("aria-expanded", open ? "true" : "false");
                menuButton.setAttribute("aria-label", open ? menuButton.dataset.labelClose : menuButton.dataset.labelOpen);
            }
            if (sheet) sheet.inert = !open;
            onScroll();
        }
        if (menuButton && sheet) {
            sheet.inert = true;
            menuButton.addEventListener("click", function () {
                setMenu(!root.classList.contains("menu-open"));
            });
            sheet.addEventListener("click", function (event) {
                if (event.target.closest("a")) setMenu(false);
            });
            document.addEventListener("keydown", function (event) {
                if (event.key === "Escape" && root.classList.contains("menu-open")) {
                    setMenu(false);
                    menuButton.focus();
                }
            });
            window.matchMedia("(min-width: 1024px)").addEventListener("change", function (event) {
                if (event.matches) setMenu(false);
            });
        }

        // Split marked headlines into words so they can rise in one after another.
        var reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
        document.querySelectorAll("[data-split]").forEach(function (heading) {
            if (reduceMotion) {
                heading.classList.add("in");
                return;
            }
            var index = 0;
            (function wrap(node) {
                Array.prototype.slice.call(node.childNodes).forEach(function (child) {
                    if (child.nodeType === 3) {
                        var fragment = document.createDocumentFragment();
                        child.textContent.split(/(\s+)/).forEach(function (part) {
                            if (!part) return;
                            if (/^\s+$/.test(part)) {
                                fragment.appendChild(document.createTextNode(part));
                                return;
                            }
                            var outer = document.createElement("span");
                            var inner = document.createElement("span");
                            outer.className = "w";
                            inner.textContent = part;
                            inner.style.transitionDelay = (0.08 + index * 0.06) + "s";
                            index += 1;
                            outer.appendChild(inner);
                            fragment.appendChild(outer);
                        });
                        child.parentNode.replaceChild(fragment, child);
                    } else if (child.nodeType === 1) {
                        wrap(child);
                    }
                });
            }(heading));
            heading.setAttribute("aria-label", heading.textContent.replace(/\s+/g, " ").trim());
            requestAnimationFrame(function () {
                requestAnimationFrame(function () { heading.classList.add("in"); });
            });
        });

        // Reveal sections as they scroll into view.
        var items = document.querySelectorAll(".rv");
        if ("IntersectionObserver" in window && !window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
            var observer = new IntersectionObserver(function (entries) {
                entries.forEach(function (entry) {
                    if (entry.isIntersecting) {
                        entry.target.classList.add("in");
                        observer.unobserve(entry.target);
                    }
                });
            }, { rootMargin: "0px 0px -8% 0px", threshold: 0.08 });
            items.forEach(function (item) { observer.observe(item); });
        } else {
            items.forEach(function (item) { item.classList.add("in"); });
        }
    });
}());
