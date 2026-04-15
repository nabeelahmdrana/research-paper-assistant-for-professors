"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { BookOpen, Menu, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { checkHealth } from "@/lib/api";

const navLinks = [
  { href: "/", label: "Dashboard" },
  { href: "/upload", label: "Upload" },
  { href: "/query", label: "Query" },
  { href: "/library", label: "Library" },
];

type ConnectionStatus = "checking" | "connected" | "disconnected";

export function Navbar() {
  const pathname = usePathname();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState<ConnectionStatus>("checking");

  useEffect(() => {
    checkHealth()
      .then((h) => setConnectionStatus(h.status === "ok" ? "connected" : "disconnected"))
      .catch(() => setConnectionStatus("disconnected"));
  }, []);

  const statusDot = {
    checking: "bg-yellow-400",
    connected: "bg-green-500",
    disconnected: "bg-red-400",
  }[connectionStatus];

  const statusLabel = {
    checking: "Checking...",
    connected: "Connected",
    disconnected: "Disconnected",
  }[connectionStatus];

  return (
    <header className="sticky top-0 z-50 bg-white border-b border-gray-200">
      <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
        {/* Logo */}
        <Link href="/" className="flex items-center gap-2 font-bold text-blue-600 text-lg">
          <BookOpen className="w-10 h-10" />
        </Link>

        {/* Desktop nav */}
        <nav className="hidden md:flex items-center gap-6">
          {navLinks.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className={cn(
                "text-sm transition-colors",
                pathname === link.href
                  ? "text-blue-600 font-semibold border-b-2 border-blue-600 pb-0.5"
                  : "text-gray-600 hover:text-gray-900"
              )}
            >
              {link.label}
            </Link>
          ))}
        </nav>

        {/* Status indicator */}
        <div className="hidden md:flex items-center gap-2">
          <span className={cn("w-2 h-2 rounded-full inline-block", statusDot)} />
          <span className="text-xs text-gray-500">{statusLabel}</span>
        </div>

        {/* Mobile hamburger */}
        <button
          className="md:hidden p-2 rounded-md text-gray-600 hover:text-gray-900 hover:bg-gray-100"
          onClick={() => setMobileOpen(!mobileOpen)}
          aria-label="Toggle menu"
        >
          {mobileOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
        </button>
      </div>

      {/* Mobile menu */}
      {mobileOpen && (
        <div className="md:hidden border-t border-gray-200 bg-white px-6 py-4 flex flex-col gap-4">
          {navLinks.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              onClick={() => setMobileOpen(false)}
              className={cn(
                "text-sm transition-colors",
                pathname === link.href
                  ? "text-blue-600 font-semibold"
                  : "text-gray-600 hover:text-gray-900"
              )}
            >
              {link.label}
            </Link>
          ))}
          <div className="flex items-center gap-2 pt-2 border-t border-gray-200">
            <span className={cn("w-2 h-2 rounded-full inline-block", statusDot)} />
            <span className="text-xs text-gray-500">{statusLabel}</span>
          </div>
        </div>
      )}
    </header>
  );
}
