import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Research Paper Assistant",
  description: "Local-first research paper assistant for professors",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <nav className="border-b px-6 py-4 flex gap-6">
          <a href="/" className="font-semibold text-blue-600">
            Research Query
          </a>
          <a href="/upload" className="font-semibold text-blue-600">
            Paper Library
          </a>
        </nav>
        <main className="container mx-auto px-6 py-8">{children}</main>
      </body>
    </html>
  );
}
