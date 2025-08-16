"use client";

import React, { createContext, useContext, useEffect, useMemo, useState } from "react";
import { messages as M } from "@/app/i18n.js";

type Lang = "en" | "de";
type Dict = Record<string,string>;
const messages = M as Record<Lang, Dict>;

type Ctx = {
  lang: Lang;
  setLang: (l: Lang) => void;
  t: (k: string, fb?: string) => string;
  ready: boolean;
};

const I18nContext = createContext<Ctx | null>(null);

export function I18nProvider({
  children,
  initialLang = "en",
}: {
  children: React.ReactNode;
  initialLang?: Lang;
}) {
  const [lang, setLang] = useState<Lang>(initialLang);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    try {
      const stored = window.localStorage.getItem("lang") as Lang | null;
      let next: Lang | null = null;
      if (stored === "en" || stored === "de") next = stored;
      else {
        const nav = (navigator?.language || "").toLowerCase();
        next = nav.startsWith("de") ? "de" : "en";
      }
      if (next && next !== lang) setLang(next);
    } finally {
      setReady(true);
    }
  }, []); // run once after mount

  useEffect(() => {
    try { window.localStorage.setItem("lang", lang); } catch {}
    if (typeof document !== "undefined") document.documentElement.lang = lang;
  }, [lang]);

  const t = useMemo(() => {
    const dict = messages[lang] || {};
    return (k: string, fb = "") => dict[k] ?? fb;
  }, [lang]);

  const value = useMemo(() => ({ lang, setLang, t, ready }), [lang, t, ready]);
  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n() {
  const ctx = useContext(I18nContext);
  if (!ctx) throw new Error("useI18n must be used inside <I18nProvider>");
  return ctx;
}