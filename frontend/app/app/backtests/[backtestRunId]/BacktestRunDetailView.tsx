"use client";

import { startTransition, useEffect, useEffectEvent, useState, type CSSProperties, type FormEvent, type SVGProps } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import {
  ApiError,
  cancelJob,
  createStrategyTemplate,
  getBacktestRun,
  getCurrentUser,
  listJobEvents,
  listBacktestEquityPoints,
  listBacktestFinalHoldings,
  listBacktestReviewTargets,
  listBacktestTrades,
  updateBacktestRun,
  type BacktestEquityPoint,
  type BacktestFinalHolding,
  type BacktestReviewTarget,
  type BacktestRun,
  type BacktestTrade,
  type JobEvent,
} from "@/lib/api";
import { JobTimeline } from "@/app/app/_components/JobTimeline";
import { ResourceCollaborationPanel } from "@/app/app/_components/ResourceCollaborationPanel";
import { useJobStream } from "@/lib/jobStream";
import { readViewPreference, writeViewPreference } from "@/lib/viewPreferences";

type LoadState = "loading" | "ready" | "error";

type BacktestRunDetailViewProps = {
  backtestRunId: number;
};

type BacktestDetailPreference = {
  tradePageSize: number;
  tradeSort: string;
  tradeDirection: "asc" | "desc";
  reviewTargetPageSize: number;
  reviewTargetSort: string;
  reviewTargetDirection: "asc" | "desc";
  holdingSort: string;
  holdingDirection: "asc" | "desc";
  showBenchmark: boolean;
  showTradeReason: boolean;
  showReviewCompany: boolean;
};

const DEFAULT_DETAIL_PREFERENCE: BacktestDetailPreference = {
  tradePageSize: 25,
  tradeSort: "position",
  tradeDirection: "asc",
  reviewTargetPageSize: 25,
  reviewTargetSort: "position",
  reviewTargetDirection: "asc",
  holdingSort: "position",
  holdingDirection: "asc",
  showBenchmark: true,
  showTradeReason: true,
  showReviewCompany: true,
};


