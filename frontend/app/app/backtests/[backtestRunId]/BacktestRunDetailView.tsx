"use client";

import { startTransition, useEffect, useState, type CSSProperties, type SVGProps } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import {
  ApiError,
  getBacktestRun,
  getCurrentUser,
  listBacktestEquityPoints,
  listBacktestFinalHoldings,
  listBacktestReviewTargets,
  listBacktestTrades,
  type BacktestEquityPoint,
  type BacktestFinalHolding,
  type BacktestReviewTarget,
  type BacktestRun,
  type BacktestTrade,
} from "@/lib/api";

type LoadState = "loading" | "ready" | "error";

type BacktestRunDetailViewProps = {
  backtestRunId: number;
};


export function BacktestRunDetailView({ backtestRunId }: BacktestRunDetailViewProps) {
  const router = useRouter();
  const [backtestRun, setBacktestRun] = useState<BacktestRun | null>(null);
  const [equityPoints, setEquityPoints] = useState<BacktestEquityPoint[]>([]);
  const [trades, setTrades] = useState<BacktestTrade[]>([]);
  const [tradeCount, setTradeCount] = useState(0);
  const [reviewTargets, setReviewTargets] = useState<BacktestReviewTarget[]>([]);
  const [reviewTargetCount, setReviewTargetCount] = useState(0);
  const [finalHoldings, setFinalHoldings] = useState<BacktestFinalHolding[]>([]);
  const [finalHoldingCount, setFinalHoldingCount] = useState(0);
  const [tradePage, setTradePage] = useState(1);
  const [tradePageSize, setTradePageSize] = useState(25);
  const [tradeSort, setTradeSort] = useState("position");
  const [tradeDirection, setTradeDirection] = useState<"asc" | "desc">("asc");
  const [reviewTargetPage, setReviewTargetPage] = useState(1);
  const [reviewTargetPageSize, setReviewTargetPageSize] = useState(25);
  const [reviewTargetSort, setReviewTargetSort] = useState("position");
  const [reviewTargetDirection, setReviewTargetDirection] = useState<"asc" | "desc">("asc");
  const [holdingSort, setHoldingSort] = useState("position");
  const [holdingDirection, setHoldingDirection] = useState<"asc" | "desc">("asc");
  const [state, setState] = useState<LoadState>("loading");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;

    async function load() {
      try {
        await getCurrentUser();
        const payloads = await loadDetailPayloads(backtestRunId, {
          tradePage,
          tradePageSize,
          tradeSort,
          tradeDirection,
          reviewTargetPage,
          reviewTargetPageSize,
          reviewTargetSort,
          reviewTargetDirection,
          holdingSort,
          holdingDirection,
        });
        if (!active) {
          return;
        }
        applyPayloads(payloads);
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
        setError(loadError instanceof Error ? loadError.message : "Unable to load the backtest run.");
        setState("error");
      }
    }

    void load();

    return () => {
      active = false;
    };
  }, [
    backtestRunId,
    holdingDirection,
    holdingSort,
    reviewTargetDirection,
    reviewTargetPage,
    reviewTargetPageSize,
    reviewTargetSort,
    router,
    tradeDirection,
    tradePage,
    tradePageSize,
    tradeSort,
  ]);

  useEffect(() => {
    if (backtestRun == null || backtestRun.job.is_terminal || state !== "ready") {
      return undefined;
    }

    const intervalId = window.setInterval(() => {
      void refreshDetail();
    }, 2000);

    return () => {
      window.clearInterval(intervalId);
    };
  }, [backtestRun, state]);

  async function refreshDetail() {
    try {
      const payloads = await loadDetailPayloads(backtestRunId, {
        tradePage,
        tradePageSize,
        tradeSort,
        tradeDirection,
        reviewTargetPage,
        reviewTargetPageSize,
        reviewTargetSort,
        reviewTargetDirection,
        holdingSort,
        holdingDirection,
      });
      applyPayloads(payloads);
    } catch (refreshError) {
      setError(formatApiError(refreshError, "Unable to refresh the backtest run."));
    }
  }

  function applyPayloads(payloads: Awaited<ReturnType<typeof loadDetailPayloads>>) {
    setBacktestRun(payloads.run);
    setEquityPoints(payloads.equity.results);
    setTrades(payloads.trades.results);
    setTradeCount(payloads.trades.count);
    setReviewTargets(payloads.reviewTargets.results);
    setReviewTargetCount(payloads.reviewTargets.count);
    setFinalHoldings(payloads.finalHoldings.results);
    setFinalHoldingCount(payloads.finalHoldings.count);
  }

  if (state === "loading") {
    return (
      <main style={pageStyle}>
        <section style={panelStyle}>
          <p style={eyebrowStyle}>Backtest Run</p>
          <h1 style={titleStyle}>Loading persisted backtest results</h1>
        </section>
      </main>
    );
  }

  if (state === "error" || backtestRun == null) {
    return (
      <main style={pageStyle}>
        <section style={panelStyle}>
          <p style={eyebrowStyle}>Backtest Run</p>
          <h1 style={titleStyle}>Backtest unavailable</h1>
          <p style={bodyStyle}>{error ?? "Unable to load this backtest run."}</p>
          <div style={actionRowStyle}>
            <Link href="/app/backtests" style={primaryLinkStyle}>
              Back to backtests
            </Link>
          </div>
        </section>
      </main>
    );
  }

  const tradePageCount = Math.max(1, Math.ceil(tradeCount / tradePageSize));
  const reviewTargetPageCount = Math.max(1, Math.ceil(reviewTargetCount / reviewTargetPageSize));
  const chartData = buildChartSeries(equityPoints);

  return (
    <main style={pageStyle}>
      <section style={panelStyle}>
        <div style={headerRowStyle}>
          <div>
            <p style={eyebrowStyle}>Backtest Run</p>
            <h1 style={titleStyle}>#{backtestRun.id} · {backtestRun.universe.name}</h1>
          </div>
          <div style={actionRowStyle}>
            <Link href="/app/backtests" style={ghostLinkStyle}>
              All backtests
            </Link>
            <Link href={`/app/universes/${backtestRun.universe.id}`} style={ghostLinkStyle}>
              Universe
            </Link>
            <Link href={`/app/backtests?draft_backtest_run_id=${backtestRun.id}`} style={ghostLinkStyle}>
              Duplicate as draft
            </Link>
            <Link href="/app/history" style={ghostLinkStyle}>
              History
            </Link>
            <Link href="/app/templates" style={ghostLinkStyle}>
              Templates
            </Link>
            <Link href="/app/screens" style={ghostLinkStyle}>
              Screens
            </Link>
          </div>
        </div>

        <p style={bodyStyle}>
          Workspace: <strong>{backtestRun.workspace.name}</strong>. The full equity curve, trades,
          review targets, and final holdings are persisted, so the result remains inspectable after
          refresh or re-login.
        </p>

        {error ? <p style={errorStyle}>{error}</p> : null}

        <div style={statusCardStyle}>
          <div style={statusHeaderStyle}>
            <div>
              <p style={sectionLabelStyle}>Job state</p>
              <h2 style={statusTitleStyle}>{backtestRun.job.state.replaceAll("_", " ")}</h2>
            </div>
            <span style={stateBadgeStyle(backtestRun.job.state)}>{backtestRun.job.state.replaceAll("_", " ")}</span>
          </div>
          <div style={progressTrackStyle}>
            <div style={{ ...progressFillStyle, width: `${Math.max(6, backtestRun.job.progress_percent)}%` }} />
          </div>
          <div style={progressMetaStyle}>
            <span>{backtestRun.job.progress_percent}%</span>
            <span>{backtestRun.job.current_step || "Pending"}</span>
          </div>
        </div>

        <div style={summaryGridStyle}>
          <SummaryCard label="Total return" value={formatPercent(backtestRun.summary.total_return)} detail={`${backtestRun.start_date} to ${backtestRun.end_date}`} />
          <SummaryCard label="Annualized" value={formatPercent(backtestRun.summary.annualized_return)} detail={`Max drawdown ${formatPercent(backtestRun.summary.max_drawdown)}`} />
          <SummaryCard label="Ending equity" value={formatCurrency(backtestRun.summary.ending_equity)} detail={`${backtestRun.summary.ending_positions ?? "-"} ending positions`} />
          <SummaryCard
            label="Benchmark"
            value={formatPercent(backtestRun.summary.benchmark_return)}
            detail={`Alpha ${formatPercent(backtestRun.summary.alpha_vs_benchmark)}`}
          />
          <SummaryCard label="Trades" value={String(backtestRun.trade_count)} detail={`${backtestRun.review_target_count} review targets`} />
          <SummaryCard label="Export" value={backtestRun.export?.filename ?? "Pending"} detail={backtestRun.export ? "Artifact ready" : "Available when complete"} />
        </div>

        <div style={chartCardStyle}>
          <div style={tableHeaderStyle}>
            <div>
              <p style={sectionLabelStyle}>Equity curve</p>
              <h2 style={tableTitleStyle}>{equityPoints.length.toLocaleString()} points</h2>
            </div>
            {backtestRun.export ? (
              <a href={backtestRun.export.download_url} style={primaryLinkStyle}>
                Download artifacts
              </a>
            ) : null}
          </div>
          {chartData == null ? (
            <p style={bodyStyle}>
              {backtestRun.job.is_terminal ? "No equity points were persisted." : "Equity curve will appear once the run finishes."}
            </p>
          ) : (
            <div style={{ display: "grid", gap: "0.85rem" }}>
              <EquityCurveChart data={chartData} />
              <div style={legendStyle}>
                <span style={legendItemStyle}><span style={{ ...legendLineStyle, background: "#162132" }} />Strategy</span>
                {chartData.hasBenchmark ? (
                  <span style={legendItemStyle}><span style={{ ...legendLineStyle, background: "#5d8dc0" }} />Benchmark</span>
                ) : null}
              </div>
            </div>
          )}
        </div>

        <div style={layoutStyle}>
          <section style={sectionCardStyle}>
            <div style={tableHeaderStyle}>
              <div>
                <p style={sectionLabelStyle}>Trades</p>
                <h2 style={tableTitleStyle}>{tradeCount.toLocaleString()} rows</h2>
              </div>
              <div style={toolbarStyle}>
                <select value={tradeSort} onChange={(event) => setTradeSort(event.target.value)} style={compactInputStyle}>
                  <option value="position">Position</option>
                  <option value="date">Date</option>
                  <option value="ticker">Ticker</option>
                  <option value="side">Side</option>
                  <option value="shares">Shares</option>
                  <option value="price">Price</option>
                  <option value="proceeds">Proceeds</option>
                </select>
                <select value={tradeDirection} onChange={(event) => setTradeDirection(event.target.value as "asc" | "desc")} style={compactInputStyle}>
                  <option value="asc">Ascending</option>
                  <option value="desc">Descending</option>
                </select>
              </div>
            </div>
            <DataTable
              headers={["Date", "Ticker", "Side", "Shares", "Price", "Proceeds", "Reason"]}
              rows={trades.map((trade) => [
                trade.date,
                trade.ticker,
                trade.side,
                formatNumber(trade.shares),
                formatCurrency(trade.price),
                formatCurrency(trade.proceeds),
                trade.reason,
              ])}
              emptyMessage={backtestRun.job.is_terminal ? "No trades were persisted." : "Trades will appear once the run finishes."}
            />
            <div style={paginationStyle}>
              <button type="button" style={ghostButtonStyle} onClick={() => setTradePage((value) => Math.max(1, value - 1))} disabled={tradePage <= 1}>
                Previous
              </button>
              <span style={metaStyle}>Page {tradePage} of {tradePageCount}</span>
              <button type="button" style={ghostButtonStyle} onClick={() => setTradePage((value) => Math.min(tradePageCount, value + 1))} disabled={tradePage >= tradePageCount}>
                Next
              </button>
            </div>
          </section>

          <section style={sectionCardStyle}>
            <div style={tableHeaderStyle}>
              <div>
                <p style={sectionLabelStyle}>Review targets</p>
                <h2 style={tableTitleStyle}>{reviewTargetCount.toLocaleString()} rows</h2>
              </div>
              <div style={toolbarStyle}>
                <select value={reviewTargetSort} onChange={(event) => setReviewTargetSort(event.target.value)} style={compactInputStyle}>
                  <option value="position">Position</option>
                  <option value="date">Date</option>
                  <option value="target_rank">Target rank</option>
                  <option value="ticker">Ticker</option>
                  <option value="final_score">Final score</option>
                </select>
                <select
                  value={reviewTargetDirection}
                  onChange={(event) => setReviewTargetDirection(event.target.value as "asc" | "desc")}
                  style={compactInputStyle}
                >
                  <option value="asc">Ascending</option>
                  <option value="desc">Descending</option>
                </select>
              </div>
            </div>
            <DataTable
              headers={["Date", "Rank", "Ticker", "Company", "Final", "Composite"]}
              rows={reviewTargets.map((target) => [
                target.date,
                String(target.target_rank),
                target.ticker,
                target.company_name ?? "-",
                target.final_score == null ? "-" : String(target.final_score),
                target.composite_score == null ? "-" : String(target.composite_score),
              ])}
              emptyMessage={backtestRun.job.is_terminal ? "No review targets were persisted." : "Review targets will appear once the run finishes."}
            />
            <div style={paginationStyle}>
              <button type="button" style={ghostButtonStyle} onClick={() => setReviewTargetPage((value) => Math.max(1, value - 1))} disabled={reviewTargetPage <= 1}>
                Previous
              </button>
              <span style={metaStyle}>Page {reviewTargetPage} of {reviewTargetPageCount}</span>
              <button
                type="button"
                style={ghostButtonStyle}
                onClick={() => setReviewTargetPage((value) => Math.min(reviewTargetPageCount, value + 1))}
                disabled={reviewTargetPage >= reviewTargetPageCount}
              >
                Next
              </button>
            </div>
          </section>
        </div>

        <section style={sectionCardStyle}>
          <div style={tableHeaderStyle}>
            <div>
              <p style={sectionLabelStyle}>Final holdings</p>
              <h2 style={tableTitleStyle}>{finalHoldingCount.toLocaleString()} rows</h2>
            </div>
            <div style={toolbarStyle}>
              <select value={holdingSort} onChange={(event) => setHoldingSort(event.target.value)} style={compactInputStyle}>
                <option value="position">Position</option>
                <option value="ticker">Ticker</option>
                <option value="shares">Shares</option>
                <option value="entry_date">Entry date</option>
                <option value="entry_price">Entry price</option>
                <option value="score">Score</option>
              </select>
              <select value={holdingDirection} onChange={(event) => setHoldingDirection(event.target.value as "asc" | "desc")} style={compactInputStyle}>
                <option value="asc">Ascending</option>
                <option value="desc">Descending</option>
              </select>
            </div>
          </div>
          <DataTable
            headers={["Ticker", "Shares", "Entry date", "Entry price", "Score"]}
            rows={finalHoldings.map((holding) => [
              holding.ticker,
              formatNumber(holding.shares),
              holding.entry_date,
              formatCurrency(holding.entry_price),
              holding.score == null ? "-" : String(holding.score),
            ])}
            emptyMessage={backtestRun.job.is_terminal ? "No final holdings were persisted." : "Final holdings will appear once the run finishes."}
          />
        </section>
      </section>
    </main>
  );
}

