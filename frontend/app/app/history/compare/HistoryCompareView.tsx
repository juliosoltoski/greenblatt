"use client";

import { startTransition, useEffect, useMemo, useState, type CSSProperties } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import {
  ApiError,
  getBacktestRun,
  getCurrentUser,
  getScreenRun,
  listBacktestFinalHoldings,
  listScreenRows,
  type BacktestFinalHolding,
  type BacktestRun,
  type ScreenResultRow,
  type ScreenRun,
} from "@/lib/api";

type LoadState = "loading" | "ready" | "error";

type HistoryCompareViewProps = {
  kind: "screen" | "backtest";
  leftId: number;
  rightId: number;
};


export function HistoryCompareView({ kind, leftId, rightId }: HistoryCompareViewProps) {
  const router = useRouter();
  const [screenRuns, setScreenRuns] = useState<[ScreenRun, ScreenRun] | null>(null);
  const [screenRows, setScreenRows] = useState<[ScreenResultRow[], ScreenResultRow[]] | null>(null);
  const [backtestRuns, setBacktestRuns] = useState<[BacktestRun, BacktestRun] | null>(null);
  const [backtestHoldings, setBacktestHoldings] = useState<[BacktestFinalHolding[], BacktestFinalHolding[]] | null>(null);
  const [state, setState] = useState<LoadState>("loading");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;

    async function load() {
      if (!Number.isFinite(leftId) || !Number.isFinite(rightId)) {
        setError("Two valid run ids are required for comparison.");
        setState("error");
        return;
      }
      try {
        await getCurrentUser();
        if (kind === "screen") {
          const [leftRun, rightRun, leftRows, rightRows] = await Promise.all([
            getScreenRun(leftId),
            getScreenRun(rightId),
            listScreenRows({ screenRunId: leftId, pageSize: 10 }),
            listScreenRows({ screenRunId: rightId, pageSize: 10 }),
          ]);
          if (!active) {
            return;
          }
          setScreenRuns([leftRun, rightRun]);
          setScreenRows([leftRows.results, rightRows.results]);
        } else {
          const [leftRun, rightRun, leftHoldings, rightHoldings] = await Promise.all([
            getBacktestRun(leftId),
            getBacktestRun(rightId),
            listBacktestFinalHoldings({ backtestRunId: leftId, pageSize: 100 }),
            listBacktestFinalHoldings({ backtestRunId: rightId, pageSize: 100 }),
          ]);
          if (!active) {
            return;
          }
          setBacktestRuns([leftRun, rightRun]);
          setBacktestHoldings([leftHoldings.results, rightHoldings.results]);
        }
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
        setError(loadError instanceof Error ? loadError.message : "Unable to compare these runs.");
        setState("error");
      }
    }

    void load();

    return () => {
      active = false;
    };
  }, [kind, leftId, rightId, router]);

  const screenComparison = useMemo(() => {
    if (screenRuns == null || screenRows == null) {
      return null;
    }
    const leftTickers = screenRows[0].map((row) => row.ticker);
    const rightTickers = screenRows[1].map((row) => row.ticker);
    const rightSet = new Set(rightTickers);
    const leftSet = new Set(leftTickers);
    return {
      overlap: leftTickers.filter((ticker) => rightSet.has(ticker)),
      leftOnly: leftTickers.filter((ticker) => !rightSet.has(ticker)),
      rightOnly: rightTickers.filter((ticker) => !leftSet.has(ticker)),
    };
  }, [screenRows, screenRuns]);

  const backtestComparison = useMemo(() => {
    if (backtestRuns == null || backtestHoldings == null) {
      return null;
    }
    const leftTickers = backtestHoldings[0].map((holding) => holding.ticker);
    const rightTickers = backtestHoldings[1].map((holding) => holding.ticker);
    const rightSet = new Set(rightTickers);
    const leftSet = new Set(leftTickers);
    return {
      overlap: leftTickers.filter((ticker) => rightSet.has(ticker)),
      leftOnly: leftTickers.filter((ticker) => !rightSet.has(ticker)),
      rightOnly: rightTickers.filter((ticker) => !leftSet.has(ticker)),
    };
  }, [backtestHoldings, backtestRuns]);

  function handleExportComparison() {
    const payload =
      kind === "screen"
        ? { kind, runs: screenRuns, comparison: screenComparison, rows: screenRows }
        : { kind, runs: backtestRuns, comparison: backtestComparison, holdings: backtestHoldings };
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
    const url = window.URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `${kind}-comparison-${leftId}-vs-${rightId}.json`;
    anchor.click();
    window.URL.revokeObjectURL(url);
  }

  if (state === "loading") {
    return (
      <main style={pageStyle}>
        <section style={panelStyle}>
          <p style={eyebrowStyle}>Comparison</p>
          <h1 style={titleStyle}>Loading the selected runs</h1>
        </section>
      </main>
    );
  }

  if (state === "error") {
    return (
      <main style={pageStyle}>
        <section style={panelStyle}>
          <p style={eyebrowStyle}>Comparison</p>
          <h1 style={titleStyle}>Comparison unavailable</h1>
          <p style={bodyStyle}>{error ?? "Unable to compare these runs."}</p>
          <Link href="/app/history" style={primaryLinkStyle}>
            Back to history
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
            <p style={eyebrowStyle}>Comparison</p>
            <h1 style={titleStyle}>{kind === "screen" ? "Screen runs" : "Backtest runs"} side by side</h1>
          </div>
          <div style={actionRowStyle}>
            <Link href="/app/history" style={ghostLinkStyle}>
              History
            </Link>
            <Link href="/app/templates" style={ghostLinkStyle}>
              Templates
            </Link>
            <button type="button" style={buttonStyle} onClick={handleExportComparison}>
              Export comparison
            </button>
          </div>
        </div>

        {kind === "screen" && screenRuns && screenComparison ? (
          <>
            <div style={summaryGridStyle}>
              <ComparisonCard label={`Run #${screenRuns[0].id}`} primary={screenRuns[0].universe.name} detail={`${screenRuns[0].result_count} rows · ${screenRuns[0].exclusion_count} exclusions`} />
              <ComparisonCard label={`Run #${screenRuns[1].id}`} primary={screenRuns[1].universe.name} detail={`${screenRuns[1].result_count} rows · ${screenRuns[1].exclusion_count} exclusions`} />
              <ComparisonCard label="Top-10 overlap" primary={String(screenComparison.overlap.length)} detail={screenComparison.overlap.join(", ") || "None"} />
              <ComparisonCard
                label="Result delta"
                primary={`${screenRuns[0].result_count - screenRuns[1].result_count > 0 ? "+" : ""}${screenRuns[0].result_count - screenRuns[1].result_count}`}
                detail={`Exclusion delta ${screenRuns[0].exclusion_count - screenRuns[1].exclusion_count > 0 ? "+" : ""}${screenRuns[0].exclusion_count - screenRuns[1].exclusion_count}`}
              />
            </div>
            <div style={layoutStyle}>
              <CompareList title="Left only" values={screenComparison.leftOnly} />
              <CompareList title="Overlap" values={screenComparison.overlap} />
              <CompareList title="Right only" values={screenComparison.rightOnly} />
            </div>
          </>
        ) : null}

        {kind === "backtest" && backtestRuns && backtestComparison ? (
          <>
            <div style={summaryGridStyle}>
              <ComparisonCard label={`Run #${backtestRuns[0].id}`} primary={formatPercent(backtestRuns[0].summary.total_return)} detail={`Trades ${backtestRuns[0].trade_count} · Max DD ${formatPercent(backtestRuns[0].summary.max_drawdown)}`} />
              <ComparisonCard label={`Run #${backtestRuns[1].id}`} primary={formatPercent(backtestRuns[1].summary.total_return)} detail={`Trades ${backtestRuns[1].trade_count} · Max DD ${formatPercent(backtestRuns[1].summary.max_drawdown)}`} />
              <ComparisonCard label="Final holdings overlap" primary={String(backtestComparison.overlap.length)} detail={backtestComparison.overlap.join(", ") || "None"} />
              <ComparisonCard
                label="Alpha delta"
                primary={formatSignedPercent(asNumber(backtestRuns[0].summary.alpha_vs_benchmark) - asNumber(backtestRuns[1].summary.alpha_vs_benchmark))}
                detail={`Trade delta ${backtestRuns[0].trade_count - backtestRuns[1].trade_count > 0 ? "+" : ""}${backtestRuns[0].trade_count - backtestRuns[1].trade_count}`}
              />
            </div>
            <div style={layoutStyle}>
              <CompareList title="Left only" values={backtestComparison.leftOnly} />
              <CompareList title="Overlap" values={backtestComparison.overlap} />
              <CompareList title="Right only" values={backtestComparison.rightOnly} />
            </div>
          </>
        ) : null}
      </section>
    </main>
  );
}

