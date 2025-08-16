// components/MobileTabBar.tsx
"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import clsx from "clsx";

const TABS = [
  {
    href: "/private-jet",
    label: "Private Jet",
    icon: (
      <svg width="22" height="22" viewBox="0 0 24 24" fill="currentColor" aria-hidden>
        <path d="M2 16l8-3 3-8 3 8 6 3-6 1-3 6-3-6-8-1z" />
      </svg>
    ),
  },
  {
    href: "#",
    label: "Helicopter",
    soon: true,
    icon: (
      <svg width="22" height="22" viewBox="0 0 24 24" fill="currentColor" aria-hidden>
        <path d="M3 12h14a4 4 0 110 8H7a4 4 0 110-8zM2 6h20v2H2z" />
      </svg>
    ),
  },
  {
    href: "#",
    label: "Yacht",
    soon: true,
    icon: (
      <svg width="22" height="22" viewBox="0 0 24 24" fill="currentColor" aria-hidden>
        <path d="M3 17l3-5 8-3 4 5 3 3H3z" />
      </svg>
    ),
  },
  {
    href: "/signin",
    label: "Account",
    icon: (
      <svg width="22" height="22" viewBox="0 0 24 24" fill="currentColor" aria-hidden>
        <path d="M12 12a5 5 0 100-10 5 5 0 000 10zm-9 9a9 9 0 1118 0H3z" />
      </svg>
    ),
  },
];

export default function MobileTabBar() {
  const pathname = usePathname();

// components/MobileTabBar.tsx (replace the return block)
return (
  <>
    <div className="mobile-tabbar">
      <nav className="mobile-tabbar__pill" role="navigation" aria-label="App">
        {TABS.map((t) => {
          const active =
            t.href !== "#" && pathname?.startsWith(t.href) ? "is-active" : "";
          const disabled = t.soon || t.href === "#";
          const content = (
            <>
              <span className="tab-icon">{t.icon}</span>
              <span className="tab-label">
                {t.label}
                {t.soon && <span className="tab-soon">Soon</span>}
              </span>
            </>
          );
          return disabled ? (
            <span key={t.label} className={clsx("tab-item", active, "is-disabled")}>
              {content}
            </span>
          ) : (
            <Link key={t.label} href={t.href} className={clsx("tab-item", active)}>
              {content}
            </Link>
          );
        })}
      </nav>
    </div>
    <div className="mobile-tabbar-spacer" />
  </>
);
}