async function loadDetailPayloads(
  backtestRunId: number,
  options: {
    tradePage: number;
    tradePageSize: number;
    tradeSort: string;
    tradeDirection: "asc" | "desc";
    reviewTargetPage: number;
    reviewTargetPageSize: number;
    reviewTargetSort: string;
    reviewTargetDirection: "asc" | "desc";
    holdingSort: string;
    holdingDirection: "asc" | "desc";
  },
) {
  const [run, equity, trades, reviewTargets, finalHoldings] = await Promise.all([
    getBacktestRun(backtestRunId),
    listBacktestEquityPoints(backtestRunId),
    listBacktestTrades({
      backtestRunId,
      page: options.tradePage,
      pageSize: options.tradePageSize,
      sort: options.tradeSort,
      direction: options.tradeDirection,
    }),
    listBacktestReviewTargets({
      backtestRunId,
      page: options.reviewTargetPage,
      pageSize: options.reviewTargetPageSize,
      sort: options.reviewTargetSort,
      direction: options.reviewTargetDirection,
    }),
    listBacktestFinalHoldings({
      backtestRunId,
      sort: options.holdingSort,
      direction: options.holdingDirection,
    }),
  ]);
  return { run, equity, trades, reviewTargets, finalHoldings };
}

function buildChartSeries(points: BacktestEquityPoint[]) {
  if (points.length === 0) {
    return null;
  }

  const values = points.flatMap((point) => [point.equity, point.benchmark_equity].filter((value): value is number => value != null));
  const minValue = Math.min(...values);
  const maxValue = Math.max(...values);
  const range = maxValue - minValue || 1;
  const width = 960;
  const height = 320;
  const padding = 24;

  const project = (value: number, index: number) => {
    const x = padding + (index / Math.max(1, points.length - 1)) * (width - padding * 2);
    const y = height - padding - ((value - minValue) / range) * (height - padding * 2);
    return `${x.toFixed(2)},${y.toFixed(2)}`;
  };

  const equityPath = points.map((point, index) => project(point.equity, index)).join(" ");
  const benchmarkPoints = points
    .map((point, index) => (point.benchmark_equity == null ? null : project(point.benchmark_equity, index)))
    .filter((value): value is string => value != null);

  return {
    width,
    height,
    minValue,
    maxValue,
    firstDate: points[0]?.date ?? "",
    lastDate: points[points.length - 1]?.date ?? "",
    equityPath,
    benchmarkPath: benchmarkPoints.join(" "),
    hasBenchmark: benchmarkPoints.length > 1,
  };
}

