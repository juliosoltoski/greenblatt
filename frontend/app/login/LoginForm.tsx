"use client";

import { startTransition, useState, type CSSProperties, type FormEvent } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { login } from "@/lib/api";

const accessHighlights = [
  "Open saved universes, templates, and recent research in one place.",
  "Pick up a screen or backtest without rebuilding the full setup.",
  "Keep recurring workflows, alerts, and review history attached to the same workspace.",
];

const supportNotes = ["Private workspace access", "Saved research history", "Reusable workflows"];

export function LoginForm() {
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsSubmitting(true);
    setError(null);
    try {
      await login(username, password);
      startTransition(() => {
        router.replace("/app");
      });
    } catch (loginError) {
      setError(loginError instanceof Error ? loginError.message : "Login failed.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <main style={shellStyle}>
      <section style={layoutStyle}>
        <section style={panelStyle}>
          <p style={eyebrowStyle}>Research workspace</p>
          <h1 style={titleStyle}>Return to your saved process</h1>
          <p style={bodyStyle}>
            Sign in to open your universes, screens, backtests, templates, and recurring research
            workflows.
          </p>

          <form onSubmit={handleSubmit} style={formStyle}>
            <label style={fieldStyle}>
              <span style={labelStyle}>Username</span>
              <input
                type="text"
                name="username"
                autoComplete="username"
                value={username}
                onChange={(event) => setUsername(event.target.value)}
                style={inputStyle}
                required
              />
            </label>
            <label style={fieldStyle}>
              <span style={labelStyle}>Password</span>
              <input
                type="password"
                name="password"
                autoComplete="current-password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                style={inputStyle}
                required
              />
            </label>
            <button type="submit" style={buttonStyle} disabled={isSubmitting}>
              {isSubmitting ? "Signing in..." : "Sign in"}
            </button>
          </form>

          {error ? <p style={errorStyle}>{error}</p> : null}

          <p style={supportTextStyle}>Use your Greenblatt workspace credentials.</p>

          <div style={footerLinksStyle}>
            <Link href="/" style={ghostLinkStyle}>
              Return home
            </Link>
          </div>
        </section>

        <aside style={supportPanelStyle}>
          <div>
            <p style={supportEyebrowStyle}>Private research workspace</p>
            <h2 style={supportTitleStyle}>Pick up where you left off</h2>
            <p style={supportBodyStyle}>
              Your saved research stays organized in one place so the next decision starts with
              context, not reconstruction.
            </p>
          </div>

          <div style={supportListStyle}>
            {accessHighlights.map((item) => (
              <div key={item} style={supportListItemStyle}>
                {item}
              </div>
            ))}
          </div>

          <div style={supportNoteRowStyle}>
            {supportNotes.map((item) => (
              <span key={item} style={supportNoteStyle}>
                {item}
              </span>
            ))}
          </div>
        </aside>
      </section>
    </main>
  );
}

const shellStyle: CSSProperties = {
  minHeight: "100vh",
  padding: "2rem",
};

const layoutStyle: CSSProperties = {
  width: "min(1120px, 100%)",
  margin: "0 auto",
  minHeight: "calc(100vh - 4rem)",
  display: "grid",
  gap: "1rem",
  alignItems: "center",
  gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))",
};

const panelStyle: CSSProperties = {
  borderRadius: "24px",
  padding: "2rem",
  background: "rgba(255, 255, 255, 0.9)",
  boxShadow: "0 24px 80px rgba(27, 43, 65, 0.12)",
  backdropFilter: "blur(12px)",
  display: "grid",
  gap: "0.75rem",
};

const eyebrowStyle: CSSProperties = {
  margin: 0,
  fontSize: "0.85rem",
  letterSpacing: "0.18em",
  textTransform: "uppercase",
  color: "#496280",
};

const titleStyle: CSSProperties = {
  margin: "0.5rem 0 0.75rem",
  fontSize: "clamp(2rem, 4vw, 3rem)",
};

const bodyStyle: CSSProperties = {
  margin: 0,
  lineHeight: 1.6,
  color: "#334862",
};

const formStyle: CSSProperties = {
  display: "grid",
  gap: "1rem",
  marginTop: "1rem",
};

const fieldStyle: CSSProperties = {
  display: "grid",
  gap: "0.45rem",
};

const labelStyle: CSSProperties = {
  fontSize: "0.9rem",
  color: "#496280",
};

const inputStyle: CSSProperties = {
  borderRadius: "14px",
  border: "1px solid rgba(73, 98, 128, 0.25)",
  padding: "0.9rem 1rem",
  fontSize: "1rem",
  background: "#f7fafc",
};

const buttonStyle: CSSProperties = {
  border: 0,
  borderRadius: "999px",
  padding: "0.95rem 1.1rem",
  background: "#162132",
  color: "#f5f7fb",
  cursor: "pointer",
  fontSize: "1rem",
  marginTop: "0.25rem",
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
  margin: 0,
  color: "#9d1b1b",
};

const supportTextStyle: CSSProperties = {
  margin: 0,
  color: "#5c728d",
  lineHeight: 1.55,
};

const footerLinksStyle: CSSProperties = {
  display: "flex",
  flexWrap: "wrap",
  gap: "0.75rem",
};

const supportPanelStyle: CSSProperties = {
  display: "grid",
  gap: "1rem",
  padding: "1.8rem",
  borderRadius: "24px",
  background:
    "linear-gradient(180deg, rgba(248, 251, 255, 0.92) 0%, rgba(238, 244, 251, 0.96) 100%)",
  border: "1px solid rgba(73, 98, 128, 0.14)",
  boxShadow: "0 16px 50px rgba(27, 43, 65, 0.08)",
};

const supportEyebrowStyle: CSSProperties = {
  margin: 0,
  color: "#5c728d",
  fontSize: "0.8rem",
  letterSpacing: "0.14em",
  textTransform: "uppercase",
};

const supportTitleStyle: CSSProperties = {
  margin: "0.45rem 0 0",
  fontSize: "clamp(1.8rem, 3vw, 2.5rem)",
};

const supportBodyStyle: CSSProperties = {
  margin: "0.75rem 0 0",
  color: "#334862",
  lineHeight: 1.65,
};

const supportListStyle: CSSProperties = {
  display: "grid",
  gap: "0.75rem",
};

const supportListItemStyle: CSSProperties = {
  padding: "0.95rem 1rem",
  borderRadius: "16px",
  background: "rgba(255, 255, 255, 0.82)",
  border: "1px solid rgba(73, 98, 128, 0.14)",
  color: "#203247",
  lineHeight: 1.55,
};

const supportNoteRowStyle: CSSProperties = {
  display: "flex",
  flexWrap: "wrap",
  gap: "0.65rem",
};

const supportNoteStyle: CSSProperties = {
  padding: "0.45rem 0.75rem",
  borderRadius: "999px",
  background: "#dde6f0",
  color: "#203247",
  fontSize: "0.92rem",
};
