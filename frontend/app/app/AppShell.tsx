"use client";

import { startTransition, useEffect, useState, type CSSProperties } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { getCurrentUser, logout, type CurrentUser } from "@/lib/api";

type LoadState = "loading" | "ready" | "error";

export function AppShell() {
  const router = useRouter();
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [state, setState] = useState<LoadState>("loading");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;

    void getCurrentUser()
      .then((payload) => {
        if (!active) {
          return;
        }
        setUser(payload);
        setState("ready");
      })
      .catch(() => {
        if (!active) {
          return;
        }
        startTransition(() => {
          router.replace("/login");
        });
      });

    return () => {
      active = false;
    };
  }, [router]);

  async function handleLogout() {
    setError(null);
    try {
      await logout();
      startTransition(() => {
        router.replace("/login");
      });
    } catch (logoutError) {
      setError(logoutError instanceof Error ? logoutError.message : "Logout failed.");
    }
  }

  if (state === "loading" || user === null) {
    return (
      <main style={shellStyle}>
        <section style={panelStyle}>
          <p style={eyebrowStyle}>Protected App</p>
          <h1 style={titleStyle}>Checking your session</h1>
          <p style={bodyStyle}>The app shell is verifying your authenticated workspace context.</p>
        </section>
      </main>
    );
  }

  return (
    <main style={shellStyle}>
      <section style={panelStyle}>
        <div style={headerRowStyle}>
          <div>
            <p style={eyebrowStyle}>Authenticated Session</p>
            <h1 style={titleStyle}>Welcome back, {user.display_name}</h1>
          </div>
          <button type="button" style={secondaryButtonStyle} onClick={handleLogout}>
            Log out
          </button>
        </div>

        <p style={bodyStyle}>
          Your protected shell is active. Universes, jobs, screens, backtests, templates, and run
          history now work together, so saved research inputs can be repeated and compared instead
          of rebuilt by hand.
        </p>

        {error ? <p style={errorStyle}>{error}</p> : null}

        <div style={gridStyle}>
          <div style={cardStyle}>
            <p style={cardLabelStyle}>Active workspace</p>
            <h2 style={cardTitleStyle}>{user.active_workspace?.name ?? "No workspace"}</h2>
            <p style={metaStyle}>
              Role: <strong>{user.active_workspace?.role ?? "n/a"}</strong>
            </p>
            <p style={metaStyle}>
              Slug: <code>{user.active_workspace?.slug ?? "n/a"}</code>
            </p>
          </div>

          <div style={cardStyle}>
            <p style={cardLabelStyle}>Account</p>
            <h2 style={cardTitleStyle}>{user.username}</h2>
            <p style={metaStyle}>{user.email || "No email configured"}</p>
            <p style={metaStyle}>Staff access: {user.is_staff ? "yes" : "no"}</p>
          </div>

          <div style={cardStyle}>
            <p style={cardLabelStyle}>Research setup</p>
            <h2 style={cardTitleStyle}>Universes</h2>
            <p style={metaStyle}>
              Save manual lists, built-in profiles, or uploaded ticker files before launching work.
            </p>
            <Link href="/app/universes" style={{ ...linkButtonStyle, marginTop: "0.9rem" }}>
              Open universe manager
            </Link>
          </div>

          <div style={cardStyle}>
            <p style={cardLabelStyle}>Research workflow</p>
            <h2 style={cardTitleStyle}>Screens</h2>
            <p style={metaStyle}>
              Launch Magic Formula ranking runs from saved universes and review persisted results.
            </p>
            <Link href="/app/screens" style={{ ...linkButtonStyle, marginTop: "0.9rem" }}>
              Open screens
            </Link>
          </div>

          <div style={cardStyle}>
            <p style={cardLabelStyle}>Portfolio workflow</p>
            <h2 style={cardTitleStyle}>Backtests</h2>
            <p style={metaStyle}>
              Run persisted historical simulations and inspect curves, trades, and final holdings.
            </p>
            <Link href="/app/backtests" style={{ ...linkButtonStyle, marginTop: "0.9rem" }}>
              Open backtests
            </Link>
          </div>

          <div style={cardStyle}>
            <p style={cardLabelStyle}>Async pipeline</p>
            <h2 style={cardTitleStyle}>Jobs</h2>
            <p style={metaStyle}>
              Inspect the shared job queue, including smoke tests, screens, and backtests.
            </p>
            <Link href="/app/jobs" style={{ ...linkButtonStyle, marginTop: "0.9rem" }}>
              Open jobs
            </Link>
          </div>

          <div style={cardStyle}>
            <p style={cardLabelStyle}>Reusable workflows</p>
            <h2 style={cardTitleStyle}>Templates</h2>
            <p style={metaStyle}>
              Save prior runs as reusable templates, then relaunch or reopen them as drafts.
            </p>
            <Link href="/app/templates" style={{ ...linkButtonStyle, marginTop: "0.9rem" }}>
              Open templates
            </Link>
          </div>

          <div style={cardStyle}>
            <p style={cardLabelStyle}>Research archive</p>
            <h2 style={cardTitleStyle}>History</h2>
            <p style={metaStyle}>
              Browse prior screen and backtest runs, compare two runs, and save useful ones as templates.
            </p>
            <Link href="/app/history" style={{ ...linkButtonStyle, marginTop: "0.9rem" }}>
              Open history
            </Link>
          </div>

          <div style={cardStyle}>
            <p style={cardLabelStyle}>Recurring automation</p>
            <h2 style={cardTitleStyle}>Schedules</h2>
            <p style={metaStyle}>
              Launch saved templates on a recurring beat-backed cadence and trigger them manually when needed.
            </p>
            <Link href="/app/schedules" style={{ ...linkButtonStyle, marginTop: "0.9rem" }}>
              Open schedules
            </Link>
          </div>

          <div style={cardStyle}>
            <p style={cardLabelStyle}>Proactive monitoring</p>
            <h2 style={cardTitleStyle}>Alerts</h2>
            <p style={metaStyle}>
              Create email alerts for workflow completion, failures, and top-N ticker appearances.
            </p>
            <Link href="/app/alerts" style={{ ...linkButtonStyle, marginTop: "0.9rem" }}>
              Open alerts
            </Link>
          </div>
        </div>

        <div style={{ marginTop: "2rem" }}>
          <p style={cardLabelStyle}>Workspace memberships</p>
          <div style={{ display: "grid", gap: "0.75rem", marginTop: "0.75rem" }}>
            {user.workspaces.map((workspace) => (
              <div key={workspace.id} style={workspaceRowStyle}>
                <div>
                  <strong>{workspace.name}</strong>
                  <div style={metaStyle}>
                    <code>{workspace.slug}</code> - {workspace.plan_type} - {workspace.timezone}
                  </div>
                </div>
                <span style={roleBadgeStyle}>{workspace.role}</span>
              </div>
            ))}
          </div>
        </div>

        <div style={{ marginTop: "2rem", display: "flex", gap: "0.75rem", flexWrap: "wrap" }}>
          <Link href="/" style={linkButtonStyle}>
            Return home
          </Link>
          <a href="http://localhost:8000/admin/" style={ghostLinkStyle}>
            Django admin
          </a>
        </div>
      </section>
    </main>
  );
}

