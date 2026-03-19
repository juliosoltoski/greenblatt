import Link from "next/link";

const featureCards = [
  {
    title: "Research flows",
    body: "Build universes, run Magic Formula screens, compare history, and backtest shortlisted ideas without leaving the app shell.",
  },
  {
    title: "Operations visibility",
    body: "Inspect providers, queue pressure, health checks, metrics, alerts, schedules, and job timelines from one workspace.",
  },
  {
    title: "Reusable process",
    body: "Promote good runs into templates, automate them on schedules, and keep a structured research record instead of a raw export trail.",
  },
];

export default function Home() {
  return (
    <main
      style={{
        minHeight: "100vh",
        padding: "2rem",
      }}
    >
      <section
        style={{
          width: "min(1180px, 100%)",
          margin: "0 auto",
          display: "grid",
          gap: "1.25rem",
        }}
      >
        <div
          style={{
            borderRadius: "30px",
            padding: "2.25rem",
            background:
              "linear-gradient(135deg, rgba(255,255,255,0.92) 0%, rgba(244,248,252,0.96) 45%, rgba(225,236,247,0.96) 100%)",
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
            Public Surface
          </p>
          <div
            style={{
              display: "grid",
              gap: "1.25rem",
              gridTemplateColumns: "minmax(0, 1.35fr) minmax(280px, 0.85fr)",
              alignItems: "start",
              marginTop: "1rem",
            }}
          >
            <div>
              <h1 style={{ margin: 0, fontSize: "clamp(2.4rem, 5vw, 4.35rem)", lineHeight: 0.96 }}>
                Research workflows for a deployable Greenblatt stack
              </h1>
              <p style={{ maxWidth: "44rem", lineHeight: 1.7, color: "#334862", marginTop: "1rem" }}>
                Greenblatt is now a full web product: saved universes, async screens and backtests,
                templates, schedules, alerts, collaboration, provider diagnostics, and operator tooling.
                The public site introduces the product; the authenticated app is where the research runs.
              </p>
              <div style={{ marginTop: "1.4rem", display: "flex", flexWrap: "wrap", gap: "0.75rem" }}>
                <Link
                  href="/login"
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    justifyContent: "center",
                    padding: "0.8rem 1rem",
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
                    padding: "0.8rem 1rem",
                    borderRadius: "999px",
                    background: "#dde6f0",
                    color: "#162132",
                    textDecoration: "none",
                  }}
                >
                  Open app
                </Link>
                <Link
                  href="/app/providers"
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    justifyContent: "center",
                    padding: "0.8rem 1rem",
                    borderRadius: "999px",
                    background: "#eef4fa",
                    color: "#162132",
                    textDecoration: "none",
                  }}
                >
                  Provider diagnostics
                </Link>
              </div>
            </div>

            <aside
              style={{
                display: "grid",
                gap: "0.9rem",
                padding: "1rem",
                borderRadius: "22px",
                background: "rgba(255,255,255,0.82)",
                border: "1px solid rgba(73, 98, 128, 0.14)",
              }}
            >
              <div>
                <p style={{ margin: 0, color: "#5c728d", textTransform: "uppercase", letterSpacing: "0.1em", fontSize: "0.8rem" }}>
                  Live shape
                </p>
                <h2 style={{ margin: "0.35rem 0 0", fontSize: "1.45rem" }}>What the product already supports</h2>
              </div>
              <div style={{ display: "grid", gap: "0.75rem" }}>
                {[
                  "Saved universes, screens, and backtests",
                  "Templates, history, and comparison workflows",
                  "Schedules, alerts, notifications, and collaboration",
                  "Provider diagnostics, cache warm jobs, and failover",
                  "Health checks, metrics, admin, and staging scripts",
                ].map((item) => (
                  <div
                    key={item}
                    style={{
                      padding: "0.85rem 0.95rem",
                      borderRadius: "14px",
                      background: "#f7fafc",
                      border: "1px solid rgba(73, 98, 128, 0.14)",
                    }}
                  >
                    {item}
                  </div>
                ))}
              </div>
            </aside>
          </div>
        </div>

        <div style={{ marginTop: "2rem", display: "flex", flexWrap: "wrap", gap: "0.75rem" }}>
          {featureCards.map((item) => (
            <article
              key={item.title}
              style={{
                padding: "1.15rem",
                borderRadius: "22px",
                background: "rgba(255,255,255,0.88)",
                border: "1px solid rgba(73, 98, 128, 0.14)",
                boxShadow: "0 16px 50px rgba(27, 43, 65, 0.08)",
                flex: "1 1 260px",
              }}
            >
              <h2 style={{ marginTop: 0 }}>{item.title}</h2>
              <p style={{ marginBottom: 0, color: "#334862", lineHeight: 1.65 }}>{item.body}</p>
            </article>
          ))}
        </div>

        <div
          style={{
            display: "grid",
            gap: "1rem",
            gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
          }}
        >
          <section
            style={{
              padding: "1.15rem",
              borderRadius: "22px",
              background: "rgba(255,255,255,0.88)",
              border: "1px solid rgba(73, 98, 128, 0.14)",
            }}
          >
            <h2 style={{ marginTop: 0 }}>Public vs authenticated surface</h2>
            <p style={{ color: "#334862", lineHeight: 1.65 }}>
              The landing page is intentionally public-facing. Research execution, saved data, and
              collaboration stay inside the authenticated `/app` shell.
            </p>
          </section>
          <section
            style={{
              padding: "1.15rem",
              borderRadius: "22px",
              background: "rgba(255,255,255,0.88)",
              border: "1px solid rgba(73, 98, 128, 0.14)",
            }}
          >
            <h2 style={{ marginTop: 0 }}>Research-only note</h2>
            <p style={{ color: "#334862", lineHeight: 1.65 }}>
              The app supports research workflows and operational visibility. Live trading,
              commercial billing, and public cloud deployment planning remain later work.
            </p>
          </section>
          <section
            style={{
              padding: "1.15rem",
              borderRadius: "22px",
              background: "rgba(255,255,255,0.88)",
              border: "1px solid rgba(73, 98, 128, 0.14)",
            }}
          >
            <h2 style={{ marginTop: 0 }}>Operational checks</h2>
            <div style={{ display: "flex", flexWrap: "wrap", gap: "0.6rem" }}>
              <code
                style={{
                  padding: "0.55rem 0.75rem",
                  borderRadius: "999px",
                  background: "#162132",
                  color: "#f5f7fb",
                }}
              >
                /health/live/
              </code>
              <code
                style={{
                  padding: "0.55rem 0.75rem",
                  borderRadius: "999px",
                  background: "#dde6f0",
                  color: "#162132",
                }}
              >
                /health/ready/
              </code>
            </div>
          </section>
        </div>
      </section>
    </main>
  );
}
