"use client";

import { startTransition, useState, type CSSProperties, type FormEvent } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { login } from "@/lib/api";

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
      <section style={panelStyle}>
        <p style={eyebrowStyle}>Sign in</p>
        <h1 style={titleStyle}>Access your workspace</h1>
        <p style={bodyStyle}>
          The public landing page introduces the product. This sign-in flow enters the authenticated
          research shell with saved universes, runs, templates, provider diagnostics, and settings.
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

        <div style={{ marginTop: "1.5rem", display: "flex", flexWrap: "wrap", gap: "0.75rem" }}>
          <Link href="/" style={ghostLinkStyle}>
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
  width: "min(520px, 100%)",
  borderRadius: "24px",
  padding: "2rem",
  background: "rgba(255, 255, 255, 0.9)",
  boxShadow: "0 24px 80px rgba(27, 43, 65, 0.12)",
  backdropFilter: "blur(12px)",
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
  lineHeight: 1.6,
  color: "#334862",
};

const formStyle: CSSProperties = {
  display: "grid",
  gap: "1rem",
  marginTop: "1.75rem",
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
  marginTop: "1rem",
  color: "#9d1b1b",
};