function CompareList({ title, values }: { title: string; values: string[] }) {
  return (
    <section style={listCardStyle}>
      <p style={sectionLabelStyle}>{title}</p>
      {values.length === 0 ? (
        <p style={bodyStyle}>None</p>
      ) : (
        <ul style={listStyle}>
          {values.map((value) => (
            <li key={value} style={listItemStyle}>{value}</li>
          ))}
        </ul>
      )}
    </section>
  );
}

function ComparisonCard({ label, primary, detail }: { label: string; primary: string; detail: string }) {
  return (
    <div style={summaryCardStyle}>
      <p style={sectionLabelStyle}>{label}</p>
      <h2 style={summaryTitleStyle}>{primary}</h2>
      <p style={metaStyle}>{detail}</p>
    </div>
  );
}

function formatPercent(value: unknown): string {
  if (typeof value !== "number") {
    return "-";
  }
  return `${(value * 100).toFixed(2)}%`;
}

function formatSignedPercent(value: number): string {
  const prefix = value > 0 ? "+" : "";
  return `${prefix}${(value * 100).toFixed(2)}%`;
}

function asNumber(value: unknown): number {
  return typeof value === "number" ? value : 0;
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

const summaryGridStyle: CSSProperties = {
  display: "grid",
  gap: "1rem",
  gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))",
  marginTop: "1.5rem",
};

