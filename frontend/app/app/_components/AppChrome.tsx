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
    label: "Assets",
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
    label: "Settings",
    items: [{ href: "http://localhost:8000/admin/", label: "Django admin" }],
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
          <p style={brandMetaStyle}>Magic Formula research workspace</p>
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
  padding: "1.25rem 1rem 2rem",
};

const chromeStyle: CSSProperties = {
  width: "min(1400px, 100%)",
  margin: "0 auto",
  padding: "1rem 1.1rem",
  borderRadius: "24px",
  background: "rgba(255, 255, 255, 0.82)",
  border: "1px solid rgba(73, 98, 128, 0.14)",
  boxShadow: "0 18px 60px rgba(27, 43, 65, 0.08)",
  backdropFilter: "blur(12px)",
  position: "sticky",
  top: "1rem",
  zIndex: 10,
};

const brandBlockStyle: CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  alignItems: "baseline",
  gap: "1rem",
  flexWrap: "wrap",
};

const brandLinkStyle: CSSProperties = {
  fontSize: "1.45rem",
  fontWeight: 700,
  textDecoration: "none",
  letterSpacing: "-0.03em",
};

const brandMetaStyle: CSSProperties = {
  margin: 0,
  color: "#496280",
};

const navGridStyle: CSSProperties = {
  display: "grid",
  gap: "0.9rem",
  gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
  marginTop: "1rem",
};

const navGroupStyle: CSSProperties = {
  display: "grid",
  gap: "0.55rem",
  padding: "0.85rem",
  borderRadius: "18px",
  background: "#f7fafc",
  border: "1px solid rgba(73, 98, 128, 0.12)",
};

const groupLabelStyle: CSSProperties = {
  margin: 0,
  fontSize: "0.77rem",
  letterSpacing: "0.12em",
  textTransform: "uppercase",
  color: "#5c728d",
};

const groupLinksStyle: CSSProperties = {
  display: "flex",
  gap: "0.55rem",
  flexWrap: "wrap",
};

const navLinkStyle: CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  justifyContent: "center",
  minHeight: "2.35rem",
  padding: "0.55rem 0.8rem",
  borderRadius: "999px",
  textDecoration: "none",
  background: "#e7eef6",
  color: "#203247",
};

const activeNavLinkStyle: CSSProperties = {
  ...navLinkStyle,
  background: "#162132",
  color: "#f5f7fb",
};

const contentStyle: CSSProperties = {
  width: "min(1400px, 100%)",
  margin: "0 auto",
  paddingTop: "1.25rem",
};
