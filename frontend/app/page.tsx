import type { CSSProperties } from "react";
import Link from "next/link";

const workflowSteps = [
  {
    title: "Build the right starting list",
    body: "Start from a broad market universe, a sector watchlist, or your own file so every screen begins with the opportunity set you actually want to study.",
  },
  {
    title: "Rank and test ideas quickly",
    body: "Run screens, review the shortlist, and pressure-test the setup across history before the idea earns a permanent place in your process.",
  },
  {
    title: "Keep the process reusable",
    body: "Save templates, revisit prior runs, and schedule recurring workflows so strong research habits survive beyond a single session.",
  },
];

const platformPillars = [
  {
    title: "Private research workspace",
    body: "Saved universes, templates, and run history stay tied together instead of disappearing into folders and exports.",
  },
  {
    title: "Clear historical record",
    body: "Review past screens and backtests with the context that produced them, not just the final output.",
  },
  {
    title: "Built for repeatable work",
    body: "Turn a strong setup into a reusable template and bring the same process back whenever the market changes.",
  },
];

const workspaceHighlights = [
  "Build or upload universes that fit your research style.",
  "Run screens and backtests without rebuilding the same setup every time.",
  "Save the workflows worth repeating and keep a dated trail of prior work.",
];

export default function Home() {
  return (
    <main style={pageStyle}>
      <section style={heroSectionStyle}>
        <div style={heroGridStyle}>
          <div style={heroCopyStyle}>
            <p style={eyebrowStyle}>Research Platform</p>
            <h1 style={titleStyle}>
              Screen stronger ideas. Test them across history. Keep the process repeatable.
            </h1>
            <p style={bodyStyle}>
              Greenblatt gives disciplined investors one workspace for universes, rankings,
              backtests, templates, and recurring research workflows. Move from a broad market
              scan to a reusable process without losing the context behind each decision.
            </p>
            <div style={actionRowStyle}>
              <Link href="/login" style={primaryLinkStyle}>
                Sign in
              </Link>
              <Link href="/app" style={secondaryLinkStyle}>
                Open workspace
              </Link>
              <a href="#workflow" style={tertiaryLinkStyle}>
                See workflow
              </a>
            </div>
            <div style={trustStripStyle}>
              {["Saved universes", "Reusable templates", "Repeatable backtests"].map((item) => (
                <div key={item} style={trustPillStyle}>
                  {item}
                </div>
              ))}
            </div>
          </div>

          <aside style={heroAsideStyle}>
            <div>
              <p style={cardEyebrowStyle}>Inside the workspace</p>
              <h2 style={asideTitleStyle}>A cleaner research routine</h2>
              <p style={asideBodyStyle}>
                Keep your starting lists, run history, and reusable setups connected so every new
                decision starts with context instead of a blank page.
              </p>
            </div>
            <div style={asideListStyle}>
              {workspaceHighlights.map((item) => (
                <div key={item} style={asideListItemStyle}>
                  {item}
                </div>
              ))}
            </div>
            <div style={asideFooterStyle}>Built for research discipline, not trade execution.</div>
          </aside>
        </div>
      </section>

      <section id="workflow" style={sectionStyle}>
        <div style={sectionHeaderStyle}>
          <p style={sectionEyebrowStyle}>Workflow</p>
          <h2 style={sectionTitleStyle}>From first pass to reusable process</h2>
          <p style={sectionBodyStyle}>
            Each step is designed to help you go from a broad market idea to a structured workflow
            you can review, reuse, and run again.
          </p>
        </div>
        <div style={cardGridStyle}>
          {workflowSteps.map((item) => (
            <article key={item.title} style={sectionCardStyle}>
              <h3 style={cardTitleStyle}>{item.title}</h3>
              <p style={cardBodyStyle}>{item.body}</p>
            </article>
          ))}
        </div>
      </section>

      <section style={sectionStyle}>
        <div style={cardGridStyle}>
          {platformPillars.map((item) => (
            <article key={item.title} style={supportCardStyle}>
              <h2 style={supportCardTitleStyle}>{item.title}</h2>
              <p style={cardBodyStyle}>{item.body}</p>
            </article>
          ))}
        </div>
      </section>
    </main>
  );
}

const pageStyle: CSSProperties = {
  minHeight: "100vh",
  padding: "1.5rem",
};

const heroSectionStyle: CSSProperties = {
  width: "min(1180px, 100%)",
  margin: "0 auto",
  padding: "2.1rem",
  borderRadius: "32px",
  background:
    "linear-gradient(135deg, rgba(255,255,255,0.95) 0%, rgba(244,248,252,0.98) 45%, rgba(225,236,247,0.98) 100%)",
  boxShadow: "0 24px 80px rgba(27, 43, 65, 0.12)",
  backdropFilter: "blur(12px)",
};

const heroGridStyle: CSSProperties = {
  display: "grid",
  gap: "1rem",
  gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))",
  alignItems: "start",
};

const heroCopyStyle: CSSProperties = {
  display: "grid",
  gap: "1rem",
};