export function BacktestRunDetailView({ backtestRunId }: BacktestRunDetailViewProps) {
  const router = useRouter();
  const [backtestRun, setBacktestRun] = useState<BacktestRun | null>(null);
  const [events, setEvents] = useState<JobEvent[]>([]);
  const [equityPoints, setEquityPoints] = useState<BacktestEquityPoint[]>([]);
  const [trades, setTrades] = useState<BacktestTrade[]>([]);
  const [tradeCount, setTradeCount] = useState(0);
  const [reviewTargets, setReviewTargets] = useState<BacktestReviewTarget[]>([]);
  const [reviewTargetCount, setReviewTargetCount] = useState(0);
  const [finalHoldings, setFinalHoldings] = useState<BacktestFinalHolding[]>([]);
  const [finalHoldingCount, setFinalHoldingCount] = useState(0);
  const [tradePage, setTradePage] = useState(1);
  const [tradePageSize, setTradePageSize] = useState(DEFAULT_DETAIL_PREFERENCE.tradePageSize);
  const [tradeSort, setTradeSort] = useState(DEFAULT_DETAIL_PREFERENCE.tradeSort);
  const [tradeDirection, setTradeDirection] = useState<"asc" | "desc">(DEFAULT_DETAIL_PREFERENCE.tradeDirection);
  const [reviewTargetPage, setReviewTargetPage] = useState(1);
  const [reviewTargetPageSize, setReviewTargetPageSize] = useState(DEFAULT_DETAIL_PREFERENCE.reviewTargetPageSize);
  const [reviewTargetSort, setReviewTargetSort] = useState(DEFAULT_DETAIL_PREFERENCE.reviewTargetSort);
  const [reviewTargetDirection, setReviewTargetDirection] = useState<"asc" | "desc">(DEFAULT_DETAIL_PREFERENCE.reviewTargetDirection);
  const [holdingSort, setHoldingSort] = useState(DEFAULT_DETAIL_PREFERENCE.holdingSort);
  const [holdingDirection, setHoldingDirection] = useState<"asc" | "desc">(DEFAULT_DETAIL_PREFERENCE.holdingDirection);
  const [showBenchmark, setShowBenchmark] = useState(DEFAULT_DETAIL_PREFERENCE.showBenchmark);
  const [showTradeReason, setShowTradeReason] = useState(DEFAULT_DETAIL_PREFERENCE.showTradeReason);
  const [showReviewCompany, setShowReviewCompany] = useState(DEFAULT_DETAIL_PREFERENCE.showReviewCompany);
  const [state, setState] = useState<LoadState>("loading");
  const [error, setError] = useState<string | null>(null);
  const [isStarred, setIsStarred] = useState(false);
  const [tagsText, setTagsText] = useState("");
  const [notes, setNotes] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [isSavingTemplate, setIsSavingTemplate] = useState(false);
  const [jobAction, setJobAction] = useState<"cancel" | null>(null);

  useEffect(() => {
    const preference = readViewPreference<BacktestDetailPreference>("backtest-run-detail", DEFAULT_DETAIL_PREFERENCE);
    setTradePageSize(preference.tradePageSize);
    setTradeSort(preference.tradeSort);
    setTradeDirection(preference.tradeDirection);
    setReviewTargetPageSize(preference.reviewTargetPageSize);
    setReviewTargetSort(preference.reviewTargetSort);
    setReviewTargetDirection(preference.reviewTargetDirection);
    setHoldingSort(preference.holdingSort);
    setHoldingDirection(preference.holdingDirection);
    setShowBenchmark(preference.showBenchmark);
    setShowTradeReason(preference.showTradeReason);
    setShowReviewCompany(preference.showReviewCompany);
  }, []);

  useEffect(() => {
    writeViewPreference("backtest-run-detail", {
      tradePageSize,
      tradeSort,
      tradeDirection,
      reviewTargetPageSize,
      reviewTargetSort,
      reviewTargetDirection,
      holdingSort,
      holdingDirection,
      showBenchmark,
      showTradeReason,
      showReviewCompany,
    });
  }, [
    holdingDirection,
    holdingSort,
    reviewTargetDirection,
    reviewTargetPageSize,
    reviewTargetSort,
    showBenchmark,
    showReviewCompany,
    showTradeReason,
    tradeDirection,
    tradePageSize,
    tradeSort,
  ]);

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

  const handleStreamJob = useEffectEvent((job: BacktestRun["job"]) => {
    setBacktestRun((current) => (current ? { ...current, job } : current));
  });

  const handleStreamEvent = useEffectEvent((event: JobEvent) => {
    setEvents((current) => {
      if (current.some((item) => item.id === event.id)) {
        return current;
      }
      return [...current, event].slice(-120);
    });
  });

  useJobStream({
    jobId: backtestRun?.job.id ?? null,
    enabled: state === "ready" && backtestRun != null && !backtestRun.job.is_terminal,
    onJob: handleStreamJob,
    onEvent: handleStreamEvent,
    onError: () => {
      void refreshDetail();
    },
  });

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
      applyPayloads(payloads, false);
    } catch (refreshError) {
      setError(formatApiError(refreshError, "Unable to refresh the backtest run."));
    }
  }

  function applyPayloads(payloads: Awaited<ReturnType<typeof loadDetailPayloads>>, syncAnnotations: boolean) {
    setBacktestRun(payloads.run);
    setEquityPoints(payloads.equity.results);
    setTrades(payloads.trades.results);
    setTradeCount(payloads.trades.count);
    setReviewTargets(payloads.reviewTargets.results);
    setReviewTargetCount(payloads.reviewTargets.count);
    setFinalHoldings(payloads.finalHoldings.results);
    setFinalHoldingCount(payloads.finalHoldings.count);
    setEvents(payloads.events.results);
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
      const updated = await updateBacktestRun(backtestRunId, {
        isStarred,
        tags: splitTags(tagsText),
        notes,
      });
      setBacktestRun(updated);
      setIsStarred(updated.is_starred);
      setTagsText(updated.tags.join(", "));
      setNotes(updated.notes);
    } catch (saveError) {
      setError(formatApiError(saveError, "Unable to save the backtest annotations."));
    } finally {
      setIsSaving(false);
    }
  }

  async function handlePromoteToTemplate() {
    if (backtestRun == null) {
      return;
    }
    const name = window.prompt("Template name", `Backtest run ${backtestRun.id}`);
    if (name == null || name.trim() === "") {
      return;
    }
    setIsSavingTemplate(true);
    setError(null);
    try {
      await createStrategyTemplate({
        name: name.trim(),
        description: backtestRun.notes || `Saved from backtest run #${backtestRun.id}`,
        sourceBacktestRunId: backtestRun.id,
        isStarred: backtestRun.is_starred,
        tags: backtestRun.tags,
        notes: backtestRun.notes,
      });
      startTransition(() => {
        router.push("/app/templates");
      });
    } catch (templateError) {
      setError(formatApiError(templateError, "Unable to save this backtest as a template."));
    } finally {
      setIsSavingTemplate(false);
    }
  }

  async function handleCancelJob() {
    if (backtestRun == null || backtestRun.job.is_terminal) {
      return;
    }
    setJobAction("cancel");
    setError(null);
    try {
      const updatedJob = await cancelJob(backtestRun.job.id);
      setBacktestRun((current) => (current ? { ...current, job: updatedJob } : current));
      await refreshDetail();
    } catch (cancelError) {
      setError(formatApiError(cancelError, "Unable to request cancellation for this backtest."));
    } finally {
      setJobAction(null);
    }
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
  const dataQuality = extractDataQuality(backtestRun.summary);

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
              Clone as draft
            </Link>
            <button type="button" style={primaryLinkButtonStyle} onClick={() => void handlePromoteToTemplate()} disabled={isSavingTemplate}>
              {isSavingTemplate ? "Saving..." : "Promote to template"}
            </button>
          </div>
        </div>

        <p style={bodyStyle}>
          Workspace: <strong>{backtestRun.workspace.name}</strong>. The full equity curve, trades,
          review targets, and final holdings are persisted, and this page now remembers your table
          preferences so repeated review work is lighter.
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
          <div style={actionRowStyle}>
            {!backtestRun.job.is_terminal ? (
              <button type="button" style={primaryLinkButtonStyle} onClick={() => void handleCancelJob()} disabled={jobAction === "cancel"}>
                {jobAction === "cancel" ? "Requesting..." : "Request cancel"}
              </button>
            ) : null}
            {backtestRun.job.cancellation_requested ? <span style={pillStyle}>Cancellation requested</span> : null}
          </div>
        </div>

        <section style={sectionCardStyle}>
          <p style={sectionLabelStyle}>Job timeline</p>
          <JobTimeline events={events} emptyMessage="Activity appears after the run starts." />
        </section>

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
          <SummaryCard
            label="Research status"
            value={backtestRun.is_starred ? "Starred" : "Standard"}
            detail={
              backtestRun.tags.length > 0
                ? backtestRun.tags.join(", ")
                : "Add tags to group this backtest with related research."
            }
          />
        </div>

        {dataQuality.warningCount > 0 ? (
          <section style={calloutStyle}>
            <p style={sectionLabelStyle}>Data quality</p>
            <h2 style={tableTitleStyle}>{dataQuality.warningCount} warning{dataQuality.warningCount === 1 ? "" : "s"}</h2>
            <div style={stackStyle}>
              {dataQuality.warnings.map((warning) => (
                <div key={warning.code} style={warningRowStyle}>
                  <strong>{warning.code.replaceAll("_", " ")}</strong>
                  <span>{warning.message}</span>
                </div>
              ))}
            </div>
          </section>
        ) : null}

        <div style={detailGridStyle}>
          <section style={sectionCardStyle}>
            <div style={tableHeaderStyle}>
              <div>
                <p style={sectionLabelStyle}>Research notes</p>
                <h2 style={tableTitleStyle}>Bookmark and annotate</h2>
              </div>
              {backtestRun.is_starred ? <span style={starPillStyle}>Starred</span> : null}
            </div>
            <form onSubmit={handleSaveAnnotations} style={formStyle}>
              <label style={fieldStyle}>
                <span style={labelStyle}>Tags</span>
                <input
                  type="text"
                  value={tagsText}
                  onChange={(event) => setTagsText(event.target.value)}
                  placeholder="benchmark, review, keeper"
                  style={inputStyle}
                />
              </label>
              <label style={fieldStyle}>
                <span style={labelStyle}>Notes</span>
                <textarea value={notes} onChange={(event) => setNotes(event.target.value)} rows={6} style={textareaStyle} />
              </label>
              <label style={checkboxFieldStyle}>
                <input type="checkbox" checked={isStarred} onChange={(event) => setIsStarred(event.target.checked)} />
                <span>Star this backtest so it stays easy to find in history</span>
              </label>
              <button type="submit" style={primaryButtonStyle} disabled={isSaving}>
                {isSaving ? "Saving..." : "Save annotations"}
              </button>
            </form>
          </section>

          <section style={sectionCardStyle}>
            <div style={tableHeaderStyle}>
              <div>
                <p style={sectionLabelStyle}>Artifacts</p>
                <h2 style={tableTitleStyle}>{backtestRun.artifacts.length} available</h2>
              </div>
            </div>
            <div style={artifactListStyle}>
              {backtestRun.artifacts.length === 0 ? (
                <p style={bodyStyle}>
                  {backtestRun.job.is_terminal
                    ? "This run finished without saved exports."
                    : "Exports will appear when the run completes."}
                </p>
              ) : (
                backtestRun.artifacts.map((artifact) => (
                  <a key={artifact.download_url} href={artifact.download_url} style={artifactLinkStyle}>
                    <strong>{artifact.label}</strong>
                    <span style={metaStyle}>{artifact.filename}</span>
                  </a>
                ))
              )}
            </div>
          </section>
        </div>

        <div style={chartCardStyle}>
          <div style={tableHeaderStyle}>
            <div>
              <p style={sectionLabelStyle}>Equity curve</p>
              <h2 style={tableTitleStyle}>{equityPoints.length.toLocaleString()} points</h2>
            </div>
            <label style={toggleStyle}>
              <input type="checkbox" checked={showBenchmark} onChange={(event) => setShowBenchmark(event.target.checked)} />
              <span>Show benchmark</span>
            </label>
          </div>
          {chartData == null ? (
            <p style={bodyStyle}>
              {backtestRun.job.is_terminal
                ? "This run finished without an equity curve."
                : "Equity curve will appear when the run completes."}
            </p>
          ) : (
            <div style={{ display: "grid", gap: "0.85rem" }}>
              <EquityCurveChart data={chartData} showBenchmark={showBenchmark} />
              {chartData.sampledCount < chartData.sourceCount ? (
                <p style={metaStyle}>
                  Rendering {chartData.sampledCount.toLocaleString()} sampled points from {chartData.sourceCount.toLocaleString()} persisted equity points to keep the chart responsive.
                </p>
              ) : null}
              <div style={legendStyle}>
                <span style={legendItemStyle}><span style={{ ...legendLineStyle, background: "#162132" }} />Strategy</span>
                {chartData.hasBenchmark && showBenchmark ? (
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
                <select
                  value={tradePageSize}
                  onChange={(event) => {
                    setTradePage(1);
                    setTradePageSize(Number(event.target.value));
                  }}
                  style={compactInputStyle}
                >
                  <option value={10}>10</option>
                  <option value={25}>25</option>
                  <option value={50}>50</option>
                </select>
                <label style={toggleStyle}>
                  <input type="checkbox" checked={showTradeReason} onChange={(event) => setShowTradeReason(event.target.checked)} />
                  <span>Reason</span>
                </label>
              </div>
            </div>
            <DataTable
              headers={[
                "Date",
                "Ticker",
                "Side",
                "Shares",
                "Price",
                "Proceeds",
                ...(showTradeReason ? ["Reason"] : []),
              ]}
              rows={trades.map((trade) => [
                trade.date,
                trade.ticker,
                trade.side,
                formatNumber(trade.shares),
                formatCurrency(trade.price),
                formatCurrency(trade.proceeds),
                ...(showTradeReason ? [trade.reason] : []),
              ])}
              tickerColumnIndex={1}
              emptyMessage={
                backtestRun.job.is_terminal
                  ? "This run finished without saved trades."
                  : "Trades will appear when the run completes."
              }
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
                <select
                  value={reviewTargetPageSize}
                  onChange={(event) => {
                    setReviewTargetPage(1);
                    setReviewTargetPageSize(Number(event.target.value));
                  }}
                  style={compactInputStyle}
                >
                  <option value={10}>10</option>
                  <option value={25}>25</option>
                  <option value={50}>50</option>
                </select>
                <label style={toggleStyle}>
                  <input type="checkbox" checked={showReviewCompany} onChange={(event) => setShowReviewCompany(event.target.checked)} />
                  <span>Company</span>
                </label>
              </div>
            </div>
            <DataTable
              headers={["Date", "Rank", "Ticker", ...(showReviewCompany ? ["Company"] : []), "Final", "Composite"]}
              rows={reviewTargets.map((target) => [
                target.date,
                String(target.target_rank),
                target.ticker,
                ...(showReviewCompany ? [target.company_name ?? "-"] : []),
                target.final_score == null ? "-" : String(target.final_score),
                target.composite_score == null ? "-" : String(target.composite_score),
              ])}
              tickerColumnIndex={2}
              emptyMessage={
                backtestRun.job.is_terminal
                  ? "No review targets were saved for this run."
                  : "Review targets will appear when the run completes."
              }
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
            tickerColumnIndex={0}
            emptyMessage={
              backtestRun.job.is_terminal
                ? "This run finished without final holdings."
                : "Final holdings will appear when the run completes."
            }
          />
        </section>

        <ResourceCollaborationPanel
          workspaceId={backtestRun.workspace.id}
          resourceKind="backtest_run"
          resourceId={backtestRun.id}
        />
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
  const events = await listJobEvents(run.job.id, 120);
  return { run, equity, trades, reviewTargets, finalHoldings, events };
}

function buildChartSeries(points: BacktestEquityPoint[]) {
  if (points.length === 0) {
    return null;
  }

  const sampledPoints = downsamplePoints(points, 180);
  const renderPoints = sampledPoints.length === points.length ? points : sampledPoints;
  const values = renderPoints.flatMap((point) => [point.equity, point.benchmark_equity].filter((value): value is number => value != null));
  const minValue = Math.min(...values);
  const maxValue = Math.max(...values);
  const range = maxValue - minValue || 1;
  const width = 960;
  const height = 320;
  const padding = 24;

  const project = (value: number, index: number) => {
    const x = padding + (index / Math.max(1, renderPoints.length - 1)) * (width - padding * 2);
    const y = height - padding - ((value - minValue) / range) * (height - padding * 2);
    return `${x.toFixed(2)},${y.toFixed(2)}`;
  };

  const equityPath = renderPoints.map((point, index) => project(point.equity, index)).join(" ");
  const benchmarkPoints = renderPoints
    .map((point, index) => (point.benchmark_equity == null ? null : project(point.benchmark_equity, index)))
    .filter((value): value is string => value != null);

  return {
    width,
    height,
    minValue,
    maxValue,
    firstDate: renderPoints[0]?.date ?? "",
    lastDate: renderPoints[renderPoints.length - 1]?.date ?? "",
    equityPath,
    benchmarkPath: benchmarkPoints.join(" "),
    hasBenchmark: benchmarkPoints.length > 1,
    sampledCount: renderPoints.length,
    sourceCount: points.length,
  };
}

function downsamplePoints(points: BacktestEquityPoint[], maxPoints: number): BacktestEquityPoint[] {
  if (points.length <= maxPoints) {
    return points;
  }
  const lastIndex = points.length - 1;
  const step = lastIndex / Math.max(1, maxPoints - 1);
  const sampled: BacktestEquityPoint[] = [];
  for (let index = 0; index < maxPoints; index += 1) {
    const pointIndex = index === maxPoints - 1 ? lastIndex : Math.round(index * step);
    sampled.push(points[pointIndex]);
  }
  return sampled;
}

function EquityCurveChart({
  data,
  showBenchmark,
}: {
  data: NonNullable<ReturnType<typeof buildChartSeries>>;
  showBenchmark: boolean;
}) {
  return (
    <svg viewBox={`0 0 ${data.width} ${data.height}`} style={chartStyle}>
      <line x1="24" y1={data.height - 24} x2={data.width - 24} y2={data.height - 24} stroke="#c4d2e0" strokeWidth="1" />
      <line x1="24" y1="24" x2="24" y2={data.height - 24} stroke="#c4d2e0" strokeWidth="1" />
      <polyline fill="none" stroke="#162132" strokeWidth="3" points={data.equityPath} />
      {data.hasBenchmark && showBenchmark ? <polyline fill="none" stroke="#5d8dc0" strokeWidth="2.5" strokeDasharray="8 6" points={data.benchmarkPath} /> : null}
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
  tickerColumnIndex,
  emptyMessage,
}: {
  headers: string[];
  rows: string[][];
  tickerColumnIndex: number;
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
                  <td key={`${valueIndex}-${value}`} style={valueIndex === tickerColumnIndex ? tickerCellStyle : cellStyle}>
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

function splitTags(value: string): string[] {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
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

function extractDataQuality(summary: Record<string, unknown>): {
  warningCount: number;
  warnings: Array<{ code: string; message: string }>;
} {
  const payload = typeof summary.data_quality === "object" && summary.data_quality != null ? summary.data_quality : null;
  const warningCount =
    payload != null && typeof (payload as { warning_count?: unknown }).warning_count === "number"
      ? ((payload as { warning_count: number }).warning_count ?? 0)
      : 0;
  const warnings = Array.isArray((payload as { warnings?: unknown } | null)?.warnings)
    ? ((payload as { warnings: Array<{ code?: string; message?: string }> }).warnings ?? [])
        .map((warning) => ({
          code: warning.code ?? "warning",
          message: warning.message ?? "A data quality warning was recorded for this run.",
        }))
    : [];
  return { warningCount, warnings };
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

const calloutStyle: CSSProperties = {
  padding: "1.25rem",
  borderRadius: "22px",
  background: "#fff7e8",
  border: "1px solid rgba(201, 140, 0, 0.22)",
  marginTop: "1.5rem",
  display: "grid",
  gap: "0.85rem",
};

const stackStyle: CSSProperties = {
  display: "grid",
  gap: "1rem",
  alignContent: "start",
};

const warningRowStyle: CSSProperties = {
  display: "grid",
  gap: "0.2rem",
  color: "#6a4a00",
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

const detailGridStyle: CSSProperties = {
  display: "grid",
  gap: "1rem",
  gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))",
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

const compactInputStyle: CSSProperties = {
  borderRadius: "12px",
  border: "1px solid rgba(73, 98, 128, 0.25)",
  padding: "0.7rem 0.8rem",
  background: "#fff",
};

const checkboxFieldStyle: CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: "0.55rem",
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

const ghostButtonStyle: CSSProperties = {
  border: 0,
  borderRadius: "999px",
  padding: "0.8rem 1rem",
  background: "#dde6f0",
  color: "#162132",
  cursor: "pointer",
};

const primaryButtonStyle: CSSProperties = {
  border: 0,
  borderRadius: "999px",
  padding: "0.85rem 1rem",
  background: "#162132",
  color: "#f5f7fb",
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

const primaryLinkButtonStyle: CSSProperties = {
  border: 0,
  display: "inline-flex",
  alignItems: "center",
  justifyContent: "center",
  borderRadius: "999px",
  padding: "0.8rem 1rem",
  background: "#162132",
  color: "#f5f7fb",
  cursor: "pointer",
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

const artifactListStyle: CSSProperties = {
  display: "grid",
  gap: "0.75rem",
  marginTop: "1rem",
};

const artifactLinkStyle: CSSProperties = {
  display: "grid",
  gap: "0.25rem",
  padding: "0.95rem 1rem",
  borderRadius: "16px",
  background: "#fff",
  border: "1px solid rgba(73, 98, 128, 0.15)",
  color: "#162132",
  textDecoration: "none",
};

const starPillStyle: CSSProperties = {
  padding: "0.25rem 0.55rem",
  borderRadius: "999px",
  background: "#fff4cc",
  color: "#8b5c00",
  fontSize: "0.82rem",
};

const pillStyle: CSSProperties = {
  padding: "0.3rem 0.65rem",
  borderRadius: "999px",
  background: "#eef4fa",
  color: "#35506b",
  fontSize: "0.82rem",
};
