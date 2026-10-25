(function () {
    "use strict";

    var root = document.documentElement;
    // If the page was already painted before this script ran (a first visit on a slow connection),
    // what is on screen stays as it is instead of hiding and animating in a second time.
    var painted = !!(window.performance && performance.getEntriesByType && performance.getEntriesByType("paint").length);
    function onScreen(el) {
        var rect = el.getBoundingClientRect();
        return rect.top < window.innerHeight && rect.bottom > 0;
    }
    if (painted) {
        document.querySelectorAll(".rv").forEach(function (el) {
            if (onScreen(el)) el.classList.remove("rv", "d1", "d2", "d3");
        });
    }
    root.classList.add("js");

    // Language: every page exists in Uzbek, Russian and English; the switcher opens the same page in
    // the chosen language. The old Google Translate cookie is cleared so it never translates a page twice.
    (function clearOldTranslateCookie() {
        var host = window.location.hostname;
        ["", ";domain=" + host, ";domain=." + host].forEach(function (domain) {
            document.cookie = "googtrans=;expires=Thu, 01 Jan 1970 00:00:00 GMT;path=/" + domain;
        });
    }());

    document.addEventListener("DOMContentLoaded", function () {
        document.querySelectorAll("[data-lang-select]").forEach(function (select) {
            select.addEventListener("change", function () {
                if (select.value) window.location.assign(select.value);
            });
        });

        // Header: shadow once the page scrolls; on phones it slides away while reading down and
        // comes back on the first scroll up.
        var header = document.querySelector("[data-header]");
        var dock = document.querySelector("[data-dock]");
        var hero = document.querySelector("[data-hero]");
        var lastY = window.scrollY || 0;
        var compact = window.matchMedia("(max-width: 1023px)");
        function onScroll() {
            var y = window.scrollY || 0;
            var menuOpen = root.classList.contains("menu-open");
            if (header) {
                header.classList.toggle("is-scrolled", y > 8);
                if (Math.abs(y - lastY) > 6 || y < 80) {
                    header.classList.toggle("is-hidden", compact.matches && !menuOpen && y > 420 && y > lastY);
                    lastY = y;
                }
            }
            if (dock) {
                var threshold = hero ? hero.offsetTop + hero.offsetHeight * 0.6 : 320;
                dock.classList.toggle("is-visible", y > threshold && !menuOpen);
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

        var reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
        var splitText = !reduceMotion;

        function eachWord(node, make) {
            Array.prototype.slice.call(node.childNodes).forEach(function (child) {
                if (child.nodeType === 1) {
                    eachWord(child, make);
                    return;
                }
                if (child.nodeType !== 3) return;
                var fragment = document.createDocumentFragment();
                child.textContent.split(/(\s+)/).forEach(function (part) {
                    if (!part) return;
                    fragment.appendChild(/^\s+$/.test(part) ? document.createTextNode(part) : make(part));
                });
                child.parentNode.replaceChild(fragment, child);
            });
        }

        // Headlines: words rise in one after another.
        document.querySelectorAll("[data-split], .page-hero h1").forEach(function (heading) {
            heading.classList.add("words");
            if (!splitText || (painted && onScreen(heading))) {
                heading.classList.add("in");
                return;
            }
            var index = 0;
            var label = heading.textContent.replace(/\s+/g, " ").trim();
            eachWord(heading, function (word) {
                var outer = document.createElement("span");
                var inner = document.createElement("span");
                outer.className = "w";
                inner.textContent = word;
                inner.style.transitionDelay = (0.06 + index * 0.055) + "s";
                index += 1;
                outer.appendChild(inner);
                return outer;
            });
            heading.setAttribute("aria-label", label);
            requestAnimationFrame(function () {
                requestAnimationFrame(function () { heading.classList.add("in"); });
            });
        });

        // Statement text: each word gets its index, CSS lights it as the section's progress passes it.
        document.querySelectorAll("[data-words]").forEach(function (text) {
            if (!splitText) return;
            var index = 0;
            eachWord(text, function (word) {
                var span = document.createElement("span");
                span.className = "sw";
                span.textContent = word;
                span.style.setProperty("--i", index);
                index += 1;
                return span;
            });
            text.style.setProperty("--n", index);
        });

        // Reveal blocks as they scroll into view. Items in the same grid follow each other; once in
        // place an item drops the reveal styles so hover motion is quick again.
        var items = document.querySelectorAll(".rv");
        if ("IntersectionObserver" in window && !reduceMotion) {
            items.forEach(function (item) {
                var parent = item.parentElement;
                if (parent && (parent.classList.contains("grid") || parent.classList.contains("steps") || parent.classList.contains("faq"))) {
                    var siblings = Array.prototype.filter.call(parent.children, function (el) { return el.classList.contains("rv"); });
                    item.style.setProperty("--d", (siblings.indexOf(item) % 4) * 0.09 + "s");
                }
                item.addEventListener("transitionend", function settle(event) {
                    if (event.target !== item || event.propertyName !== "transform" || !item.classList.contains("in")) return;
                    item.removeEventListener("transitionend", settle);
                    item.classList.remove("rv", "in", "d1", "d2", "d3");
                    item.style.removeProperty("--d");
                });
            });
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

        // Scroll-linked motion: each [data-scrub] element gets --p from 0 to 1.
        //   exit    — 0 at rest, 1 once the element has scrolled out at the top (heroes)
        //   enter   — 0 as it enters at the bottom, 1 when its top reaches 30% of the screen
        //   text    — like enter, over a longer stretch, so words light up while reading
        //   through — 0 entering at the bottom, 1 leaving at the top (parallax)
        document.querySelectorAll(".page-hero").forEach(function (el) { el.setAttribute("data-scrub", "exit"); });
        document.querySelectorAll(".stage-top, .courses-band").forEach(function (el) { el.setAttribute("data-scrub", "through"); });
        var scrubbed = Array.prototype.slice.call(document.querySelectorAll("[data-scrub]"));
        if (reduceMotion) {
            scrubbed.forEach(function (el) { el.classList.add("in"); });
            scrubbed = [];
        }
        var pending = false;
        function clamp(value) { return value < 0 ? 0 : value > 1 ? 1 : value; }
        function scrub() {
            pending = false;
            var vh = window.innerHeight;
            scrubbed.forEach(function (el) {
                var box = el.getBoundingClientRect();
                if (box.bottom < -40 || box.top > vh + 40) return;
                var mode = el.getAttribute("data-scrub");
                var p;
                if (mode === "exit") p = clamp(-box.top / Math.max(box.height, 1));
                else if (mode === "through") p = clamp((vh - box.top) / (vh + box.height));
                else if (mode === "text") p = clamp((vh * 0.9 - box.top) / (box.height + vh * 0.35));
                else p = clamp((vh - box.top) / (vh * 0.7));
                el.style.setProperty("--p", p.toFixed(4));
                if (mode === "enter" && p > 0.55) el.classList.add("in");
            });
        }
        function requestScrub() {
            if (!pending) {
                pending = true;
                requestAnimationFrame(scrub);
            }
        }
        if (scrubbed.length) {
            window.addEventListener("scroll", requestScrub, { passive: true });
            window.addEventListener("resize", requestScrub);
            scrub();
        }

        // Photo rows: arrow buttons scroll one screenful and grey out at the ends.
        document.querySelectorAll("[data-scroll-prev], [data-scroll-next]").forEach(function (button) {
            var row = document.getElementById(button.getAttribute("data-scroll-prev") || button.getAttribute("data-scroll-next"));
            if (!row) return;
            var step = button.hasAttribute("data-scroll-prev") ? -1 : 1;
            function update() {
                var max = row.scrollWidth - row.clientWidth - 2;
                button.disabled = step < 0 ? row.scrollLeft <= 2 : row.scrollLeft >= max;
            }
            button.addEventListener("click", function () {
                row.scrollBy({ left: step * row.clientWidth, behavior: reduceMotion ? "auto" : "smooth" });
            });
            row.addEventListener("scroll", update, { passive: true });
            window.addEventListener("resize", update);
            update();
        });

        // Photo rows with data-autoscroll: every few seconds glide slowly to the next photo, and from
        // the last one back to the first. Pauses while the visitor touches, hovers, focuses or uses the
        // arrows (resuming a few seconds later), while the row is off screen or the tab is hidden, and
        // never runs under reduced motion.
        document.querySelectorAll("[data-autoscroll]").forEach(function (row) {
            if (reduceMotion) return;
            var DELAY = 3500;
            var GLIDE = 1400;
            var RESUME = 6000;
            var timer = null;
            var visible = false;
            var heldUntil = 0;
            var gliding = false;

            function easeInOut(t) { return t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2; }

            function glideTo(target) {
                var start = row.scrollLeft;
                var distance = target - start;
                var began = null;
                gliding = true;
                row.style.scrollSnapType = "none";
                row.style.scrollBehavior = "auto";
                function frame(now) {
                    if (began === null) began = now;
                    var t = Math.min((now - began) / GLIDE, 1);
                    row.scrollLeft = start + distance * easeInOut(t);
                    if (t < 1 && gliding) {
                        requestAnimationFrame(frame);
                    } else {
                        gliding = false;
                        row.style.scrollSnapType = "";
                        row.style.scrollBehavior = "";
                    }
                }
                requestAnimationFrame(frame);
            }

            function next() {
                var items = Array.prototype.slice.call(row.children);
                var max = row.scrollWidth - row.clientWidth;
                if (!items.length || max <= 2) return;
                if (row.scrollLeft >= max - 2) {
                    glideTo(0);
                    return;
                }
                var origin = row.getBoundingClientRect().left + parseFloat(getComputedStyle(row).scrollPaddingLeft || 0);
                for (var i = 0; i < items.length; i += 1) {
                    var offset = items[i].getBoundingClientRect().left - origin;
                    if (offset > 4) {
                        glideTo(Math.min(row.scrollLeft + offset, max));
                        return;
                    }
                }
                glideTo(max);
            }

            function schedule() {
                clearTimeout(timer);
                timer = null;
                if (!visible || document.hidden) return;
                var wait = Math.max(DELAY, heldUntil - Date.now());
                timer = setTimeout(function () {
                    if (Date.now() < heldUntil) {
                        schedule();
                        return;
                    }
                    next();
                    schedule();
                }, wait);
            }

            function hold() {
                gliding = false;
                heldUntil = Date.now() + RESUME;
                schedule();
            }

            ["pointerdown", "touchstart", "wheel", "keydown", "focusin"].forEach(function (type) {
                row.addEventListener(type, hold, { passive: true });
            });
            row.addEventListener("pointerenter", function (event) {
                if (event.pointerType === "mouse") hold();
            });
            row.addEventListener("pointermove", function (event) {
                if (event.pointerType === "mouse") heldUntil = Date.now() + RESUME;
            }, { passive: true });
            document.querySelectorAll('[data-scroll-prev="' + row.id + '"], [data-scroll-next="' + row.id + '"]').forEach(function (button) {
                button.addEventListener("click", hold);
            });
            document.addEventListener("visibilitychange", schedule);
            if ("IntersectionObserver" in window) {
                new IntersectionObserver(function (entries) {
                    visible = entries[0].isIntersecting;
                    schedule();
                }, { threshold: 0.4 }).observe(row);
            } else {
                visible = true;
                schedule();
            }
        });

        // Pointer effects on devices with a mouse: the hero poster tilts, cards catch a soft light.
        if (!reduceMotion && window.matchMedia("(hover: hover) and (pointer: fine)").matches) {
            var poster = document.querySelector(".hero-poster");
            var frame = poster && poster.querySelector(".hero-poster-frame");
            if (frame) {
                poster.addEventListener("pointermove", function (event) {
                    var box = poster.getBoundingClientRect();
                    var x = (event.clientX - box.left) / box.width - 0.5;
                    var y = (event.clientY - box.top) / box.height - 0.5;
                    frame.style.setProperty("--ry", (x * 10).toFixed(2) + "deg");
                    frame.style.setProperty("--rx", (y * -8).toFixed(2) + "deg");
                });
                poster.addEventListener("pointerleave", function () {
                    frame.style.setProperty("--ry", "0deg");
                    frame.style.setProperty("--rx", "0deg");
                });
            }
            document.addEventListener("pointermove", function (event) {
                var card = event.target.closest && event.target.closest(".card.lift, a.card");
                if (!card) return;
                var box = card.getBoundingClientRect();
                card.style.setProperty("--mx", (event.clientX - box.left) + "px");
                card.style.setProperty("--my", (event.clientY - box.top) + "px");
            }, { passive: true });
        }
    });
}());
