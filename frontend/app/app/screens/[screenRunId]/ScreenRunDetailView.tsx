"use client";

import { startTransition, useEffect, useMemo, useState, type CSSProperties, type FormEvent } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import {
  ApiError,
  createStrategyTemplate,
  getCurrentUser,
  getScreenRun,
  listScreenExclusions,
  listScreenRows,
  updateScreenRun,
  type ScreenExclusion,
  type ScreenResultRow,
  type ScreenRun,
} from "@/lib/api";
import { readViewPreference, writeViewPreference } from "@/lib/viewPreferences";

type LoadState = "loading" | "ready" | "error";

type ScreenRunDetailViewProps = {
  screenRunId: number;
};

type TablePreference = {
  rowPageSize: number;
  rowSort: string;
  rowDirection: "asc" | "desc";
  showCompany: boolean;
  showMomentum: boolean;
};

const DEFAULT_TABLE_PREFERENCE: TablePreference = {
  rowPageSize: 25,
  rowSort: "position",
  rowDirection: "asc",
  showCompany: true,
  showMomentum: true,
};

export function ScreenRunDetailView({ screenRunId }: ScreenRunDetailViewProps) {
  const router = useRouter();
  const [screenRun, setScreenRun] = useState<ScreenRun | null>(null);
  const [rows, setRows] = useState<ScreenResultRow[]>([]);
  const [exclusions, setExclusions] = useState<ScreenExclusion[]>([]);
  const [rowCount, setRowCount] = useState(0);
  const [exclusionCount, setExclusionCount] = useState(0);
  const [rowPage, setRowPage] = useState(1);
  const [rowPageSize, setRowPageSize] = useState(DEFAULT_TABLE_PREFERENCE.rowPageSize);
  const [rowSort, setRowSort] = useState(DEFAULT_TABLE_PREFERENCE.rowSort);
  const [rowDirection, setRowDirection] = useState<"asc" | "desc">(DEFAULT_TABLE_PREFERENCE.rowDirection);
  const [showCompany, setShowCompany] = useState(DEFAULT_TABLE_PREFERENCE.showCompany);
  const [showMomentum, setShowMomentum] = useState(DEFAULT_TABLE_PREFERENCE.showMomentum);
  const [exclusionPage, setExclusionPage] = useState(1);
  const [state, setState] = useState<LoadState>("loading");
  const [error, setError] = useState<string | null>(null);
  const [isStarred, setIsStarred] = useState(false);
  const [tagsText, setTagsText] = useState("");
  const [notes, setNotes] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [isSavingTemplate, setIsSavingTemplate] = useState(false);

  useEffect(() => {
    const preference = readViewPreference<TablePreference>("screen-run-detail", DEFAULT_TABLE_PREFERENCE);
    setRowPageSize(preference.rowPageSize);
    setRowSort(preference.rowSort);
    setRowDirection(preference.rowDirection);
    setShowCompany(preference.showCompany);
    setShowMomentum(preference.showMomentum);
  }, []);

  useEffect(() => {
    writeViewPreference("screen-run-detail", {
      rowPageSize,
      rowSort,
      rowDirection,
      showCompany,
      showMomentum,
    });
  }, [rowDirection, rowPageSize, rowSort, showCompany, showMomentum]);

  useEffect(() => {
    let active = true;

    async function load() {
      try {
        await getCurrentUser();
        const payloads = await loadDetailPayloads(screenRunId, {
          rowPage,
          rowPageSize,
          rowSort,
          rowDirection,
          exclusionPage,
        });
        if (!active) {
          return;
        }
        applyPayloads(payloads, true);
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
        setError(loadError instanceof Error ? loadError.message : "Unable to load the screen run.");
        setState("error");
      }
    }

    void load();

    return () => {
      active = false;
    };
  }, [exclusionPage, rowDirection, rowPage, rowPageSize, rowSort, router, screenRunId]);

  useEffect(() => {
    if (screenRun == null || screenRun.job.is_terminal || state !== "ready") {
      return undefined;
    }

    const intervalId = window.setInterval(() => {
      void refreshDetail();
    }, 1500);

    return () => {
      window.clearInterval(intervalId);
    };
  }, [screenRun, state]);

  const rowPageCount = Math.max(1, Math.ceil(rowCount / rowPageSize));
  const exclusionPageCount = Math.max(1, Math.ceil(exclusionCount / 25));
  const visibleColumnCount = 5 + (showCompany ? 1 : 0) + (showMomentum ? 1 : 0);
  const topTickers = rows.slice(0, 3).map((row) => row.ticker);
  const exclusionSummary = useMemo(() => summarizeExclusions(exclusions), [exclusions]);

  async function refreshDetail() {
    try {
      const payloads = await loadDetailPayloads(screenRunId, {
        rowPage,
        rowPageSize,
        rowSort,
        rowDirection,
        exclusionPage,
      });
      applyPayloads(payloads, false);
    } catch (refreshError) {
      setError(formatApiError(refreshError, "Unable to refresh the screen run."));
    }
  }

  function applyPayloads(payloads: Awaited<ReturnType<typeof loadDetailPayloads>>, syncAnnotations: boolean) {
    setScreenRun(payloads.run);
    setRows(payloads.rows.results);
    setExclusions(payloads.exclusions.results);
    setRowCount(payloads.rows.count);
    setExclusionCount(payloads.exclusions.count);
    if (syncAnnotations) {
      setIsStarred(payloads.run.is_starred);
      setTagsText(payloads.run.tags.join(", "));
      setNotes(payloads.run.notes);
    }
  }

  async function handleSaveAnnotations(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsSaving(true);
    setError(null);
    try {
      const updated = await updateScreenRun(screenRunId, {
        isStarred,
        tags: splitTags(tagsText),
        notes,
      });
      setScreenRun(updated);
      setIsStarred(updated.is_starred);
      setTagsText(updated.tags.join(", "));
      setNotes(updated.notes);
    } catch (saveError) {
      setError(formatApiError(saveError, "Unable to save the run annotations."));
    } finally {
      setIsSaving(false);
    }
  }

  async function handlePromoteToTemplate() {
    if (screenRun == null) {
      return;
    }
    const name = window.prompt("Template name", `Screen run ${screenRun.id}`);
    if (name == null || name.trim() === "") {
      return;
    }
    setIsSavingTemplate(true);
    setError(null);
    try {
      await createStrategyTemplate({
        name: name.trim(),
        description: screenRun.notes || `Saved from screen run #${screenRun.id}`,
        sourceScreenRunId: screenRun.id,
        isStarred: screenRun.is_starred,
        tags: screenRun.tags,
        notes: screenRun.notes,
      });
      startTransition(() => {
        router.push("/app/templates");
      });
    } catch (templateError) {
      setError(formatApiError(templateError, "Unable to save this run as a template."));
    } finally {
      setIsSavingTemplate(false);
    }
  }

  if (state === "loading") {
    return (
      <main style={pageStyle}>
        <section style={panelStyle}>
          <p style={eyebrowStyle}>Screen Run</p>
          <h1 style={titleStyle}>Loading persisted screen results</h1>
        </section>
      </main>
    );
  }

  if (state === "error" || screenRun == null) {
    return (
      <main style={pageStyle}>
        <section style={panelStyle}>
          <p style={eyebrowStyle}>Screen Run</p>
          <h1 style={titleStyle}>Screen run unavailable</h1>
          <p style={bodyStyle}>{error ?? "Unable to load this screen run."}</p>
          <div style={actionRowStyle}>
            <Link href="/app/screens" style={primaryLinkStyle}>
              Back to screens
            </Link>
          </div>
        </section>
      </main>
    );
  }

  return (
    <main style={pageStyle}>
      <section style={panelStyle}>
        <div style={headerRowStyle}>
          <div>
            <p style={eyebrowStyle}>Screen Run</p>
            <h1 style={titleStyle}>
              #{screenRun.id} · {screenRun.universe.name}
            </h1>
          </div>
          <div style={actionRowStyle}>
            <Link href="/app/screens" style={ghostLinkStyle}>
              All screens
            </Link>
            <Link href={`/app/universes/${screenRun.universe.id}`} style={ghostLinkStyle}>
              Universe
            </Link>
            <Link href={`/app/screens?draft_screen_run_id=${screenRun.id}`} style={ghostLinkStyle}>
              Clone as draft
            </Link>
            <button type="button" style={buttonStyle} onClick={() => void handlePromoteToTemplate()} disabled={isSavingTemplate}>
              {isSavingTemplate ? "Saving..." : "Promote to template"}
            </button>
          </div>
        </div>

        <p style={bodyStyle}>
          Workspace: <strong>{screenRun.workspace.name}</strong>. This page now remembers your
          preferred result-table layout and lets you annotate the run before you revisit it later.
        </p>

        {error ? <p style={errorStyle}>{error}</p> : null}

        <div style={statusCardStyle}>
          <div style={statusHeaderStyle}>
            <div>
              <p style={sectionLabelStyle}>Job state</p>
              <h2 style={statusTitleStyle}>{screenRun.job.state.replaceAll("_", " ")}</h2>
            </div>
            <span style={stateBadgeStyle(screenRun.job.state)}>{screenRun.job.state.replaceAll("_", " ")}</span>
          </div>
          <div style={progressTrackStyle}>
            <div style={{ ...progressFillStyle, width: `${Math.max(6, screenRun.job.progress_percent)}%` }} />
          </div>
          <div style={progressMetaStyle}>
            <span>{screenRun.job.progress_percent}%</span>
            <span>{screenRun.job.current_step || "Pending"}</span>
          </div>
        </div>

        <div style={summaryGridStyle}>
          <SummaryCard
            label="What happened"
            value={topTickers.length > 0 ? topTickers.join(", ") : "Waiting"}
            detail={topTickers.length > 0 ? "Top names on the current page" : "Top picks appear when ranking finishes"}
          />
          <SummaryCard
            label="Ranked rows"
            value={screenRun.result_count.toLocaleString()}
            detail={`${screenRun.total_candidate_count.toLocaleString()} total candidates`}
          />
          <SummaryCard
            label="Exclusions"
            value={screenRun.exclusion_count.toLocaleString()}
            detail={`${screenRun.resolved_ticker_count.toLocaleString()} tickers screened`}
          />
          <SummaryCard
            label="Configuration"
            value={screenRun.momentum_mode}
            detail={`Top ${screenRun.top_n} · Cache ${screenRun.cache_ttl_hours}h`}
          />
          <SummaryCard
            label="Research status"
            value={screenRun.is_starred ? "Starred" : "Standard"}
            detail={screenRun.tags.length > 0 ? screenRun.tags.join(", ") : "No tags yet"}
          />
        </div>

        <div style={layoutStyle}>
          <section style={sectionCardStyle}>
            <div style={tableHeaderStyle}>
              <div>
                <p style={sectionLabelStyle}>Ranked results</p>
                <h2 style={tableTitleStyle}>{rowCount.toLocaleString()} rows</h2>
              </div>
              <div style={toolbarStyle}>
                <select value={rowSort} onChange={(event) => setRowSort(event.target.value)} style={compactInputStyle}>
                  <option value="position">Position</option>
                  <option value="ticker">Ticker</option>
                  <option value="company_name">Company</option>
                  <option value="market_cap">Market cap</option>
                  <option value="return_on_capital">ROC</option>
                  <option value="earnings_yield">EY</option>
                  <option value="momentum_6m">Momentum</option>
                  <option value="final_score">Final score</option>
                </select>
                <select
                  value={rowDirection}
                  onChange={(event) => setRowDirection(event.target.value as "asc" | "desc")}
                  style={compactInputStyle}
                >
                  <option value="asc">Ascending</option>
                  <option value="desc">Descending</option>
                </select>
                <select
                  value={rowPageSize}
                  onChange={(event) => {
                    setRowPage(1);
                    setRowPageSize(Number(event.target.value));
                  }}
                  style={compactInputStyle}
                >
                  <option value={10}>10</option>
                  <option value={25}>25</option>
                  <option value={50}>50</option>
                </select>
                <label style={toggleStyle}>
                  <input type="checkbox" checked={showCompany} onChange={(event) => setShowCompany(event.target.checked)} />
                  <span>Company</span>
                </label>
                <label style={toggleStyle}>
                  <input type="checkbox" checked={showMomentum} onChange={(event) => setShowMomentum(event.target.checked)} />
                  <span>Momentum</span>
                </label>
              </div>
            </div>
            <div style={tableWrapperStyle}>
              <table style={tableStyle}>
                <thead>
                  <tr>
                    <th style={headerCellStyle}>#</th>
                    <th style={headerCellStyle}>Ticker</th>
                    {showCompany ? <th style={headerCellStyle}>Company</th> : null}
                    <th style={headerCellStyle}>ROC</th>
                    <th style={headerCellStyle}>EY</th>
                    {showMomentum ? <th style={headerCellStyle}>Momentum</th> : null}
                    <th style={headerCellStyle}>Final</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.length === 0 ? (
                    <tr>
                      <td style={emptyCellStyle} colSpan={visibleColumnCount}>
                        {screenRun.job.is_terminal ? "No ranked rows were persisted." : "Rows will appear once the run finishes."}
                      </td>
                    </tr>
                  ) : (
                    rows.map((row) => (
                      <tr key={row.id}>
                        <td style={cellStyle}>{row.position}</td>
                        <td style={tickerCellStyle}>{row.ticker}</td>
                        {showCompany ? <td style={cellStyle}>{row.company_name ?? "-"}</td> : null}
                        <td style={cellStyle}>{formatNumber(row.return_on_capital)}</td>
                        <td style={cellStyle}>{formatNumber(row.earnings_yield)}</td>
                        {showMomentum ? <td style={cellStyle}>{formatNumber(row.momentum_6m)}</td> : null}
                        <td style={cellStyle}>{row.final_score ?? "-"}</td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
            <div style={paginationStyle}>
              <button type="button" style={ghostButtonStyle} onClick={() => setRowPage((value) => Math.max(1, value - 1))} disabled={rowPage <= 1}>
                Previous
              </button>
              <span style={metaStyle}>
                Page {rowPage} of {rowPageCount}
              </span>
              <button
                type="button"
                style={ghostButtonStyle}
                onClick={() => setRowPage((value) => Math.min(rowPageCount, value + 1))}
                disabled={rowPage >= rowPageCount}
              >
                Next
              </button>
            </div>
          </section>

          <div style={stackStyle}>
            <section style={sectionCardStyle}>
              <div style={tableHeaderStyle}>
                <div>
                  <p style={sectionLabelStyle}>Research notes</p>
                  <h2 style={tableTitleStyle}>Bookmark and annotate</h2>
                </div>
                {screenRun.is_starred ? <span style={starPillStyle}>Starred</span> : null}
              </div>
              <form onSubmit={handleSaveAnnotations} style={formStyle}>
                <label style={fieldStyle}>
                  <span style={labelStyle}>Tags</span>
                  <input
                    type="text"
                    value={tagsText}
                    onChange={(event) => setTagsText(event.target.value)}
                    placeholder="watchlist, review, quality"
                    style={inputStyle}
                  />
                </label>
                <label style={fieldStyle}>
                  <span style={labelStyle}>Notes</span>
                  <textarea value={notes} onChange={(event) => setNotes(event.target.value)} rows={6} style={textareaStyle} />
                </label>
                <label style={checkboxFieldStyle}>
                  <input type="checkbox" checked={isStarred} onChange={(event) => setIsStarred(event.target.checked)} />
                  <span>Star this run so it stays easy to find in history</span>
                </label>
                <button type="submit" style={buttonStyle} disabled={isSaving}>
                  {isSaving ? "Saving..." : "Save annotations"}
                </button>
              </form>
            </section>

            <section style={sectionCardStyle}>
              <div style={tableHeaderStyle}>
                <div>
                  <p style={sectionLabelStyle}>Artifacts</p>
                  <h2 style={tableTitleStyle}>{screenRun.artifacts.length} available</h2>
                </div>
              </div>
              <div style={stackStyle}>
                {screenRun.artifacts.map((artifact) => (
                  <a key={artifact.download_url} href={artifact.download_url} style={artifactLinkStyle}>
                    <strong>{artifact.label}</strong>
                    <span style={subtleMetaStyle}>{artifact.filename}</span>
                  </a>
                ))}
              </div>
            </section>

            <section style={sectionCardStyle}>
              <div style={tableHeaderStyle}>
                <div>
                  <p style={sectionLabelStyle}>Exclusions</p>
                  <h2 style={tableTitleStyle}>{exclusionCount.toLocaleString()} rows</h2>
                </div>
                <span style={pillStyle}>First page</span>
              </div>
              {exclusionSummary.length > 0 ? (
                <div style={tagRowStyle}>
                  {exclusionSummary.map((item) => (
                    <span key={item.reason} style={tagStyle}>
                      {item.reason} ({item.count})
                    </span>
                  ))}
                </div>
              ) : null}
              <div style={tableWrapperStyle}>
                <table style={tableStyle}>
                  <thead>
                    <tr>
                      <th style={headerCellStyle}>Ticker</th>
                      <th style={headerCellStyle}>Reason</th>
                    </tr>
                  </thead>
                  <tbody>
                    {exclusions.length === 0 ? (
                      <tr>
                        <td style={emptyCellStyle} colSpan={2}>
                          {screenRun.job.is_terminal ? "No exclusions were recorded." : "Exclusions will appear once the run finishes."}
                        </td>
                      </tr>
                    ) : (
                      exclusions.map((exclusion) => (
                        <tr key={exclusion.id}>
                          <td style={tickerCellStyle}>{exclusion.ticker}</td>
                          <td style={cellStyle}>{exclusion.reason}</td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
              <div style={paginationStyle}>
                <button
                  type="button"
                  style={ghostButtonStyle}
                  onClick={() => setExclusionPage((value) => Math.max(1, value - 1))}
                  disabled={exclusionPage <= 1}
                >
                  Previous
                </button>
                <span style={metaStyle}>
                  Page {exclusionPage} of {exclusionPageCount}
                </span>
                <button
                  type="button"
                  style={ghostButtonStyle}
                  onClick={() => setExclusionPage((value) => Math.min(exclusionPageCount, value + 1))}
                  disabled={exclusionPage >= exclusionPageCount}
                >
                  Next
                </button>
              </div>
            </section>
          </div>
        </div>
      </section>
    </main>
  );
}

async function loadDetailPayloads(
  screenRunId: number,
  options: {
    rowPage: number;
    rowPageSize: number;
    rowSort: string;
    rowDirection: "asc" | "desc";
    exclusionPage: number;
  },
) {
  const [run, rows, exclusions] = await Promise.all([
    getScreenRun(screenRunId),
    listScreenRows({
      screenRunId,
      page: options.rowPage,
      pageSize: options.rowPageSize,
      sort: options.rowSort,
      direction: options.rowDirection,
    }),
    listScreenExclusions({ screenRunId, page: options.exclusionPage, pageSize: 25 }),
  ]);
  return { run, rows, exclusions };
}

function summarizeExclusions(exclusions: ScreenExclusion[]): Array<{ reason: string; count: number }> {
  const counts = new Map<string, number>();
  for (const exclusion of exclusions) {
    counts.set(exclusion.reason, (counts.get(exclusion.reason) ?? 0) + 1);
  }
  return [...counts.entries()]
    .map(([reason, count]) => ({ reason, count }))
    .sort((left, right) => right.count - left.count)
    .slice(0, 4);
}

function splitTags(value: string): string[] {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function SummaryCard({ label, value, detail }: { label: string; value: string; detail: string }) {
  return (
    <div style={summaryCardStyle}>
      <p style={sectionLabelStyle}>{label}</p>
      <h2 style={summaryTitleStyle}>{value}</h2>
      <p style={metaStyle}>{detail}</p>
    </div>
  );
}

function formatApiError(error: unknown, fallback: string): string {
  if (error instanceof ApiError) {
    return error.errors.length > 0 ? `${error.message} ${error.errors.join(" ")}` : error.message;
  }
  return error instanceof Error ? error.message : fallback;
}

function formatNumber(value: number | null): string {
  if (value == null) {
    return "-";
  }
  return value.toFixed(4);
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
  width: "min(1480px, 100%)",
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

const summaryGridStyle: CSSProperties = {
  display: "grid",
  gap: "1rem",
  gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
  marginTop: "1.5rem",
};

const summaryCardStyle: CSSProperties = {
  padding: "1.1rem",
  borderRadius: "20px",
  background: "#f8fbff",
  border: "1px solid rgba(73, 98, 128, 0.18)",
  display: "grid",
  gap: "0.55rem",
};

const summaryTitleStyle: CSSProperties = {
  margin: 0,
  fontSize: "1.55rem",
};

const statusCardStyle: CSSProperties = {
  padding: "1.25rem",
  borderRadius: "22px",
  background: "#f8fbff",
  border: "1px solid rgba(73, 98, 128, 0.18)",
  marginTop: "1.5rem",
};

const statusHeaderStyle: CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  alignItems: "flex-start",
  gap: "1rem",
};

const statusTitleStyle: CSSProperties = {
  margin: "0.35rem 0 0",
  fontSize: "1.9rem",
};

const progressTrackStyle: CSSProperties = {
  marginTop: "1rem",
  width: "100%",
  height: "0.7rem",
  borderRadius: "999px",
  background: "#dde6f0",
  overflow: "hidden",
};

const progressFillStyle: CSSProperties = {
  height: "100%",
  borderRadius: "999px",
  background: "linear-gradient(90deg, #24405f 0%, #5d8dc0 100%)",
};

const progressMetaStyle: CSSProperties = {
  marginTop: "0.75rem",
  display: "flex",
  justifyContent: "space-between",
  gap: "0.75rem",
  color: "#496280",
  flexWrap: "wrap",
};

const layoutStyle: CSSProperties = {
  display: "grid",
  gap: "1rem",
  gridTemplateColumns: "minmax(0, 1.45fr) minmax(320px, 0.95fr)",
  marginTop: "1.5rem",
};

const stackStyle: CSSProperties = {
  display: "grid",
  gap: "1rem",
  alignContent: "start",
};

const sectionCardStyle: CSSProperties = {
  padding: "1.25rem",
  borderRadius: "22px",
  background: "#f8fbff",
  border: "1px solid rgba(73, 98, 128, 0.18)",
};

const tableHeaderStyle: CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  gap: "1rem",
  alignItems: "flex-start",
  flexWrap: "wrap",
};

const tableTitleStyle: CSSProperties = {
  margin: "0.35rem 0 0",
  fontSize: "1.45rem",
};

const toolbarStyle: CSSProperties = {
  display: "flex",
  gap: "0.65rem",
  flexWrap: "wrap",
  alignItems: "center",
};

const formStyle: CSSProperties = {
  display: "grid",
  gap: "0.85rem",
  marginTop: "1rem",
};

const fieldStyle: CSSProperties = {
  display: "grid",
  gap: "0.45rem",
};

const labelStyle: CSSProperties = {
  fontSize: "0.92rem",
  color: "#334862",
};

const inputStyle: CSSProperties = {
  width: "100%",
  borderRadius: "14px",
  border: "1px solid rgba(73, 98, 128, 0.25)",
  padding: "0.85rem 0.95rem",
  fontSize: "0.98rem",
  background: "#fff",
};

const textareaStyle: CSSProperties = {
  ...inputStyle,
  resize: "vertical",
  minHeight: "7rem",
};

const checkboxFieldStyle: CSSProperties = {
  display: "flex",
  gap: "0.55rem",
  alignItems: "center",
  padding: "0.9rem 1rem",
  borderRadius: "14px",
  border: "1px solid rgba(73, 98, 128, 0.18)",
  background: "#fff",
};

const toggleStyle: CSSProperties = {
  display: "inline-flex",
  gap: "0.4rem",
  alignItems: "center",
  padding: "0.65rem 0.8rem",
  borderRadius: "12px",
  background: "#fff",
  border: "1px solid rgba(73, 98, 128, 0.18)",
  color: "#334862",
};

const tableWrapperStyle: CSSProperties = {
  marginTop: "1rem",
  overflowX: "auto",
};

const tableStyle: CSSProperties = {
  width: "100%",
  borderCollapse: "collapse",
};

const headerCellStyle: CSSProperties = {
  textAlign: "left",
  padding: "0.75rem 0.65rem",
  fontSize: "0.86rem",
  letterSpacing: "0.08em",
  textTransform: "uppercase",
  color: "#5c728d",
  borderBottom: "1px solid rgba(73, 98, 128, 0.2)",
};

const cellStyle: CSSProperties = {
  padding: "0.8rem 0.65rem",
  borderBottom: "1px solid rgba(73, 98, 128, 0.12)",
  color: "#334862",
  verticalAlign: "top",
};

const tickerCellStyle: CSSProperties = {
  ...cellStyle,
  fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace",
  color: "#162132",
};

const emptyCellStyle: CSSProperties = {
  padding: "1rem 0.65rem",
  color: "#5c728d",
  textAlign: "center",
};

const paginationStyle: CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  alignItems: "center",
  gap: "0.75rem",
  marginTop: "1rem",
  flexWrap: "wrap",
};

const compactInputStyle: CSSProperties = {
  borderRadius: "12px",
  border: "1px solid rgba(73, 98, 128, 0.25)",
  padding: "0.7rem 0.8rem",
  background: "#fff",
};

const buttonStyle: CSSProperties = {
  border: 0,
  borderRadius: "999px",
  padding: "0.85rem 1rem",
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

const artifactLinkStyle: CSSProperties = {
  display: "grid",
  gap: "0.2rem",
  padding: "0.9rem 1rem",
  borderRadius: "16px",
  background: "#fff",
  border: "1px solid rgba(73, 98, 128, 0.15)",
  color: "#162132",
  textDecoration: "none",
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
  maxWidth: "68rem",
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

const metaStyle: CSSProperties = {
  margin: "0.25rem 0",
  color: "#496280",
  lineHeight: 1.5,
};

const subtleMetaStyle: CSSProperties = {
  color: "#6d8097",
  lineHeight: 1.5,
};

const pillStyle: CSSProperties = {
  padding: "0.35rem 0.6rem",
  borderRadius: "999px",
  background: "#dde6f0",
  color: "#162132",
  fontSize: "0.82rem",
};

const starPillStyle: CSSProperties = {
  padding: "0.25rem 0.55rem",
  borderRadius: "999px",
  background: "#fff4cc",
  color: "#8b5c00",
  fontSize: "0.82rem",
};

const tagRowStyle: CSSProperties = {
  display: "flex",
  gap: "0.45rem",
  flexWrap: "wrap",
  marginTop: "0.85rem",
};

const tagStyle: CSSProperties = {
  padding: "0.3rem 0.55rem",
  borderRadius: "999px",
  background: "#dde6f0",
  color: "#334862",
  fontSize: "0.84rem",
};
