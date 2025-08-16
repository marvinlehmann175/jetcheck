"use client";

import { I18nProvider } from "@/app/_providers/I18nProvider";

export default function Providers({
  children,
  initialLang,
}: {
  children: React.ReactNode;
  initialLang: "en" | "de";
}) {
  return <I18nProvider initialLang={initialLang}>{children}</I18nProvider>;
}