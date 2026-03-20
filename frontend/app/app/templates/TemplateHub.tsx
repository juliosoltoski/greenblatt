"use client";

import { startTransition, useEffect, useState, type CSSProperties } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import {
  ApiError,
  deleteStrategyTemplate,
  getCurrentUser,
  launchStrategyTemplate,
  listStrategyTemplates,
  updateStrategyTemplate,
  type CurrentUser,
  type StrategyTemplate,
} from "@/lib/api";
import { readViewPreference, writeViewPreference } from "@/lib/viewPreferences";

type LoadState = "loading" | "ready" | "error";
type WorkflowFilter = "all" | "screen" | "backtest";

export function TemplateHub() {
  const router = useRouter();
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [templates, setTemplates] = useState<StrategyTemplate[]>([]);
  const [workflowFilter, setWorkflowFilter] = useState<WorkflowFilter>("all");
  const [starredOnly, setStarredOnly] = useState(false);
  const [state, setState] = useState<LoadState>("loading");
  const [error, setError] = useState<string | null>(null);
  const [isLaunchingId, setIsLaunchingId] = useState<number | null>(null);
  const hasActiveFilters = workflowFilter !== "all" || starredOnly;

  useEffect(() => {
    const preference = readViewPreference<{ workflowFilter: WorkflowFilter; starredOnly: boolean }>("template-hub", {
      workflowFilter: "all",
      starredOnly: false,
    });
    setWorkflowFilter(preference.workflowFilter);
    setStarredOnly(preference.starredOnly);
  }, []);

  useEffect(() => {
    writeViewPreference("template-hub", { workflowFilter, starredOnly });
  }, [starredOnly, workflowFilter]);

  useEffect(() => {
    let active = true;

    async function load() {
      try {
        const currentUser = await getCurrentUser();
        const payload = await listStrategyTemplates({
          workspaceId: currentUser.active_workspace?.id,
          workflowKind: workflowFilter === "all" ? undefined : workflowFilter,
          starredOnly,
          pageSize: 50,
        });
        if (!active) {
          return;
        }
        setUser(currentUser);
        setTemplates(payload.results);
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
        setError(loadError instanceof Error ? loadError.message : "Unable to load templates.");
        setState("error");
      }
    }

    void load();

    return () => {
      active = false;
    };
  }, [router, starredOnly, workflowFilter]);

  async function refreshTemplates(currentUser: CurrentUser) {
    const payload = await listStrategyTemplates({
      workspaceId: currentUser.active_workspace?.id,
      workflowKind: workflowFilter === "all" ? undefined : workflowFilter,
      starredOnly,
      pageSize: 50,
    });
    setTemplates(payload.results);
  }

  async function handleLaunch(template: StrategyTemplate) {
    if (user == null) {
      return;
    }
    setError(null);
    setIsLaunchingId(template.id);
    try {
      const launched = await launchStrategyTemplate(template.id);
      startTransition(() => {
        router.push(
          launched.workflow_kind === "screen"
            ? `/app/screens/${launched.run.id}`
            : `/app/backtests/${launched.run.id}`,
        );
      });
    } catch (launchError) {
      setError(formatApiError(launchError, "Unable to launch this template."));
    } finally {
      setIsLaunchingId(null);
      await refreshTemplates(user);
    }
  }

  async function handleEdit(template: StrategyTemplate) {
    const nextName = window.prompt("Template name", template.name);
    if (nextName == null || nextName.trim() === "") {
      return;
    }
    const nextDescription = window.prompt("Template description", template.description) ?? template.description;
    const nextTags = window.prompt("Template tags (comma separated)", template.tags.join(", ")) ?? template.tags.join(", ");
    const nextNotes = window.prompt("Template notes", template.notes) ?? template.notes;
    try {
      await updateStrategyTemplate(template.id, {
        name: nextName.trim(),
        description: nextDescription.trim(),
        tags: splitTags(nextTags),
        notes: nextNotes.trim(),
      });
      if (user) {
        await refreshTemplates(user);
      }
    } catch (updateError) {
      setError(formatApiError(updateError, "Unable to update this template."));
    }
  }

  async function handleToggleStar(template: StrategyTemplate) {
    try {
      await updateStrategyTemplate(template.id, { isStarred: !template.is_starred });
      if (user) {
        await refreshTemplates(user);
      }
    } catch (updateError) {
      setError(formatApiError(updateError, "Unable to update the template bookmark."));
    }
  }

  async function handleDelete(template: StrategyTemplate) {
    if (!window.confirm(`Delete template "${template.name}"?`)) {
      return;
    }
    try {
      await deleteStrategyTemplate(template.id);
      if (user) {
        await refreshTemplates(user);
      }
    } catch (deleteError) {
      setError(formatApiError(deleteError, "Unable to delete this template."));
    }
  }

  if (state === "loading") {
    return (
      <main style={pageStyle}>
        <section style={panelStyle}>
          <p style={eyebrowStyle}>Templates</p>
          <h1 style={titleStyle}>Loading reusable workflows</h1>
        </section>
      </main>
    );
  }

  if (state === "error" || user == null) {
    return (
      <main style={pageStyle}>
        <section style={panelStyle}>
          <p style={eyebrowStyle}>Templates</p>
          <h1 style={titleStyle}>Templates unavailable</h1>
          <p style={bodyStyle}>{error ?? "Unable to open your template library."}</p>
          <Link href="/app" style={primaryLinkStyle}>
            Back to dashboard
          </Link>
        </section>
      </main>
    );
  }

  return (
    <main style={pageStyle}>
      <section style={panelStyle}>
        <div style={headerRowStyle}>
          <div>
            <p style={eyebrowStyle}>Templates</p>
            <h1 style={titleStyle}>Turn strong runs into reusable workflows</h1>
          </div>
          <div style={actionRowStyle}>
            <Link href="/app/history" style={ghostLinkStyle}>
              Open history
            </Link>
            <Link href="/app" style={ghostLinkStyle}>
              Dashboard
            </Link>
          </div>
        </div>

        <p style={bodyStyle}>
          Save the screens and backtests worth repeating so a strong idea becomes a reusable
          workflow instead of a one-off result.
        </p>

        {error ? <p style={errorStyle}>{error}</p> : null}

        <div style={toolbarStyle}>
          <label style={fieldStyle}>
            <span style={labelStyle}>Workflow</span>
            <select
              value={workflowFilter}
              onChange={(event) => setWorkflowFilter(event.target.value as WorkflowFilter)}
              style={inputStyle}
            >
              <option value="all">All</option>
              <option value="screen">Screens</option>
              <option value="backtest">Backtests</option>
            </select>
          </label>
          <label style={checkboxFieldStyle}>
            <input type="checkbox" checked={starredOnly} onChange={(event) => setStarredOnly(event.target.checked)} />
            <span>Starred templates only</span>
          </label>
          <div style={noteStyle}>
            Save templates from history or any run detail page once the setup is worth repeating.
          </div>
        </div>

        <div style={listStyle}>
          {templates.length === 0 ? (
            <section style={cardStyle}>
              <p style={sectionLabelStyle}>No templates yet</p>
              <h2 style={cardTitleStyle}>
                {hasActiveFilters ? "No templates match this view" : "Your reusable workflow library is still empty"}
              </h2>
              <p style={bodyStyle}>
                {hasActiveFilters
                  ? "Clear the filters or save a screen or backtest from history to bring matching templates into view."
                  : "Save a strong screen or backtest when you want to rerun the same setup without rebuilding it from scratch."}
              </p>
              <div style={actionRowStyle}>
                <Link href="/app/history" style={primaryLinkStyle}>
                  Open history
                </Link>
                {hasActiveFilters ? (
                  <button
                    type="button"
                    style={ghostButtonStyle}
                    onClick={() => {
                      setWorkflowFilter("all");
                      setStarredOnly(false);
                    }}
                  >
                    Clear filters
                  </button>
                ) : null}
              </div>
            </section>
          ) : (
            templates.map((template) => (
              <section key={template.id} style={cardStyle}>
                <div style={cardHeaderStyle}>
                  <div>
                    <div style={titleRowStyle}>
                      <p style={sectionLabelStyle}>{humanizeLabel(template.workflow_kind)} template</p>
                      {template.is_starred ? <span style={starPillStyle}>Starred</span> : null}
                      <span style={pillStyle}>{humanizeLabel(template.review_status)}</span>
                    </div>
                    <h2 style={cardTitleStyle}>
                      <Link href={`/app/templates/${template.id}`} style={titleLinkStyle}>
                        {template.name}
                      </Link>
                    </h2>
                    <p style={metaStyle}>{template.universe.name}</p>
                  </div>
                  <span style={pillStyle}>{template.last_used_at ? "Used" : "New"}</span>
                </div>
                <p style={bodyStyle}>
                  {template.description || "Add a short note so future reruns start with context."}
                </p>
                {template.tags.length > 0 ? (
                  <div style={tagRowStyle}>
                    {template.tags.map((tag) => (
                      <span key={tag} style={tagStyle}>
                        {tag}
                      </span>
                    ))}
                  </div>
                ) : null}
                {template.notes ? <p style={noteBlockStyle}>{template.notes}</p> : null}
                <p style={metaStyle}>Created from {templateSourceLabel(template)}</p>
                <div style={actionRowStyle}>
                  <Link href={`/app/templates/${template.id}`} style={ghostLinkStyle}>
                    Open
                  </Link>
                  <Link
                    href={
                      template.workflow_kind === "screen"
                        ? `/app/screens?template_id=${template.id}`
                        : `/app/backtests?template_id=${template.id}`
                    }
                    style={ghostLinkStyle}
                  >
                    Open draft
                  </Link>
                  <button
                    type="button"
                    style={buttonStyle}
                    onClick={() => void handleLaunch(template)}
                    disabled={isLaunchingId === template.id}
                  >
                    {isLaunchingId === template.id ? "Launching..." : "Run now"}
                  </button>
                  <button type="button" style={ghostButtonStyle} onClick={() => void handleToggleStar(template)}>
                    {template.is_starred ? "Unstar" : "Star"}
                  </button>
                  <button type="button" style={ghostButtonStyle} onClick={() => void handleEdit(template)}>
                    Edit
                  </button>
                  <button type="button" style={dangerButtonStyle} onClick={() => void handleDelete(template)}>
                    Delete
                  </button>
                </div>
              </section>
            ))
          )}
        </div>
      </section>
    </main>
  );
}

