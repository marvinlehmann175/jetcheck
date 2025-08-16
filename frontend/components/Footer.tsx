// components/Footer.tsx
"use client";
export default function Footer() {
  return (
    <footer className="footer">
      <span suppressHydrationWarning>© {new Date().getFullYear()} JetCheck</span>
      <span className="sep">•</span>
      <a href="https://jetcheck-eight.vercel.app" target="_blank" rel="noreferrer">Live</a>
    </footer>
  );
}