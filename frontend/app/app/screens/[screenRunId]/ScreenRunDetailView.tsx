"use client";

import { startTransition, useEffect, useState, type CSSProperties } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import {
  ApiError,
  getCurrentUser,
  getScreenRun,
  listScreenExclusions,
  listScreenRows,
  type ScreenExclusion,
  type ScreenResultRow,
  type ScreenRun,
} from "@/lib/api";

type LoadState = "loading" | "ready" | "error";

type ScreenRunDetailViewProps = {
  screenRunId: number;
};


export function ScreenRunDetailView({ screenRunId }: ScreenRunDetailViewProps) {
  const router = useRouter();
  const [screenRun, setScreenRun] = useState<ScreenRun | null>(null);
  const [rows, setRows] = useState<ScreenResultRow[]>([]);
  const [exclusions, setExclusions] = useState<ScreenExclusion[]>([]);
  const [rowCount, setRowCount] = useState(0);
  const [exclusionCount, setExclusionCount] = useState(0);
  const [rowPage, setRowPage] = useState(1);
  const [rowPageSize, setRowPageSize] = useState(25);
  const [rowSort, setRowSort] = useState("position");
  const [rowDirection, setRowDirection] = useState<"asc" | "desc">("asc");
  const [exclusionPage, setExclusionPage] = useState(1);
  const [state, setState] = useState<LoadState>("loading");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;

    async function load() {
      try {
        await getCurrentUser();
        const [screenPayload, rowPayload, exclusionPayload] = await Promise.all([
          getScreenRun(screenRunId),
          listScreenRows({ screenRunId, page: rowPage, pageSize: rowPageSize, sort: rowSort, direction: rowDirection }),
          listScreenExclusions({ screenRunId, page: exclusionPage, pageSize: 25 }),
        ]);
        if (!active) {
          return;
        }
        setScreenRun(screenPayload);
        setRows(rowPayload.results);
        setExclusions(exclusionPayload.results);
        setRowCount(rowPayload.count);
        setExclusionCount(exclusionPayload.count);
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

  async function refreshDetail() {
    try {
      const [screenPayload, rowPayload, exclusionPayload] = await Promise.all([
        getScreenRun(screenRunId),
        listScreenRows({ screenRunId, page: rowPage, pageSize: rowPageSize, sort: rowSort, direction: rowDirection }),
        listScreenExclusions({ screenRunId, page: exclusionPage, pageSize: 25 }),
      ]);
      setScreenRun(screenPayload);
      setRows(rowPayload.results);
      setExclusions(exclusionPayload.results);
      setRowCount(rowPayload.count);
      setExclusionCount(exclusionPayload.count);
    } catch (refreshError) {
      setError(formatApiError(refreshError, "Unable to refresh the screen run."));
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

  const rowPageCount = Math.max(1, Math.ceil(rowCount / rowPageSize));
  const exclusionPageCount = Math.max(1, Math.ceil(exclusionCount / 25));

  return (
    <main style={pageStyle}>
      <section style={panelStyle}>
        <div style={headerRowStyle}>
          <div>
            <p style={eyebrowStyle}>Screen Run</p>
            <h1 style={titleStyle}>#{screenRun.id} · {screenRun.universe.name}</h1>
          </div>
          <div style={actionRowStyle}>
            <Link href="/app/screens" style={ghostLinkStyle}>
              All screens
            </Link>
            <Link href={`/app/universes/${screenRun.universe.id}`} style={ghostLinkStyle}>
              Universe
            </Link>
            <Link href={`/app/screens?draft_screen_run_id=${screenRun.id}`} style={ghostLinkStyle}>
              Duplicate as draft
            </Link>
            <Link href="/app/history" style={ghostLinkStyle}>
              History
            </Link>
            <Link href="/app/templates" style={ghostLinkStyle}>
              Templates
            </Link>
            <Link href="/app/jobs" style={ghostLinkStyle}>
              Jobs
            </Link>
          </div>
        </div>

        <p style={bodyStyle}>
          Workspace: <strong>{screenRun.workspace.name}</strong>. Job status is persisted separately,
          so the ranked results and exclusions remain available after refresh or re-login.
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
          <div style={summaryCardStyle}>
            <p style={sectionLabelStyle}>Ranked rows</p>
            <h2 style={summaryTitleStyle}>{screenRun.result_count.toLocaleString()}</h2>
            <p style={metaStyle}>{screenRun.total_candidate_count.toLocaleString()} total candidates</p>
          </div>
          <div style={summaryCardStyle}>
            <p style={sectionLabelStyle}>Exclusions</p>
            <h2 style={summaryTitleStyle}>{screenRun.exclusion_count.toLocaleString()}</h2>
            <p style={metaStyle}>{screenRun.resolved_ticker_count.toLocaleString()} tickers screened</p>
          </div>
          <div style={summaryCardStyle}>
            <p style={sectionLabelStyle}>Configuration</p>
            <h2 style={summaryTitleStyle}>{screenRun.momentum_mode}</h2>
            <p style={metaStyle}>Top {screenRun.top_n} | Cache TTL {screenRun.cache_ttl_hours}h</p>
          </div>
          <div style={summaryCardStyle}>
            <p style={sectionLabelStyle}>Export</p>
            <h2 style={summaryTitleStyle}>{screenRun.export?.filename ?? "Pending"}</h2>
            {screenRun.export ? (
              <a href={screenRun.export.download_url} style={primaryLinkStyle}>
                Download CSV
              </a>
            ) : (
              <p style={metaStyle}>Export will be available when the run finishes.</p>
            )}
          </div>
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
              </div>
            </div>
            <div style={tableWrapperStyle}>
              <table style={tableStyle}>
                <thead>
                  <tr>
                    <th style={headerCellStyle}>#</th>
                    <th style={headerCellStyle}>Ticker</th>
                    <th style={headerCellStyle}>Company</th>
                    <th style={headerCellStyle}>ROC</th>
                    <th style={headerCellStyle}>EY</th>
                    <th style={headerCellStyle}>Momentum</th>
                    <th style={headerCellStyle}>Final</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.length === 0 ? (
                    <tr>
                      <td style={emptyCellStyle} colSpan={7}>
                        {screenRun.job.is_terminal ? "No ranked rows were persisted." : "Rows will appear once the run finishes."}
                      </td>
                    </tr>
                  ) : (
                    rows.map((row) => (
                      <tr key={row.id}>
                        <td style={cellStyle}>{row.position}</td>
                        <td style={tickerCellStyle}>{row.ticker}</td>
                        <td style={cellStyle}>{row.company_name ?? "-"}</td>
                        <td style={cellStyle}>{formatNumber(row.return_on_capital)}</td>
                        <td style={cellStyle}>{formatNumber(row.earnings_yield)}</td>
                        <td style={cellStyle}>{formatNumber(row.momentum_6m)}</td>
                        <td style={cellStyle}>{row.final_score ?? "-"}</td>
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
                onClick={() => setRowPage((value) => Math.max(1, value - 1))}
                disabled={rowPage <= 1}
              >
                Previous
              </button>
              <span style={metaStyle}>Page {rowPage} of {rowPageCount}</span>
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

          <section style={sectionCardStyle}>
            <div style={tableHeaderStyle}>
              <div>
                <p style={sectionLabelStyle}>Exclusions</p>
                <h2 style={tableTitleStyle}>{exclusionCount.toLocaleString()} rows</h2>
              </div>
              <span style={pillStyle}>First page sorted by ticker</span>
            </div>
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
              <span style={metaStyle}>Page {exclusionPage} of {exclusionPageCount}</span>
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
  width: "min(1440px, 100%)",
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
  gap: "0.65rem",
  alignContent: "start",
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

const layoutStyle: CSSProperties = {
  display: "grid",
  gap: "1rem",
  gridTemplateColumns: "minmax(0, 1.35fr) minmax(320px, 0.9fr)",
  marginTop: "1.5rem",
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

const toolbarStyle: CSSProperties = {
  display: "flex",
  gap: "0.65rem",
  flexWrap: "wrap",
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

const summaryTitleStyle: CSSProperties = {
  margin: 0,
  fontSize: "1.8rem",
};

const statusTitleStyle: CSSProperties = {
  margin: "0.45rem 0 0",
  fontSize: "1.7rem",
  textTransform: "capitalize",
};

const tableTitleStyle: CSSProperties = {
  margin: "0.45rem 0 0",
  fontSize: "1.4rem",
};

const metaStyle: CSSProperties = {
  margin: 0,
  color: "#496280",
  lineHeight: 1.5,
};

const progressTrackStyle: CSSProperties = {
  width: "100%",
  height: "14px",
  borderRadius: "999px",
  background: "#dbe5ef",
  overflow: "hidden",
  marginTop: "1rem",
};

const progressFillStyle: CSSProperties = {
  height: "100%",
  borderRadius: "999px",
  background: "linear-gradient(90deg, #162132, #496280)",
};

const progressMetaStyle: CSSProperties = {
  marginTop: "0.6rem",
  display: "flex",
  justifyContent: "space-between",
  gap: "1rem",
  color: "#496280",
  flexWrap: "wrap",
};

const pillStyle: CSSProperties = {
  alignSelf: "flex-start",
  padding: "0.4rem 0.7rem",
  borderRadius: "999px",
  background: "#e5edf6",
  color: "#3d556f",
  fontSize: "0.88rem",
};
