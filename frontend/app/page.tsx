import Link from "next/link";

const checklist = [
  "Saved universes, screens, and backtests",
  "Reusable templates and run history",
  "Schedules, alerts, and notification tracking",
  "Provider diagnostics and failover",
  "Docker Compose local stack and staging scripts",
  "Django admin, health checks, and metrics",
];

export default function Home() {
  return (
    <main
      style={{
        minHeight: "100vh",
        display: "grid",
        placeItems: "center",
        padding: "2rem",
      }}
    >
      <section
        style={{
          width: "min(840px, 100%)",
          borderRadius: "24px",
          padding: "2rem",
          background: "rgba(255, 255, 255, 0.88)",
          boxShadow: "0 24px 80px rgba(27, 43, 65, 0.12)",
          backdropFilter: "blur(12px)",
        }}
      >
        <p
          style={{
            margin: 0,
            fontSize: "0.85rem",
            letterSpacing: "0.18em",
            textTransform: "uppercase",
            color: "#496280",
          }}
        >
          Current Product
        </p>
        <h1 style={{ marginBottom: "0.75rem", fontSize: "clamp(2rem, 4vw, 3.25rem)" }}>
          Greenblatt Web App
        </h1>
        <p style={{ maxWidth: "54rem", lineHeight: 1.6, color: "#334862" }}>
          The platform now supports end-to-end research workflows: build universes, launch screens,
          backtest the shortlist, save templates, automate schedules, and monitor long-running jobs
          from one authenticated workspace.
        </p>

        <div
          style={{
            display: "grid",
            gap: "1rem",
            gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
            marginTop: "2rem",
          }}
        >
          {checklist.map((item) => (
            <div
              key={item}
              style={{
                padding: "1rem",
                borderRadius: "18px",
                background: "#f7fafc",
                border: "1px solid rgba(73, 98, 128, 0.18)",
              }}
            >
              {item}
            </div>
          ))}
        </div>

        <div style={{ marginTop: "2rem", display: "flex", flexWrap: "wrap", gap: "0.75rem" }}>
          <Link
            href="/login"
            style={{
              display: "inline-flex",
              alignItems: "center",
              justifyContent: "center",
              padding: "0.65rem 0.9rem",
              borderRadius: "999px",
              background: "#162132",
              color: "#f5f7fb",
              textDecoration: "none",
            }}
          >
            Sign in
          </Link>
          <Link
            href="/app"
            style={{
              display: "inline-flex",
              alignItems: "center",
              justifyContent: "center",
              padding: "0.65rem 0.9rem",
              borderRadius: "999px",
              background: "#dde6f0",
              color: "#162132",
              textDecoration: "none",
            }}
          >
            Open dashboard
          </Link>
          <code
            style={{
              padding: "0.65rem 0.9rem",
              borderRadius: "999px",
              background: "#162132",
              color: "#f5f7fb",
            }}
          >
            /health/live/
          </code>
          <code
            style={{
              padding: "0.65rem 0.9rem",
              borderRadius: "999px",
              background: "#dde6f0",
              color: "#162132",
            }}
          >
            /health/ready/
          </code>
        </div>
      </section>
    </main>
  );
}
