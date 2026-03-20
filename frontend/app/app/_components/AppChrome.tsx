"use client";

import type { CSSProperties, ReactNode } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";

type NavItem = {
  href: string;
  label: string;
};

const navItems: NavItem[] = [
  { href: "/app", label: "Dashboard" },
  { href: "/app/universes", label: "Universes" },
  { href: "/app/screens", label: "Screens" },
  { href: "/app/backtests", label: "Backtests" },
  { href: "/app/templates", label: "Templates" },
  { href: "/app/history", label: "History" },
  { href: "/app/schedules", label: "Schedules" },
  { href: "/app/alerts", label: "Alerts" },
  { href: "/app/collaboration", label: "Collaboration" },
  { href: "/app/settings", label: "Settings" },
];

type AppChromeProps = {
  children: ReactNode;
};

export function AppChrome({ children }: AppChromeProps) {
  const pathname = usePathname();

  return (
    <div style={frameStyle}>
      <header style={chromeStyle}>
        <div style={topRowStyle}>
          <div style={brandBlockStyle}>
            <Link href="/app" style={brandLinkStyle}>
              Greenblatt
            </Link>
            <p style={brandMetaStyle}>Systematic value research</p>
          </div>

          <nav aria-label="Primary" style={navStyle}>
            {navItems.map((item) => {
              const active = isActivePath(pathname, item.href);
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  style={active ? activeNavLinkStyle : navLinkStyle}
                  aria-current={active ? "page" : undefined}
                >
                  {item.label}
                </Link>
              );
            })}
          </nav>
        </div>
      </header>

      <div style={contentStyle}>{children}</div>
    </div>
  );
}

function isActivePath(pathname: string, href: string): boolean {
  if (href === "/app") {
    return pathname === "/app";
  }
  return pathname === href || pathname.startsWith(`${href}/`);
}

const frameStyle: CSSProperties = {
  minHeight: "100vh",
  padding: "0.65rem 0.75rem 1.25rem",
};

const chromeStyle: CSSProperties = {
  width: "min(1400px, 100%)",
  margin: "0 auto",
  padding: "0.7rem 0.85rem",
  borderRadius: "18px",
  background: "rgba(255, 255, 255, 0.82)",
  border: "1px solid rgba(73, 98, 128, 0.14)",
  boxShadow: "0 14px 36px rgba(27, 43, 65, 0.08)",
  backdropFilter: "blur(12px)",
};

const topRowStyle: CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  alignItems: "center",
  gap: "0.75rem",
  flexWrap: "wrap",
};

const brandBlockStyle: CSSProperties = {
  display: "flex",
  alignItems: "baseline",
  gap: "0.65rem",
  flexWrap: "wrap",
};

const brandLinkStyle: CSSProperties = {
  fontSize: "1.1rem",
  fontWeight: 700,
  textDecoration: "none",
  letterSpacing: "-0.03em",
};

const brandMetaStyle: CSSProperties = {
  margin: 0,
  color: "#496280",
  fontSize: "0.88rem",
};

const navStyle: CSSProperties = {
  display: "flex",
  gap: "0.45rem",
  flexWrap: "wrap",
  alignItems: "center",
  flex: "1 1 720px",
  justifyContent: "flex-end",
};

const navLinkStyle: CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  justifyContent: "center",
  minHeight: "1.9rem",
  padding: "0.38rem 0.72rem",
  borderRadius: "999px",
  textDecoration: "none",
  background: "#e7eef6",
  color: "#203247",
  fontSize: "0.92rem",
};

const activeNavLinkStyle: CSSProperties = {
  ...navLinkStyle,
  background: "#162132",
  color: "#f5f7fb",
};

const contentStyle: CSSProperties = {
  width: "min(1400px, 100%)",
  margin: "0 auto",
  paddingTop: "0.7rem",
};
