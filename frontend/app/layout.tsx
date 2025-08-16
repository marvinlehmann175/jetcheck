// app/layout.tsx
import type { Metadata, Viewport } from "next";
import "./globals.css";
import "./styles/nav.css";
import "./styles/controls.css";
import Header from "@/components/Header";
import Footer from "@/components/Footer";
import Providers from "@/app/Providers";
import { cookies } from "next/headers";

export const metadata: Metadata = {
  title: "Avante — Luxury Travel",
  description: "Private jets, helicopters, yachts — all in one place.",
  robots: {
    index: false,
    follow: false,
    nocache: true,
    googleBot: { index: false, follow: false, noimageindex: true },
  },
  icons: {
    icon: [
      { url: "/favicon-16x16.png", sizes: "16x16", type: "image/png" },
      { url: "/favicon-32x32.png", sizes: "32x32", type: "image/png" },
      { url: "/favicon.ico", sizes: "any" },
    ],
    apple: "/apple-touch-icon.png",
    other: [{ rel: "manifest", url: "/site.webmanifest" }],
  },
};

export const viewport: Viewport = { themeColor: "#0b0c10" };
export default async function RootLayout({ children }: { children: React.ReactNode }) {
  // In your environment, cookies() is async → await it
  const cookieStore = await cookies();
  const initialLang = (cookieStore.get("lang")?.value as "en" | "de") ?? "en";

  return (
    <html lang={initialLang} suppressHydrationWarning>
      <body suppressHydrationWarning>
        <Providers initialLang={initialLang}>
          <div className="screen">
            <Header />
            {children}
            <Footer />
          </div>
        </Providers>
      </body>
    </html>
  );
}