const eyebrowStyle: CSSProperties = {
  margin: 0,
  fontSize: "0.85rem",
  letterSpacing: "0.18em",
  textTransform: "uppercase" as const,
  color: "#496280",
};

const titleStyle: CSSProperties = {
  margin: 0,
  fontSize: "clamp(2.6rem, 5vw, 4.5rem)",
  lineHeight: 0.95,
  letterSpacing: "-0.04em",
};

const bodyStyle: CSSProperties = {
  maxWidth: "48rem",
  margin: 0,
  lineHeight: 1.7,
  color: "#334862",
  fontSize: "1.02rem",
};

const actionRowStyle: CSSProperties = {
  display: "flex",
  flexWrap: "wrap" as const,
  gap: "0.75rem",
};

const primaryLinkStyle: CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  justifyContent: "center",
  padding: "0.85rem 1.1rem",
  borderRadius: "999px",
  background: "#162132",
  color: "#f5f7fb",
  textDecoration: "none",
};

const secondaryLinkStyle: CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  justifyContent: "center",
  padding: "0.85rem 1.1rem",
  borderRadius: "999px",
  background: "#dde6f0",
  color: "#162132",
  textDecoration: "none",
};

const tertiaryLinkStyle: CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  justifyContent: "center",
  padding: "0.85rem 1.1rem",
  borderRadius: "999px",
  background: "#eef4fa",
  color: "#162132",
  textDecoration: "none",
};

const trustStripStyle: CSSProperties = {
  display: "grid",
  gap: "0.75rem",
  gridTemplateColumns: "repeat(auto-fit, minmax(170px, 1fr))",
  marginTop: "0.25rem",
};

const trustPillStyle: CSSProperties = {
  padding: "0.95rem 1rem",
  borderRadius: "18px",
  background: "rgba(255,255,255,0.82)",
  border: "1px solid rgba(73, 98, 128, 0.16)",
  color: "#203247",
};

const heroAsideStyle: CSSProperties = {
  display: "grid",
  gap: "1rem",
  padding: "1.15rem",
  borderRadius: "24px",
  background: "rgba(255,255,255,0.82)",
  border: "1px solid rgba(73, 98, 128, 0.14)",
};

const cardEyebrowStyle: CSSProperties = {
  margin: 0,
  color: "#5c728d",
  textTransform: "uppercase" as const,
  letterSpacing: "0.12em",
  fontSize: "0.78rem",
};

const asideTitleStyle: CSSProperties = {
  margin: "0.4rem 0 0",
  fontSize: "1.6rem",
};

const asideBodyStyle: CSSProperties = {
  margin: "0.75rem 0 0",
  color: "#334862",
  lineHeight: 1.65,
};

const asideListStyle: CSSProperties = {
  display: "grid",
  gap: "0.75rem",
};

const asideListItemStyle: CSSProperties = {
  padding: "0.9rem 1rem",
  borderRadius: "16px",
  background: "#f7fafc",
  border: "1px solid rgba(73, 98, 128, 0.14)",
  lineHeight: 1.55,
  color: "#203247",
};

const asideFooterStyle: CSSProperties = {
  padding: "0.85rem 0.95rem",
  borderRadius: "16px",
  background: "linear-gradient(180deg, #f8fbff 0%, #eef4fb 100%)",
  color: "#334862",
  lineHeight: 1.55,
};

const sectionStyle: CSSProperties = {
  width: "min(1180px, 100%)",
  margin: "0 auto",
  paddingTop: "1.35rem",
};

const sectionHeaderStyle: CSSProperties = {
  display: "grid",
  gap: "0.4rem",
  marginBottom: "1rem",
};

const sectionEyebrowStyle: CSSProperties = {
  margin: 0,
  color: "#5c728d",
  textTransform: "uppercase" as const,
  letterSpacing: "0.14em",
  fontSize: "0.78rem",
};

const sectionTitleStyle: CSSProperties = {
  margin: 0,
  fontSize: "2rem",
};

const sectionBodyStyle: CSSProperties = {
  margin: 0,
  maxWidth: "42rem",
  color: "#496280",
  lineHeight: 1.65,
};

const cardGridStyle: CSSProperties = {
  display: "grid",
  gap: "1rem",
  gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))",
};

const sectionCardStyle: CSSProperties = {
  padding: "1.2rem",
  borderRadius: "22px",
  background: "rgba(255,255,255,0.88)",
  border: "1px solid rgba(73, 98, 128, 0.14)",
  boxShadow: "0 16px 50px rgba(27, 43, 65, 0.08)",
};

const supportCardStyle: CSSProperties = {
  padding: "1.2rem",
  borderRadius: "22px",
  background: "rgba(255,255,255,0.88)",
  border: "1px solid rgba(73, 98, 128, 0.14)",
};

const cardTitleStyle: CSSProperties = {
  marginTop: 0,
  marginBottom: "0.65rem",
  fontSize: "1.3rem",
};

const supportCardTitleStyle: CSSProperties = {
  marginTop: 0,
  marginBottom: "0.65rem",
  fontSize: "1.35rem",
};

const cardBodyStyle: CSSProperties = {
  margin: 0,
  color: "#334862",
  lineHeight: 1.65,
};
