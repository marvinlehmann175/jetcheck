"use client";

import Link from "next/link";
import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { usePathname } from "next/navigation";
import clsx from "clsx";
import { useI18n } from "@/app/_providers/I18nProvider";

const FLAG: Record<"en" | "de", string> = { en: "🇺🇸", de: "🇩🇪" };

const NAV = [
  { href: "/private-jet", label: "Private Jet" },
  { href: "/helicopter", label: "Helicopter", disabled: true },
  { href: "/yacht", label: "Yacht", disabled: true },
];

export default function Header() {
  const pathname = usePathname();
  const { lang, setLang, ready } = useI18n();

  // refs
  const shellRef = useRef<HTMLDivElement | null>(null);
  const navRef = useRef<HTMLElement | null>(null);
  const blobRef = useRef<HTMLDivElement | null>(null);
  const brandRef = useRef<HTMLAnchorElement | null>(null);
  const linksRef = useRef<HTMLAnchorElement[]>([]); // anchors order: [brand, ...NAV]

  const [showLang, setShowLang] = useState(false);

  // callback ref factory (note: +1 because brand is index 0)
  const setLinkRef =
    (i: number) =>
    (el: HTMLAnchorElement | null): void => {
      if (el) linksRef.current[i + 1] = el;
    };

  const moveBlob = (el?: HTMLElement | null) => {
    const blob = blobRef.current;
    const shell = shellRef.current;
    if (!blob || !shell || !el) return;

    const shellRect = shell.getBoundingClientRect();
    const r = el.getBoundingClientRect();
    const x = r.left - shellRect.left;
    const w = r.width;

    blob.style.setProperty("--blob-x", `${x}px`);
    blob.style.setProperty("--blob-w", `${w}px`);
  };

  // collect anchors once mounted
  useLayoutEffect(() => {
    const arr: HTMLAnchorElement[] = [];
    if (brandRef.current) arr.push(brandRef.current);
    if (navRef.current) {
      arr.push(
        ...Array.from(
          navRef.current.querySelectorAll<HTMLAnchorElement>("a.topnav__link")
        )
      );
    }
    linksRef.current = arr;
  }, []);

  // position blob under active on route change
  useEffect(() => {
    const anchors = linksRef.current;
    if (!anchors.length) return;

    const activeIdx = NAV.findIndex((n) => pathname?.startsWith(n.href));
    // +1 because anchors[0] = brand
    const target = anchors[activeIdx >= 0 ? activeIdx + 1 : 0] || anchors[0];

    requestAnimationFrame(() => moveBlob(target));
  }, [pathname]);

  // recalc on resize / layout shifts
  useEffect(() => {
    const onResize = () => {
      const anchors = linksRef.current;
      if (!anchors.length) return;
      const activeIdx = NAV.findIndex((n) => pathname?.startsWith(n.href));
      moveBlob(anchors[activeIdx >= 0 ? activeIdx + 1 : 0] || anchors[0]);
    };

    const ro = new ResizeObserver(onResize);
    if (shellRef.current) ro.observe(shellRef.current);
    window.addEventListener("resize", onResize);
    const raf = requestAnimationFrame(onResize);

    return () => {
      window.removeEventListener("resize", onResize);
      cancelAnimationFrame(raf);
      ro.disconnect();
    };
  }, [pathname]);

  const handleMouseLeave = () => {
    const anchors = linksRef.current;
    if (!anchors.length) return;
    const activeIdx = NAV.findIndex((n) => pathname?.startsWith(n.href));
    moveBlob(anchors[activeIdx >= 0 ? activeIdx + 1 : 0] || anchors[0]);
  };

  return (
    <>
      {/* goo filter */}
      <svg width="0" height="0" style={{ position: "absolute" }} aria-hidden>
        <filter id="goo">
          <feGaussianBlur in="SourceGraphic" stdDeviation="6" result="blur" />
          <feColorMatrix
            in="blur"
            result="goo"
            type="matrix"
            values="
              1 0 0 0 0
              0 1 0 0 0
              0 0 1 0 0
              0 0 0 18 -8"
          />
          <feBlend in="SourceGraphic" in2="goo" />
        </filter>
      </svg>

      <div className="topbar topbar--glass">
        <div
          ref={shellRef}
          className="topbar__shell"
          onMouseLeave={handleMouseLeave}
        >
          {/* blob lives under brand + nav */}
          <div ref={blobRef} className="nav-blob" />

          {/* brand participates in blob (index 0) */}
          <div className="brand">
            <Link
              href="/"
              ref={brandRef}
              className="brand-link nav-like"
              aria-label="Go home"
              onMouseEnter={(e) => moveBlob(e.currentTarget)}
            >
              <span className="brand-dot black">A</span>
              <span className="logo">vante</span>
            </Link>
          </div>

          {/* primary nav */}
          <nav
            ref={navRef}
            className="topnav"
            role="navigation"
            aria-label="Primary"
          >
            {NAV.map((item, i) => {
              const active = pathname?.startsWith(item.href);
              const disabled = !!item.disabled;
              return (
                <span key={item.href} className="topnav__item">
                  <Link
                    href={disabled ? "#" : item.href}
                    ref={setLinkRef(i)}
                    className={clsx(
                      "topnav__link",
                      active && "topnav__link--active",
                      disabled && "topnav__link--disabled"
                    )}
                    aria-current={active ? "page" : undefined}
                    aria-disabled={disabled || undefined}
                    tabIndex={disabled ? -1 : 0}
                    onMouseEnter={(e) => !disabled && moveBlob(e.currentTarget)}
                  >
                    {item.label}
                  </Link>
                  {disabled && <span className="soon-badge">Soon</span>}
                </span>
              );
            })}
          </nav>

          {/* right utils */}
          <div className="topnav__utils">
            <Link href="/signin" className="util-like util-like--primary">
              Sign In
            </Link>

            <div className="lang-wrapper">
              <button
                className="util-like lang-switch"
                aria-haspopup="menu"
                aria-expanded={showLang ? "true" : "false"}
                aria-label="Language"
                onClick={() => setShowLang((s) => !s)}
              >
                <span className="flag">{FLAG[ready ? lang : "en"]}</span>
                <span className="lang-code">
                  {(ready ? lang : "en").toUpperCase()}
                </span>
              </button>

              {showLang && (
                <div className="lang-popover" role="menu">
                  <button
                    role="menuitemradio"
                    aria-checked={lang === "en"}
                    className={clsx("lang-item", lang === "en" && "is-active")}
                    onClick={() => {
                      setLang("en");
                      setShowLang(false);
                    }}
                  >
                    <span className="flag">🇺🇸</span> EN — English
                  </button>
                  <button
                    role="menuitemradio"
                    aria-checked={lang === "de"}
                    className={clsx("lang-item", lang === "de" && "is-active")}
                    onClick={() => {
                      setLang("de");
                      setShowLang(false);
                    }}
                  >
                    <span className="flag">🇩🇪</span> DE — Deutsch
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      <div className="topbar-spacer" />
    </>
  );
}
