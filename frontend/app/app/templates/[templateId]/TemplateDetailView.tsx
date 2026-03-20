"use client";

import { startTransition, useEffect, useState, type CSSProperties, type FormEvent } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import {
  ApiError,
  getCurrentUser,
  getStrategyTemplate,
  launchStrategyTemplate,
  updateStrategyTemplate,
  type CurrentUser,
  type StrategyTemplate,
} from "@/lib/api";
import { ResourceCollaborationPanel } from "@/app/app/_components/ResourceCollaborationPanel";

type LoadState = "loading" | "ready" | "error";

type TemplateDetailViewProps = {
  templateId: number;
};

export function TemplateDetailView({ templateId }: TemplateDetailViewProps) {
  const router = useRouter();
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [template, setTemplate] = useState<StrategyTemplate | null>(null);
  const [state, setState] = useState<LoadState>("loading");
  const [error, setError] = useState<string | null>(null);
  const [description, setDescription] = useState("");
  const [notes, setNotes] = useState("");
  const [reviewStatus, setReviewStatus] = useState<StrategyTemplate["review_status"]>("draft");
  const [reviewNotes, setReviewNotes] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [isLaunching, setIsLaunching] = useState(false);

  useEffect(() => {
    let active = true;

    async function load() {
      try {
        const [currentUser, templatePayload] = await Promise.all([getCurrentUser(), getStrategyTemplate(templateId)]);
        if (!active) {
          return;
        }
        setUser(currentUser);
        setTemplate(templatePayload);
        setDescription(templatePayload.description);
        setNotes(templatePayload.notes);
        setReviewStatus(templatePayload.review_status);
        setReviewNotes(templatePayload.review_notes);
        setState("ready");
      } catch (loadError) {
        if (!active) {
          return;
        }
        if (loadError instanceof ApiError && loadError.status === 403) {
          startTransition(() => {
            router.replace("/login");
          });
          return;
        }
        setError(loadError instanceof Error ? loadError.message : "Unable to load the template.");
        setState("error");
      }
    }

    void load();
    return () => {
      active = false;
    };
  }, [router, templateId]);

  async function handleSave(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsSaving(true);
    setError(null);
    try {
      const updated = await updateStrategyTemplate(templateId, {
        description,
        notes,
        reviewStatus,
        reviewNotes,
      });
      setTemplate(updated);
      setDescription(updated.description);
      setNotes(updated.notes);
      setReviewStatus(updated.review_status);
      setReviewNotes(updated.review_notes);
    } catch (saveError) {
      setError(formatApiError(saveError, "Unable to update this template."));
    } finally {
      setIsSaving(false);
    }
  }

  async function handleLaunch() {
    setIsLaunching(true);
    setError(null);
    try {
      const launched = await launchStrategyTemplate(templateId);
      startTransition(() => {
        router.push(
          launched.workflow_kind === "screen" ? `/app/screens/${launched.run.id}` : `/app/backtests/${launched.run.id}`,
        );
      });
    } catch (launchError) {
      setError(formatApiError(launchError, "Unable to launch this template."));
    } finally {
      setIsLaunching(false);
    }
  }

  if (state === "loading") {
    return (
      <main style={pageStyle}>
        <section style={panelStyle}>
          <p style={eyebrowStyle}>Template</p>
          <h1 style={titleStyle}>Loading saved workflow</h1>
        </section>
      </main>
    );
  }

  if (state === "error" || template == null || user == null) {
    return (
      <main style={pageStyle}>
        <section style={panelStyle}>
          <p style={eyebrowStyle}>Template</p>
          <h1 style={titleStyle}>Template unavailable</h1>
          <p style={bodyStyle}>{error ?? "Unable to load the requested template."}</p>
        </section>
      </main>
    );
  }

  return (
    <main style={pageStyle}>
      <section style={panelStyle}>
        <div style={headerStyle}>
          <div>
            <p style={eyebrowStyle}>Template</p>
            <h1 style={titleStyle}>{template.name}</h1>
          </div>
          <div style={actionRowStyle}>
            <Link href="/app/templates" style={ghostLinkStyle}>
              All templates
            </Link>
            <Link href={`/app/universes/${template.universe.id}`} style={ghostLinkStyle}>
              Open universe
            </Link>
            <button type="button" style={buttonStyle} onClick={() => void handleLaunch()} disabled={isLaunching}>
              {isLaunching ? "Launching..." : template.workflow_kind === "screen" ? "Run screen" : "Start backtest"}
            </button>
          </div>
        </div>

        <p style={bodyStyle}>
          Review the notes, launch settings, and status behind this reusable workflow. When the
          setup is ready to share, add collaboration context here instead of overloading the main
          template list.
        </p>

        {error ? <p style={errorStyle}>{error}</p> : null}

        <div style={summaryGridStyle}>
          <SummaryCard label="Workflow" value={humanizeLabel(template.workflow_kind)} detail={template.universe.name} />
          <SummaryCard
            label="Review"
            value={humanizeLabel(template.review_status)}
            detail={template.reviewed_at ? new Date(template.reviewed_at).toLocaleString() : "Review still pending"}
          />
          <SummaryCard
            label="Created"
            value={new Date(template.created_at).toLocaleDateString()}
            detail={
              template.last_used_at
                ? `Last used ${new Date(template.last_used_at).toLocaleDateString()}`
                : "Not launched from this template yet"
            }
          />
        </div>

        <form onSubmit={handleSave} style={formStyle}>
          <label style={fieldStyle}>
            <span style={labelStyle}>Description</span>
            <textarea value={description} onChange={(event) => setDescription(event.target.value)} style={textareaStyle} />
          </label>
          <label style={fieldStyle}>
            <span style={labelStyle}>Research notes</span>
            <textarea value={notes} onChange={(event) => setNotes(event.target.value)} style={textareaStyle} />
          </label>
          <div style={inlineGridStyle}>
            <label style={fieldStyle}>
              <span style={labelStyle}>Review status</span>
              <select value={reviewStatus} onChange={(event) => setReviewStatus(event.target.value as StrategyTemplate["review_status"])} style={inputStyle}>
                <option value="draft">Draft</option>
                <option value="in_review">In review</option>
                <option value="approved">Approved</option>
                <option value="changes_requested">Changes requested</option>
              </select>
            </label>
            <label style={fieldStyle}>
              <span style={labelStyle}>Review notes</span>
              <textarea value={reviewNotes} onChange={(event) => setReviewNotes(event.target.value)} style={textareaStyle} />
            </label>
          </div>
          <button type="submit" style={buttonStyle} disabled={isSaving}>
            {isSaving ? "Saving..." : "Save template changes"}
          </button>
        </form>

        <section style={cardStyle}>
          <h2 style={sectionTitleStyle}>Launch settings</h2>
          <p style={bodyStyle}>
            This is the saved configuration that will be used the next time you run the template.
          </p>
          <pre style={preStyle}>{JSON.stringify(template.config, null, 2)}</pre>
        </section>

        <ResourceCollaborationPanel
          workspaceId={user.active_workspace?.id}
          resourceKind="strategy_template"
          resourceId={template.id}
        />
      </section>
    </main>
  );
}