function splitTags(value: string): string[] {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function humanizeLabel(value: string): string {
  return value
    .split(/[_\s]+/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function templateSourceLabel(template: StrategyTemplate): string {
  if (template.source_screen_run_id) {
    return `screen #${template.source_screen_run_id}`;
  }
  if (template.source_backtest_run_id) {
    return `backtest #${template.source_backtest_run_id}`;
  }
  return "a manually saved setup";
}

function formatApiError(error: unknown, fallback: string): string {
  if (error instanceof ApiError) {
    return error.errors.length > 0 ? `${error.message} ${error.errors.join(" ")}` : error.message;
  }
  return error instanceof Error ? error.message : fallback;
}

const pageStyle: CSSProperties = {
  minHeight: "100vh",
  padding: "2rem",
};

const panelStyle: CSSProperties = {
  width: "min(1200px, 100%)",
  margin: "0 auto",
  borderRadius: "28px",
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

const actionRowStyle: CSSProperties = {
  display: "flex",
  gap: "0.75rem",
  flexWrap: "wrap",
};

const toolbarStyle: CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  gap: "1rem",
  alignItems: "end",
  marginTop: "1.5rem",
  flexWrap: "wrap",
};

const listStyle: CSSProperties = {
  display: "grid",
  gap: "1rem",
  marginTop: "1.5rem",
};

const cardStyle: CSSProperties = {
  padding: "1.25rem",
  borderRadius: "22px",
  background: "#f8fbff",
  border: "1px solid rgba(73, 98, 128, 0.18)",
};

const cardHeaderStyle: CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  gap: "1rem",
  alignItems: "flex-start",
};

const titleRowStyle: CSSProperties = {
  display: "flex",
  gap: "0.55rem",
  alignItems: "center",
  flexWrap: "wrap",
};

const cardTitleStyle: CSSProperties = {
  margin: "0.35rem 0 0",
  fontSize: "1.5rem",
};

const titleLinkStyle: CSSProperties = {
  color: "inherit",
  textDecoration: "none",
};

const fieldStyle: CSSProperties = {
  display: "grid",
  gap: "0.4rem",
};

const checkboxFieldStyle: CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: "0.55rem",
  padding: "0.85rem 1rem",
  borderRadius: "14px",
  border: "1px solid rgba(73, 98, 128, 0.18)",
  background: "#fff",
};

const labelStyle: CSSProperties = {
  fontSize: "0.92rem",
  color: "#334862",
};

const inputStyle: CSSProperties = {
  borderRadius: "14px",
  border: "1px solid rgba(73, 98, 128, 0.25)",
  padding: "0.85rem 0.95rem",
  fontSize: "0.98rem",
  background: "#fff",
};

const primaryLinkStyle: CSSProperties = {
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

const buttonStyle: CSSProperties = {
  border: 0,
  borderRadius: "999px",
  padding: "0.8rem 1rem",
  background: "#162132",
  color: "#f5f7fb",
  cursor: "pointer",
};

const ghostButtonStyle: CSSProperties = {
  border: 0,
  borderRadius: "999px",
  padding: "0.8rem 1rem",
  background: "#dde6f0",
  color: "#162132",
  cursor: "pointer",
};

const dangerButtonStyle: CSSProperties = {
  ...ghostButtonStyle,
  background: "#ffe5e0",
  color: "#8f2622",
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
  maxWidth: "56rem",
  lineHeight: 1.6,
  color: "#334862",
};

const metaStyle: CSSProperties = {
  margin: "0.25rem 0",
  color: "#496280",
  lineHeight: 1.5,
};

const errorStyle: CSSProperties = {
  marginTop: "1rem",
  padding: "0.9rem 1rem",
  borderRadius: "16px",
  background: "#ffe5e0",
  color: "#8f2622",
};

const sectionLabelStyle: CSSProperties = {
  margin: 0,
  fontSize: "0.82rem",
  letterSpacing: "0.12em",
  textTransform: "uppercase",
  color: "#5c728d",
};

const pillStyle: CSSProperties = {
  alignSelf: "flex-start",
  padding: "0.45rem 0.75rem",
  borderRadius: "999px",
  background: "#dde6f0",
  color: "#162132",
};

const starPillStyle: CSSProperties = {
  padding: "0.22rem 0.5rem",
  borderRadius: "999px",
  background: "#fff4cc",
  color: "#8b5c00",
  fontSize: "0.8rem",
};

const noteStyle: CSSProperties = {
  padding: "0.9rem 1rem",
  borderRadius: "16px",
  background: "#f8fbff",
  border: "1px solid rgba(73, 98, 128, 0.18)",
  color: "#496280",
};

const noteBlockStyle: CSSProperties = {
  margin: "0.75rem 0 0",
  padding: "0.85rem 0.95rem",
  borderRadius: "16px",
  background: "#fff",
  border: "1px solid rgba(73, 98, 128, 0.12)",
  color: "#334862",
  lineHeight: 1.6,
  whiteSpace: "pre-wrap",
};

const tagRowStyle: CSSProperties = {
  display: "flex",
  gap: "0.45rem",
  flexWrap: "wrap",
  marginTop: "0.75rem",
};

const tagStyle: CSSProperties = {
  padding: "0.3rem 0.55rem",
  borderRadius: "999px",
  background: "#dde6f0",
  color: "#334862",
  fontSize: "0.86rem",
};