function EquityCurveChart({
  data,
}: {
  data: NonNullable<ReturnType<typeof buildChartSeries>>;
}) {
  return (
    <svg viewBox={`0 0 ${data.width} ${data.height}`} style={chartStyle}>
      <line x1="24" y1={data.height - 24} x2={data.width - 24} y2={data.height - 24} stroke="#c4d2e0" strokeWidth="1" />
      <line x1="24" y1="24" x2="24" y2={data.height - 24} stroke="#c4d2e0" strokeWidth="1" />
      <polyline fill="none" stroke="#162132" strokeWidth="3" points={data.equityPath} />
      {data.hasBenchmark ? <polyline fill="none" stroke="#5d8dc0" strokeWidth="2.5" strokeDasharray="8 6" points={data.benchmarkPath} /> : null}
      <ChartLabel x={24} y={20} text={formatCurrency(data.maxValue)} />
      <ChartLabel x={24} y={data.height - 4} text={formatCurrency(data.minValue)} />
      <ChartLabel x={24} y={data.height - 6} text={data.firstDate} align="start" />
      <ChartLabel x={data.width - 24} y={data.height - 6} text={data.lastDate} align="end" />
    </svg>
  );
}

function ChartLabel({
  x,
  y,
  text,
  align = "start",
}: {
  x: number;
  y: number;
  text: string;
  align?: SVGProps<SVGTextElement>["textAnchor"];
}) {
  return (
    <text x={x} y={y} fill="#5c728d" fontSize="12" textAnchor={align}>
      {text}
    </text>
  );
}

