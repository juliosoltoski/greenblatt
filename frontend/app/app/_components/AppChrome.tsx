"use client";

import type { CSSProperties, ReactNode } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";

type NavItem = {
  href: string;
  label: string;
};

type NavGroup = {
  label: string;
  items: NavItem[];
};

const navGroups: NavGroup[] = [
  {
    label: "Home",
    items: [{ href: "/app", label: "Dashboard" }],
  },
  {
    label: "Research",
    items: [
      { href: "/app/screens", label: "Screens" },
      { href: "/app/backtests", label: "Backtests" },
    ],
  },
  {
    label: "Library",
    items: [
      { href: "/app/universes", label: "Universes" },
      { href: "/app/templates", label: "Templates" },
      { href: "/app/history", label: "History" },
    ],
  },
  {
    label: "Automation",
    items: [
      { href: "/app/jobs", label: "Jobs" },
      { href: "/app/schedules", label: "Schedules" },
      { href: "/app/alerts", label: "Alerts" },
    ],
  },
  {
    label: "Team",
    items: [{ href: "/app/collaboration", label: "Collaboration" }],
  },
  {
    label: "Settings",
    items: [
      { href: "/app/providers", label: "Data sources" },
      { href: "/app/settings", label: "Settings" },
    ],
  },
];

type AppChromeProps = {
  children: ReactNode;
};

export function AppChrome({ children }: AppChromeProps) {
  const pathname = usePathname();

  return (
    <div style={frameStyle}>
      <header style={chromeStyle}>
        <div style={brandBlockStyle}>
          <Link href="/app" style={brandLinkStyle}>
            Greenblatt
          </Link>
          <p style={brandMetaStyle}>Systematic value research</p>
        </div>

        <nav aria-label="Primary" style={navGridStyle}>
          {navGroups.map((group) => (
            <section key={group.label} style={navGroupStyle}>
              <p style={groupLabelStyle}>{group.label}</p>
              <div style={groupLinksStyle}>
                {group.items.map((item) => {
                  const active = isActivePath(pathname, item.href);
                  const isExternal = item.href.startsWith("http");
                  const sharedProps = {
                    style: active ? activeNavLinkStyle : navLinkStyle,
                    "aria-current": active ? ("page" as const) : undefined,
                  };

                  return isExternal ? (
                    <a key={item.href} href={item.href} {...sharedProps}>
                      {item.label}
                    </a>
                  ) : (
                    <Link key={item.href} href={item.href} {...sharedProps}>
                      {item.label}
                    </Link>
                  );
                })}
              </div>
            </section>
          ))}
        </nav>
      </header>

      <div style={contentStyle}>{children}</div>
    </div>
  );
}

function isActivePath(pathname: string, href: string): boolean {
  if (!href.startsWith("/")) {
    return false;
  }
  if (href === "/app") {
    return pathname === "/app";
  }
  return pathname === href || pathname.startsWith(`${href}/`);
}

const frameStyle: CSSProperties = {
  minHeight: "100vh",
  padding: "0.85rem 0.85rem 1.5rem",
};

const chromeStyle: CSSProperties = {
  width: "min(1400px, 100%)",
  margin: "0 auto",
  padding: "0.8rem 0.95rem",
  borderRadius: "20px",
  background: "rgba(255, 255, 255, 0.82)",
  border: "1px solid rgba(73, 98, 128, 0.14)",
  boxShadow: "0 16px 44px rgba(27, 43, 65, 0.08)",
  backdropFilter: "blur(12px)",
};

const brandBlockStyle: CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  alignItems: "center",
  gap: "0.75rem",
  flexWrap: "wrap",
};

const brandLinkStyle: CSSProperties = {
  fontSize: "1.2rem",
  fontWeight: 700,
  textDecoration: "none",
  letterSpacing: "-0.03em",
};

const brandMetaStyle: CSSProperties = {
  margin: 0,
  color: "#496280",
  fontSize: "0.92rem",
};

const navGridStyle: CSSProperties = {
  display: "flex",
  gap: "0.7rem",
  flexWrap: "wrap",
  marginTop: "0.75rem",
};

const navGroupStyle: CSSProperties = {
  display: "flex",
  gap: "0.45rem",
  alignItems: "center",
  flexWrap: "wrap",
  padding: "0.45rem 0.55rem",
  borderRadius: "16px",
  background: "#f7fafc",
  border: "1px solid rgba(73, 98, 128, 0.12)",
};

const groupLabelStyle: CSSProperties = {
  margin: 0,
  fontSize: "0.72rem",
  letterSpacing: "0.12em",
  textTransform: "uppercase",
  color: "#5c728d",
  padding: "0.28rem 0.45rem",
  borderRadius: "999px",
  background: "#eaf1f8",
};

const groupLinksStyle: CSSProperties = {
  display: "flex",
  gap: "0.4rem",
  flexWrap: "wrap",
};

const navLinkStyle: CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  justifyContent: "center",
  minHeight: "2rem",
  padding: "0.45rem 0.75rem",
  borderRadius: "999px",
  textDecoration: "none",
  background: "#e7eef6",
  color: "#203247",
  fontSize: "0.94rem",
};

const activeNavLinkStyle: CSSProperties = {
  ...navLinkStyle,
  background: "#162132",
  color: "#f5f7fb",
};

const contentStyle: CSSProperties = {
  width: "min(1400px, 100%)",
  margin: "0 auto",
  paddingTop: "0.9rem",
};
