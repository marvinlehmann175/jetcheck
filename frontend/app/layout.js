// app/layout.js
import "./globals.css";

export const metadata = {
  title: "JetCheck",
  description: "Empty legs – exklusiv & schnell",
};

export default function RootLayout({ children }) {
  return (
    <html lang="de">
      <body>{children}</body>
    </html>
  );
}