function DataTable({
  headers,
  rows,
  emptyMessage,
}: {
  headers: string[];
  rows: string[][];
  emptyMessage: string;
}) {
  return (
    <div style={tableWrapperStyle}>
      <table style={tableStyle}>
        <thead>
          <tr>
            {headers.map((header) => (
              <th key={header} style={headerCellStyle}>
                {header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 ? (
            <tr>
              <td style={emptyCellStyle} colSpan={headers.length}>
                {emptyMessage}
              </td>
            </tr>
          ) : (
            rows.map((row, index) => (
              <tr key={`${row[0]}-${index}`}>
                {row.map((value, valueIndex) => (
                  <td key={`${valueIndex}-${value}`} style={valueIndex === 1 ? tickerCellStyle : cellStyle}>
                    {value}
                  </td>
                ))}
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
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

function formatPercent(value: unknown): string {
  if (typeof value !== "number") {
    return "-";
  }
  return `${(value * 100).toFixed(2)}%`;
}

function formatCurrency(value: unknown): string {
  if (typeof value !== "number") {
    return "-";
  }
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 }).format(value);
}

function formatNumber(value: number): string {
  return value.toFixed(2);
}

function stateBadgeStyle(state: BacktestRun["job"]["state"]): CSSProperties {
  const palette = {
    queued: { background: "#dde6f0", color: "#162132" },
    running: { background: "#e6f1ff", color: "#0f4c81" },
    succeeded: { background: "#e2f3e7", color: "#17663a" },
    failed: { background: "#ffe5e0", color: "#8f2622" },
    cancelled: { background: "#f1ecdf", color: "#6b5a19" },
    partial_failed: { background: "#fff2d9", color: "#8b5c00" },
  } satisfies Record<BacktestRun["job"]["state"], { background: string; color: string }>;
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

const chartCardStyle: CSSProperties = {
  marginTop: "1.5rem",
  padding: "1.25rem",
  borderRadius: "22px",
  background: "#f8fbff",
  border: "1px solid rgba(73, 98, 128, 0.18)",
};

const chartStyle: CSSProperties = {
  width: "100%",
  height: "320px",
  background: "#fff",
  borderRadius: "20px",
  border: "1px solid rgba(73, 98, 128, 0.16)",
};

const legendStyle: CSSProperties = {
  display: "flex",
  gap: "1rem",
  flexWrap: "wrap",
};

const legendItemStyle: CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  gap: "0.45rem",
  color: "#496280",
};

const legendLineStyle: CSSProperties = {
  display: "inline-block",
  width: "24px",
  height: "3px",
  borderRadius: "999px",
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

const compactInputStyle: CSSProperties = {
  borderRadius: "12px",
  border: "1px solid rgba(73, 98, 128, 0.25)",
  padding: "0.7rem 0.8rem",
  background: "#fff",
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