const shellStyle: CSSProperties = {
  minHeight: "100vh",
  display: "grid",
  placeItems: "center",
  padding: "2rem",
};

const panelStyle: CSSProperties = {
  width: "min(980px, 100%)",
  borderRadius: "24px",
  padding: "2rem",
  background: "rgba(255, 255, 255, 0.9)",
  boxShadow: "0 24px 80px rgba(27, 43, 65, 0.12)",
  backdropFilter: "blur(12px)",
};

const headerRowStyle: CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  alignItems: "flex-start",
  gap: "1rem",
  flexWrap: "wrap",
};

const eyebrowStyle: CSSProperties = {
  margin: 0,
  fontSize: "0.85rem",
  letterSpacing: "0.18em",
  textTransform: "uppercase",
  color: "#496280",
};

const titleStyle: CSSProperties = {
  margin: "0.5rem 0 0",
  fontSize: "clamp(2rem, 4vw, 3rem)",
};

const bodyStyle: CSSProperties = {
  maxWidth: "54rem",
  lineHeight: 1.6,
  color: "#334862",
};

const gridStyle: CSSProperties = {
  display: "grid",
  gap: "1rem",
  gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))",
  marginTop: "1.5rem",
};

const cardStyle: CSSProperties = {
  padding: "1.25rem",
  borderRadius: "18px",
  background: "#f7fafc",
  border: "1px solid rgba(73, 98, 128, 0.18)",
};

const cardLabelStyle: CSSProperties = {
  margin: 0,
  fontSize: "0.82rem",
  letterSpacing: "0.12em",
  textTransform: "uppercase",
  color: "#5c728d",
};

const cardTitleStyle: CSSProperties = {
  margin: "0.5rem 0",
  fontSize: "1.4rem",
};

const metaStyle: CSSProperties = {
  margin: "0.2rem 0",
  color: "#496280",
  lineHeight: 1.5,
};

const workspaceRowStyle: CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  alignItems: "center",
  gap: "1rem",
  padding: "1rem",
  borderRadius: "16px",
  background: "#f7fafc",
  border: "1px solid rgba(73, 98, 128, 0.18)",
};

const roleBadgeStyle: CSSProperties = {
  padding: "0.45rem 0.75rem",
  borderRadius: "999px",
  background: "#dde6f0",
  textTransform: "capitalize",
};

const secondaryButtonStyle: CSSProperties = {
  border: 0,
  borderRadius: "999px",
  padding: "0.75rem 1rem",
  background: "#162132",
  color: "#f5f7fb",
  cursor: "pointer",
};

const linkButtonStyle: CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  justifyContent: "center",
  borderRadius: "999px",
  padding: "0.8rem 1rem",
  background: "#162132",
  color: "#f5f7fb",
  textDecoration: "none",
};

const ghostLinkStyle: CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  justifyContent: "center",
  borderRadius: "999px",
  padding: "0.8rem 1rem",
  background: "#dde6f0",
  color: "#162132",
  textDecoration: "none",
};

const errorStyle: CSSProperties = {
  color: "#9d1b1b",
  marginTop: "1rem",
};
