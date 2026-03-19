import Link from "next/link";

const featureCards = [
  {
    title: "Find better candidates",
    body: "Build investable universes, rank opportunities with the Magic Formula, and move from broad market scans to a focused shortlist.",
  },
  {
    title: "Pressure-test the idea",
    body: "Backtest shortlisted names, compare runs over time, and turn one-off experiments into repeatable research workflows.",
  },
  {
    title: "Keep research organized",
    body: "Save templates, review past work, and schedule recurring runs so your process stays consistent instead of living in scattered exports.",
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
            Systematic value research
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
                A clearer home for disciplined stock research
              </h1>
              <p style={{ maxWidth: "44rem", lineHeight: 1.7, color: "#334862", marginTop: "1rem" }}>
                Greenblatt brings value screening, backtesting, saved templates, and recurring
                research workflows into one workspace. Build a universe, rank candidates, test the
                shortlist across history, and keep the process reusable.
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
                  Open workspace
                </Link>
                <a
                  href="#workflows"
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
                  See workflow
                </a>
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
                  Platform highlights
                </p>
                <h2 style={{ margin: "0.35rem 0 0", fontSize: "1.45rem" }}>What you can already do</h2>
              </div>
              <div style={{ display: "grid", gap: "0.75rem" }}>
                {[
                  "Create saved universes and reusable templates",
                  "Run screens and backtests with persisted results",
                  "Compare history and keep a structured research trail",
                  "Schedule recurring workflows and delivery alerts",
                  "Collaborate inside a shared research workspace",
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

        <div id="workflows" style={{ marginTop: "2rem", display: "flex", flexWrap: "wrap", gap: "0.75rem" }}>
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
            <h2 style={{ marginTop: 0 }}>Private research workspace</h2>
            <p style={{ color: "#334862", lineHeight: 1.65 }}>
              Saved research, recurring workflows, and collaboration stay inside the signed-in
              workspace so your process remains private and organized.
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
            <h2 style={{ marginTop: 0 }}>Research-first by design</h2>
            <p style={{ color: "#334862", lineHeight: 1.65 }}>
              Greenblatt is built for idea generation, review, and repeatable research workflows.
              Trade execution stays outside the product.
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
            <h2 style={{ marginTop: 0 }}>Built for repeatable work</h2>
            <p style={{ color: "#334862", lineHeight: 1.65, marginBottom: 0 }}>
              The platform is designed to turn one strong research pass into a reusable template,
              a scheduled workflow, and a cleaner historical record.
            </p>
          </section>
        </div>
      </section>
    </main>
  );
}