function SummaryCard({ label, value, detail }: { label: string; value: string; detail: string }) {
  return (
    <article style={summaryCardStyle}>
      <p style={summaryLabelStyle}>{label}</p>
      <strong>{value}</strong>
      <p style={summaryDetailStyle}>{detail}</p>
    </article>
  );
}

function formatApiError(error: unknown, fallback: string): string {
  if (error instanceof ApiError) {
    return error.message;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return fallback;
}

function humanizeLabel(value: string): string {
  return value
    .split(/[_\s]+/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

const pageStyle: CSSProperties = {
  display: "grid",
  gap: "1rem",
};

const panelStyle: CSSProperties = {
  display: "grid",
  gap: "1rem",
  padding: "1.2rem",
  borderRadius: "28px",
  background: "#ffffff",
  border: "1px solid rgba(73, 98, 128, 0.12)",
};

const headerStyle: CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  gap: "1rem",
  alignItems: "center",
  flexWrap: "wrap",
};

const actionRowStyle: CSSProperties = {
  display: "flex",
  gap: "0.75rem",
  flexWrap: "wrap",
};

const eyebrowStyle: CSSProperties = {
  margin: 0,
  color: "#8a5a14",
  textTransform: "uppercase",
  letterSpacing: "0.12em",
  fontSize: "0.76rem",
};

const titleStyle: CSSProperties = {
  margin: "0.25rem 0 0",
  fontSize: "1.9rem",
};

const bodyStyle: CSSProperties = {
  margin: 0,
  color: "#496280",
  lineHeight: 1.6,
};

const errorStyle: CSSProperties = {
  margin: 0,
  padding: "0.75rem 0.95rem",
  borderRadius: "16px",
  background: "#fff2f2",
  color: "#a12f2f",
};

const ghostLinkStyle: CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  justifyContent: "center",
  minHeight: "2.6rem",
  padding: "0 0.9rem",
  borderRadius: "999px",
  border: "1px solid rgba(73, 98, 128, 0.18)",
  textDecoration: "none",
};

const buttonStyle: CSSProperties = {
  minHeight: "2.8rem",
  borderRadius: "999px",
  border: "none",
  background: "#162132",
  color: "#f5f7fb",
  padding: "0 1rem",
  fontWeight: 600,
  cursor: "pointer",
};

const summaryGridStyle: CSSProperties = {
  display: "grid",
  gap: "0.9rem",
  gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
};

const summaryCardStyle: CSSProperties = {
  display: "grid",
  gap: "0.35rem",
  padding: "0.95rem",
  borderRadius: "20px",
  background: "#f8fbff",
  border: "1px solid rgba(73, 98, 128, 0.12)",
};

const summaryLabelStyle: CSSProperties = {
  margin: 0,
  color: "#637990",
  fontSize: "0.78rem",
  textTransform: "uppercase",
  letterSpacing: "0.08em",
};

const summaryDetailStyle: CSSProperties = {
  margin: 0,
  color: "#637990",
  fontSize: "0.88rem",
};

const formStyle: CSSProperties = {
  display: "grid",
  gap: "0.9rem",
};

const inlineGridStyle: CSSProperties = {
  display: "grid",
  gap: "0.9rem",
  gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))",
};

const fieldStyle: CSSProperties = {
  display: "grid",
  gap: "0.4rem",
};

const labelStyle: CSSProperties = {
  fontWeight: 600,
};

const textareaStyle: CSSProperties = {
  minHeight: "120px",
  borderRadius: "16px",
  border: "1px solid rgba(73, 98, 128, 0.18)",
  padding: "0.85rem 0.95rem",
  resize: "vertical",
  background: "#ffffff",
};

const inputStyle: CSSProperties = {
  minHeight: "2.9rem",
  borderRadius: "14px",
  border: "1px solid rgba(73, 98, 128, 0.18)",
  padding: "0 0.9rem",
  background: "#ffffff",
};

const cardStyle: CSSProperties = {
  display: "grid",
  gap: "0.8rem",
  padding: "1rem",
  borderRadius: "20px",
  background: "#f8fbff",
  border: "1px solid rgba(73, 98, 128, 0.12)",
};

const sectionTitleStyle: CSSProperties = {
  margin: 0,
};

const preStyle: CSSProperties = {
  margin: 0,
  padding: "1rem",
  borderRadius: "18px",
  background: "#162132",
  color: "#f5f7fb",
  overflowX: "auto",
  fontSize: "0.88rem",
};