const summaryCardStyle: CSSProperties = {
  padding: "1.1rem",
  borderRadius: "20px",
  background: "#f8fbff",
  border: "1px solid rgba(73, 98, 128, 0.18)",
};

const layoutStyle: CSSProperties = {
  display: "grid",
  gap: "1rem",
  gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))",
  marginTop: "1.5rem",
};

const listCardStyle: CSSProperties = {
  padding: "1.1rem",
  borderRadius: "20px",
  background: "#f8fbff",
  border: "1px solid rgba(73, 98, 128, 0.18)",
};

const listStyle: CSSProperties = {
  margin: "1rem 0 0",
  paddingLeft: "1.2rem",
  color: "#334862",
};

const listItemStyle: CSSProperties = {
  margin: "0.25rem 0",
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
  lineHeight: 1.6,
  color: "#334862",
};

const metaStyle: CSSProperties = {
  margin: "0.25rem 0",
  color: "#496280",
  lineHeight: 1.5,
};

const sectionLabelStyle: CSSProperties = {
  margin: 0,
  fontSize: "0.82rem",
  letterSpacing: "0.12em",
  textTransform: "uppercase",
  color: "#5c728d",
};

const summaryTitleStyle: CSSProperties = {
  margin: "0.45rem 0 0",
  fontSize: "1.8rem",
};
