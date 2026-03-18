"use client";

import { startTransition, useEffect, useMemo, useState, type CSSProperties } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import {
  ApiError,
  createStrategyTemplate,
  getCurrentUser,
  listBacktests,
  listScreens,
  type BacktestRun,
  type CurrentUser,
  type JobRunState,
  type ScreenRun,
} from "@/lib/api";

type LoadState = "loading" | "ready" | "error";


export function HistoryHub() {
  const router = useRouter();
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [screens, setScreens] = useState<ScreenRun[]>([]);
  const [screenCount, setScreenCount] = useState(0);
  const [screenPage, setScreenPage] = useState(1);
  const [backtests, setBacktests] = useState<BacktestRun[]>([]);
  const [backtestCount, setBacktestCount] = useState(0);
  const [backtestPage, setBacktestPage] = useState(1);
  const [jobState, setJobState] = useState<JobRunState | "">("");
  const [selectedScreenIds, setSelectedScreenIds] = useState<number[]>([]);
  const [selectedBacktestIds, setSelectedBacktestIds] = useState<number[]>([]);
  const [state, setState] = useState<LoadState>("loading");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;

    async function load() {
      try {
        const currentUser = await getCurrentUser();
        const workspaceId = currentUser.active_workspace?.id;
        const [screenPayload, backtestPayload] = await Promise.all([
          listScreens(workspaceId, { page: screenPage, pageSize: 10, jobState }),
          listBacktests(workspaceId, { page: backtestPage, pageSize: 10, jobState }),
        ]);
        if (!active) {
          return;
        }
        setUser(currentUser);
        setScreens(screenPayload.results);
        setScreenCount(screenPayload.count);
        setBacktests(backtestPayload.results);
        setBacktestCount(backtestPayload.count);
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
        setError(loadError instanceof Error ? loadError.message : "Unable to load run history.");
        setState("error");
      }
    }

    void load();

    return () => {
      active = false;
    };
  }, [backtestPage, jobState, router, screenPage]);

  const screenPageCount = Math.max(1, Math.ceil(screenCount / 10));
  const backtestPageCount = Math.max(1, Math.ceil(backtestCount / 10));
  const screenCompareHref = useMemo(() => {
    if (selectedScreenIds.length !== 2) {
      return null;
    }
    return `/app/history/compare?kind=screen&left=${selectedScreenIds[0]}&right=${selectedScreenIds[1]}`;
  }, [selectedScreenIds]);
  const backtestCompareHref = useMemo(() => {
    if (selectedBacktestIds.length !== 2) {
      return null;
    }
    return `/app/history/compare?kind=backtest&left=${selectedBacktestIds[0]}&right=${selectedBacktestIds[1]}`;
  }, [selectedBacktestIds]);

  async function handleSaveTemplate(kind: "screen" | "backtest", runId: number) {
    const defaultName = kind === "screen" ? `Screen run ${runId}` : `Backtest run ${runId}`;
    const name = window.prompt("Template name", defaultName);
    if (name == null || name.trim() === "") {
      return;
    }
    try {
      await createStrategyTemplate({
        name: name.trim(),
        sourceScreenRunId: kind === "screen" ? runId : undefined,
        sourceBacktestRunId: kind === "backtest" ? runId : undefined,
      });
      startTransition(() => {
        router.push("/app/templates");
      });
    } catch (templateError) {
      setError(formatApiError(templateError, "Unable to save this run as a template."));
    }
  }

  function toggleSelection(values: number[], nextId: number): number[] {
    if (values.includes(nextId)) {
      return values.filter((value) => value !== nextId);
    }
    return [...values, nextId].slice(-2);
  }

  if (state === "loading") {
    return (
      <main style={pageStyle}>
        <section style={panelStyle}>
          <p style={eyebrowStyle}>History</p>
          <h1 style={titleStyle}>Loading prior screen and backtest runs</h1>
        </section>
      </main>
    );
  }

  if (state === "error" || user == null) {
    return (
      <main style={pageStyle}>
        <section style={panelStyle}>
          <p style={eyebrowStyle}>History</p>
          <h1 style={titleStyle}>Run history unavailable</h1>
          <p style={bodyStyle}>{error ?? "Unable to load run history."}</p>
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
            <p style={eyebrowStyle}>M7 History</p>
            <h1 style={titleStyle}>Discover, compare, and reuse prior runs</h1>
          </div>
          <div style={actionRowStyle}>
            <Link href="/app" style={ghostLinkStyle}>
              App shell
            </Link>
            <Link href="/app/templates" style={ghostLinkStyle}>
              Templates
            </Link>
          </div>
        </div>

        <p style={bodyStyle}>
          Active workspace: <strong>{user.active_workspace?.name ?? "Unavailable"}</strong>. Save
          useful runs as templates, open them as drafts, or compare two runs side by side.
        </p>

        {error ? <p style={errorStyle}>{error}</p> : null}

        <div style={toolbarStyle}>
          <label style={fieldStyle}>
            <span style={labelStyle}>Job state filter</span>
            <select value={jobState} onChange={(event) => setJobState(event.target.value as JobRunState | "")} style={inputStyle}>
              <option value="">All states</option>
              <option value="queued">Queued</option>
              <option value="running">Running</option>
              <option value="succeeded">Succeeded</option>
              <option value="failed">Failed</option>
              <option value="cancelled">Cancelled</option>
              <option value="partial_failed">Partial failed</option>
            </select>
          </label>
        </div>

        <div style={layoutStyle}>
          <section style={sectionCardStyle}>
            <div style={cardHeaderStyle}>
              <div>
                <p style={sectionLabelStyle}>Screens</p>
                <h2 style={cardTitleStyle}>{screenCount.toLocaleString()} runs</h2>
              </div>
              {screenCompareHref ? (
                <Link href={screenCompareHref} style={primaryLinkStyle}>
                  Compare selected
                </Link>
              ) : (
                <span style={pillStyle}>Select 2 runs to compare</span>
              )}
            </div>
            <div style={rowListStyle}>
              {screens.length === 0 ? (
                <p style={bodyStyle}>No screen runs match the current filter.</p>
              ) : (
                screens.map((screen) => (
                  <article key={screen.id} style={rowCardStyle}>
                    <label style={checkboxStyle}>
                      <input
                        type="checkbox"
                        checked={selectedScreenIds.includes(screen.id)}
                        onChange={() => setSelectedScreenIds((current) => toggleSelection(current, screen.id))}
                      />
                      <span>Compare</span>
                    </label>
                    <div style={rowBodyStyle}>
                      <div>
                        <strong>Screen #{screen.id}</strong>
                        <div style={metaStyle}>{screen.universe.name}</div>
                        <div style={subtleMetaStyle}>{screen.created_at}</div>
                      </div>
                      <span style={stateBadgeStyle(screen.job.state)}>{screen.job.state.replaceAll("_", " ")}</span>
                    </div>
                    <div style={actionRowStyle}>
                      <Link href={`/app/screens/${screen.id}`} style={ghostLinkStyle}>
                        Open
                      </Link>
                      <Link href={`/app/screens?draft_screen_run_id=${screen.id}`} style={ghostLinkStyle}>
                        Duplicate as draft
                      </Link>
                      <button type="button" style={ghostButtonStyle} onClick={() => void handleSaveTemplate("screen", screen.id)}>
                        Save as template
                      </button>
                      {screen.artifacts[0] ? (
                        <a href={screen.artifacts[0].download_url} style={ghostLinkStyle}>
                          Export
                        </a>
                      ) : null}
                    </div>
                  </article>
                ))
              )}
            </div>
            <div style={paginationStyle}>
              <button type="button" style={ghostButtonStyle} onClick={() => setScreenPage((value) => Math.max(1, value - 1))} disabled={screenPage <= 1}>
                Previous
              </button>
              <span style={metaStyle}>Page {screenPage} of {screenPageCount}</span>
              <button type="button" style={ghostButtonStyle} onClick={() => setScreenPage((value) => Math.min(screenPageCount, value + 1))} disabled={screenPage >= screenPageCount}>
                Next
              </button>
            </div>
          </section>

          <section style={sectionCardStyle}>
            <div style={cardHeaderStyle}>
              <div>
                <p style={sectionLabelStyle}>Backtests</p>
                <h2 style={cardTitleStyle}>{backtestCount.toLocaleString()} runs</h2>
              </div>
              {backtestCompareHref ? (
                <Link href={backtestCompareHref} style={primaryLinkStyle}>
                  Compare selected
                </Link>
              ) : (
                <span style={pillStyle}>Select 2 runs to compare</span>
              )}
            </div>
            <div style={rowListStyle}>
              {backtests.length === 0 ? (
                <p style={bodyStyle}>No backtests match the current filter.</p>
              ) : (
                backtests.map((backtest) => (
                  <article key={backtest.id} style={rowCardStyle}>
                    <label style={checkboxStyle}>
                      <input
                        type="checkbox"
                        checked={selectedBacktestIds.includes(backtest.id)}
                        onChange={() => setSelectedBacktestIds((current) => toggleSelection(current, backtest.id))}
                      />
                      <span>Compare</span>
                    </label>
                    <div style={rowBodyStyle}>
                      <div>
                        <strong>Backtest #{backtest.id}</strong>
                        <div style={metaStyle}>{backtest.universe.name}</div>
                        <div style={subtleMetaStyle}>{backtest.start_date} to {backtest.end_date}</div>
                      </div>
                      <span style={stateBadgeStyle(backtest.job.state)}>{backtest.job.state.replaceAll("_", " ")}</span>
                    </div>
                    <div style={actionRowStyle}>
                      <Link href={`/app/backtests/${backtest.id}`} style={ghostLinkStyle}>
                        Open
                      </Link>
                      <Link href={`/app/backtests?draft_backtest_run_id=${backtest.id}`} style={ghostLinkStyle}>
                        Duplicate as draft
                      </Link>
                      <button type="button" style={ghostButtonStyle} onClick={() => void handleSaveTemplate("backtest", backtest.id)}>
                        Save as template
                      </button>
                      {backtest.artifacts[0] ? (
                        <a href={backtest.artifacts[0].download_url} style={ghostLinkStyle}>
                          Export
                        </a>
                      ) : null}
                    </div>
                  </article>
                ))
              )}
            </div>
            <div style={paginationStyle}>
              <button type="button" style={ghostButtonStyle} onClick={() => setBacktestPage((value) => Math.max(1, value - 1))} disabled={backtestPage <= 1}>
                Previous
              </button>
              <span style={metaStyle}>Page {backtestPage} of {backtestPageCount}</span>
              <button type="button" style={ghostButtonStyle} onClick={() => setBacktestPage((value) => Math.min(backtestPageCount, value + 1))} disabled={backtestPage >= backtestPageCount}>
                Next
              </button>
            </div>
          </section>
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

function stateBadgeStyle(state: ScreenRun["job"]["state"]): CSSProperties {
  const palette = {
    queued: { background: "#dde6f0", color: "#162132" },
    running: { background: "#e6f1ff", color: "#0f4c81" },
    succeeded: { background: "#e2f3e7", color: "#17663a" },
    failed: { background: "#ffe5e0", color: "#8f2622" },
    cancelled: { background: "#f1ecdf", color: "#6b5a19" },
    partial_failed: { background: "#fff2d9", color: "#8b5c00" },
  } satisfies Record<ScreenRun["job"]["state"], { background: string; color: string }>;
  return {
    padding: "0.45rem 0.75rem",
    borderRadius: "999px",
    textTransform: "capitalize",
    background: palette[state].background,
    color: palette[state].color,
    whiteSpace: "nowrap",
  };
}

const pageStyle: CSSProperties = {
  minHeight: "100vh",
  padding: "2rem",
};

const panelStyle: CSSProperties = {
  width: "min(1320px, 100%)",
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

const layoutStyle: CSSProperties = {
  display: "grid",
  gap: "1rem",
  gridTemplateColumns: "repeat(auto-fit, minmax(420px, 1fr))",
  marginTop: "1.5rem",
};

const sectionCardStyle: CSSProperties = {
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

const rowListStyle: CSSProperties = {
  display: "grid",
  gap: "0.9rem",
  marginTop: "1rem",
};

const rowCardStyle: CSSProperties = {
  padding: "1rem",
  borderRadius: "18px",
  background: "#fff",
  border: "1px solid rgba(73, 98, 128, 0.16)",
  display: "grid",
  gap: "0.9rem",
};

const rowBodyStyle: CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  gap: "1rem",
  alignItems: "flex-start",
};

const checkboxStyle: CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  gap: "0.45rem",
  color: "#496280",
};

const paginationStyle: CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  gap: "0.75rem",
  alignItems: "center",
  marginTop: "1rem",
  flexWrap: "wrap",
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

const ghostButtonStyle: CSSProperties = {
  border: 0,
  borderRadius: "999px",
  padding: "0.8rem 1rem",
  background: "#dde6f0",
  color: "#162132",
  cursor: "pointer",
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
  fontSize: "clamp(2rem, 4vw, 3.2rem)",
};

const bodyStyle: CSSProperties = {
  maxWidth: "64rem",
  lineHeight: 1.6,
  color: "#334862",
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

const cardTitleStyle: CSSProperties = {
  margin: "0.45rem 0 0",
  fontSize: "1.6rem",
};

const metaStyle: CSSProperties = {
  margin: "0.25rem 0",
  color: "#496280",
  lineHeight: 1.5,
};

const subtleMetaStyle: CSSProperties = {
  color: "#5c728d",
  lineHeight: 1.5,
};

const pillStyle: CSSProperties = {
  alignSelf: "flex-start",
  padding: "0.45rem 0.75rem",
  borderRadius: "999px",
  background: "#dde6f0",
  color: "#162132",
};

