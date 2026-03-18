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

type LoadState = "loading" | "ready" | "error";


export function TemplateHub() {
  const router = useRouter();
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [templates, setTemplates] = useState<StrategyTemplate[]>([]);
  const [workflowFilter, setWorkflowFilter] = useState<"all" | "screen" | "backtest">("all");
  const [state, setState] = useState<LoadState>("loading");
  const [error, setError] = useState<string | null>(null);
  const [isLaunchingId, setIsLaunchingId] = useState<number | null>(null);

  useEffect(() => {
    let active = true;

    async function load() {
      try {
        const currentUser = await getCurrentUser();
        const payload = await listStrategyTemplates({
          workspaceId: currentUser.active_workspace?.id,
          workflowKind: workflowFilter === "all" ? undefined : workflowFilter,
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
  }, [router, workflowFilter]);

  async function refreshTemplates(currentUser: CurrentUser) {
    const payload = await listStrategyTemplates({
      workspaceId: currentUser.active_workspace?.id,
      workflowKind: workflowFilter === "all" ? undefined : workflowFilter,
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
    try {
      await updateStrategyTemplate(template.id, {
        name: nextName.trim(),
        description: nextDescription.trim(),
      });
      if (user) {
        await refreshTemplates(user);
      }
    } catch (updateError) {
      setError(formatApiError(updateError, "Unable to update this template."));
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
          <h1 style={titleStyle}>Loading saved strategy templates</h1>
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
          <p style={bodyStyle}>{error ?? "Unable to load saved templates."}</p>
          <Link href="/app" style={primaryLinkStyle}>
            Back to app
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
            <p style={eyebrowStyle}>M7 Templates</p>
            <h1 style={titleStyle}>Reusable screen and backtest templates</h1>
          </div>
          <div style={actionRowStyle}>
            <Link href="/app" style={ghostLinkStyle}>
              App shell
            </Link>
            <Link href="/app/history" style={ghostLinkStyle}>
              History
            </Link>
          </div>
        </div>

        <p style={bodyStyle}>
          Save templates from prior runs, then use them as a draft or launch them directly without
          re-entering the full configuration.
        </p>

        {error ? <p style={errorStyle}>{error}</p> : null}

        <div style={toolbarStyle}>
          <label style={fieldStyle}>
            <span style={labelStyle}>Workflow</span>
            <select
              value={workflowFilter}
              onChange={(event) => setWorkflowFilter(event.target.value as "all" | "screen" | "backtest")}
              style={inputStyle}
            >
              <option value="all">All</option>
              <option value="screen">Screens</option>
              <option value="backtest">Backtests</option>
            </select>
          </label>
          <div style={noteStyle}>
            New templates are created from the history page.
          </div>
        </div>

        <div style={listStyle}>
          {templates.length === 0 ? (
            <section style={cardStyle}>
              <p style={bodyStyle}>No templates have been saved yet.</p>
              <Link href="/app/history" style={primaryLinkStyle}>
                Open history
              </Link>
            </section>
          ) : (
            templates.map((template) => (
              <section key={template.id} style={cardStyle}>
                <div style={cardHeaderStyle}>
                  <div>
                    <p style={sectionLabelStyle}>{template.workflow_kind}</p>
                    <h2 style={cardTitleStyle}>{template.name}</h2>
                    <p style={metaStyle}>{template.universe.name}</p>
                  </div>
                  <span style={pillStyle}>{template.last_used_at ? "Used" : "New"}</span>
                </div>
                <p style={bodyStyle}>{template.description || "No description provided."}</p>
                <p style={metaStyle}>
                  Source: {template.source_screen_run_id ? `screen #${template.source_screen_run_id}` : template.source_backtest_run_id ? `backtest #${template.source_backtest_run_id}` : "manual"}
                </p>
                <div style={actionRowStyle}>
                  <Link
                    href={
                      template.workflow_kind === "screen"
                        ? `/app/screens?template_id=${template.id}`
                        : `/app/backtests?template_id=${template.id}`
                    }
                    style={ghostLinkStyle}
                  >
                    Use as draft
                  </Link>
                  <button
                    type="button"
                    style={buttonStyle}
                    onClick={() => void handleLaunch(template)}
                    disabled={isLaunchingId === template.id}
                  >
                    {isLaunchingId === template.id ? "Launching..." : "Launch now"}
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

const cardTitleStyle: CSSProperties = {
  margin: "0.35rem 0 0",
  fontSize: "1.5rem",
};

const fieldStyle: CSSProperties = {
  display: "grid",
  gap: "0.4rem",
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

const noteStyle: CSSProperties = {
  padding: "0.9rem 1rem",
  borderRadius: "16px",
  background: "#f8fbff",
  border: "1px solid rgba(73, 98, 128, 0.18)",
  color: "#496280",
};
