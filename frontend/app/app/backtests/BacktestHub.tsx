"use client";

import { startTransition, useEffect, useState, type CSSProperties, type FormEvent } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import {
  ApiError,
  getBacktestRun,
  getCurrentUser,
  getStrategyTemplate,
  launchBacktest,
  listBacktests,
  listUniverses,
  type BacktestRun,
  type CurrentUser,
  type StrategyTemplate,
  type UniverseSummary,
} from "@/lib/api";
import { backtestPresets, getBacktestPresetById, isoDateDaysAgo, isoDateYearsAgo } from "@/lib/workflowPresets";

type LoadState = "loading" | "ready" | "error";


function isoDateOffset(daysAgo: number): string {
  const value = new Date();
  value.setDate(value.getDate() - daysAgo);
  return value.toISOString().slice(0, 10);
}


type BacktestHubProps = {
  templateId: number | null;
  draftBacktestRunId: number | null;
  presetId: string | null;
};


export function BacktestHub({ templateId, draftBacktestRunId, presetId }: BacktestHubProps) {
  const router = useRouter();
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [universes, setUniverses] = useState<UniverseSummary[]>([]);
  const [backtests, setBacktests] = useState<BacktestRun[]>([]);
  const [state, setState] = useState<LoadState>("loading");
  const [error, setError] = useState<string | null>(null);
  const [selectedUniverseId, setSelectedUniverseId] = useState<number | null>(null);
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [initialCapital, setInitialCapital] = useState(100000);
  const [portfolioSize, setPortfolioSize] = useState(20);
  const [reviewFrequency, setReviewFrequency] = useState("W-FRI");
  const [benchmark, setBenchmark] = useState("^GSPC");
  const [momentumMode, setMomentumMode] = useState<"none" | "overlay" | "filter">("none");
  const [sectorAllowlist, setSectorAllowlist] = useState("");
  const [minMarketCap, setMinMarketCap] = useState("");
  const [useCache, setUseCache] = useState(true);
  const [refreshCache, setRefreshCache] = useState(false);
  const [cacheTtlHours, setCacheTtlHours] = useState(24);
  const [isLaunching, setIsLaunching] = useState(false);
  const [draftNotice, setDraftNotice] = useState<string | null>(null);
  const [showAdvanced, setShowAdvanced] = useState(false);

  useEffect(() => {
    let active = true;

    async function load() {
      try {
        const currentUser = await getCurrentUser();
        const workspaceId = currentUser.active_workspace?.id;
        const [universePayload, backtestPayload] = await Promise.all([
          listUniverses(workspaceId),
          listBacktests(workspaceId, { limit: 20 }),
        ]);
        if (!active) {
          return;
        }
        setUser(currentUser);
        setUniverses(universePayload.results);
        setBacktests(backtestPayload.results);
        setSelectedUniverseId((currentValue) => currentValue ?? universePayload.results[0]?.id ?? null);
        if (templateId != null && Number.isFinite(templateId) && templateId > 0) {
          const template = await getStrategyTemplate(templateId);
          if (!active) {
            return;
          }
          applyTemplateDraft(template, universePayload.results);
        } else if (draftBacktestRunId != null && Number.isFinite(draftBacktestRunId) && draftBacktestRunId > 0) {
          const priorRun = await getBacktestRun(draftBacktestRunId);
          if (!active) {
            return;
          }
          applyRunDraft(priorRun, universePayload.results);
        } else if (presetId) {
          applyPreset(presetId);
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
        setError(loadError instanceof Error ? loadError.message : "Unable to load backtests.");
        setState("error");
      }
    }

    void load();

    return () => {
      active = false;
    };
  }, [draftBacktestRunId, presetId, router, templateId]);

  useEffect(() => {
    setStartDate((currentValue) => currentValue || isoDateOffset(365 * 2));
    setEndDate((currentValue) => currentValue || isoDateOffset(1));
  }, []);

  useEffect(() => {
    if (user == null || state !== "ready") {
      return undefined;
    }
    if (!backtests.some((backtest) => !backtest.job.is_terminal)) {
      return undefined;
    }

    const intervalId = window.setInterval(() => {
      void refreshBacktests(user);
    }, 2000);

    return () => {
      window.clearInterval(intervalId);
    };
  }, [backtests, state, user]);

  async function refreshBacktests(currentUser: CurrentUser) {
    const workspaceId = currentUser.active_workspace?.id;
    const payload = await listBacktests(workspaceId, { limit: 20 });
    setBacktests(payload.results);
  }

  function applyTemplateDraft(template: StrategyTemplate, availableUniverses: UniverseSummary[]) {
    if (template.workflow_kind !== "backtest") {
      setError("This template belongs to screens, not backtests.");
      return;
    }
    applyBacktestConfig(template.universe.id, template.config, availableUniverses);
    setShowAdvanced(true);
    setDraftNotice(`Template applied: ${template.name}`);
  }

  function applyRunDraft(run: BacktestRun, availableUniverses: UniverseSummary[]) {
    applyBacktestConfig(
      run.universe.id,
      {
        start_date: run.start_date,
        end_date: run.end_date,
        initial_capital: run.initial_capital,
        portfolio_size: run.portfolio_size,
        review_frequency: run.review_frequency,
        benchmark: run.benchmark,
        momentum_mode: run.momentum_mode,
        sector_allowlist: run.sector_allowlist,
        min_market_cap: run.min_market_cap,
        use_cache: run.use_cache,
        refresh_cache: run.refresh_cache,
        cache_ttl_hours: run.cache_ttl_hours,
      },
      availableUniverses,
    );
    setShowAdvanced(true);
    setDraftNotice(`Draft loaded from backtest #${run.id}`);
  }

  function applyPreset(nextPresetId: string) {
    const preset = getBacktestPresetById(nextPresetId);
    if (preset == null) {
      return;
    }
    setStartDate(isoDateYearsAgo(preset.years));
    setEndDate(isoDateDaysAgo(1));
    setInitialCapital(preset.initialCapital);
    setPortfolioSize(preset.portfolioSize);
    setReviewFrequency(preset.reviewFrequency);
    setBenchmark(preset.benchmark);
    setMomentumMode(preset.momentumMode);
    setSectorAllowlist((preset.sectorAllowlist ?? []).join(", "));
    setMinMarketCap(preset.minMarketCap ? String(preset.minMarketCap) : "");
    setUseCache(preset.useCache ?? true);
    setRefreshCache(preset.refreshCache ?? false);
    setCacheTtlHours(preset.cacheTtlHours ?? 24);
    setShowAdvanced(Boolean(preset.sectorAllowlist?.length || preset.minMarketCap));
    setDraftNotice(`Preset applied: ${preset.label}`);
  }

  function applyBacktestConfig(
    universeId: number,
    config: Record<string, unknown>,
    availableUniverses: UniverseSummary[],
  ) {
    const matchingUniverse = availableUniverses.find((universe) => universe.id === universeId);
    setSelectedUniverseId(matchingUniverse?.id ?? universeId);
    if (typeof config.start_date === "string") {
      setStartDate(config.start_date);
    }
    if (typeof config.end_date === "string") {
      setEndDate(config.end_date);
    }
    if (typeof config.initial_capital === "number") {
      setInitialCapital(config.initial_capital);
    }
    if (typeof config.portfolio_size === "number") {
      setPortfolioSize(config.portfolio_size);
    }
    if (typeof config.review_frequency === "string") {
      setReviewFrequency(config.review_frequency);
    }
    if (typeof config.benchmark === "string") {
      setBenchmark(config.benchmark);
    }
    if (config.momentum_mode === "none" || config.momentum_mode === "overlay" || config.momentum_mode === "filter") {
      setMomentumMode(config.momentum_mode);
    }
    if (Array.isArray(config.sector_allowlist)) {
      setSectorAllowlist(config.sector_allowlist.filter((item): item is string => typeof item === "string").join(", "));
    }
    if (typeof config.min_market_cap === "number") {
      setMinMarketCap(String(config.min_market_cap));
    } else if (config.min_market_cap == null) {
      setMinMarketCap("");
    }
    if (typeof config.use_cache === "boolean") {
      setUseCache(config.use_cache);
    }
    if (typeof config.refresh_cache === "boolean") {
      setRefreshCache(config.refresh_cache);
    }
    if (typeof config.cache_ttl_hours === "number") {
      setCacheTtlHours(config.cache_ttl_hours);
    }
  }

  async function handleLaunch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (user?.active_workspace == null) {
      setError("No active workspace is available.");
      return;
    }
    if (selectedUniverseId == null) {
      setError("Create or select a saved universe before launching a backtest.");
      return;
    }

    setIsLaunching(true);
    setError(null);
    try {
      const created = await launchBacktest({
        workspaceId: user.active_workspace.id,
        universeId: selectedUniverseId,
        startDate,
        endDate,
        initialCapital,
        portfolioSize,
        reviewFrequency,
        benchmark,
        momentumMode,
        sectorAllowlist: sectorAllowlist
          .split(",")
          .map((item) => item.trim())
          .filter(Boolean),
        minMarketCap: minMarketCap.trim() === "" ? null : Number(minMarketCap),
        useCache,
        refreshCache,
        cacheTtlHours,
      });
      await refreshBacktests(user);
      startTransition(() => {
        router.push(`/app/backtests/${created.id}`);
      });
    } catch (launchError) {
      setError(formatApiError(launchError, "Unable to launch the backtest."));
    } finally {
      setIsLaunching(false);
    }
  }

  if (state === "loading") {
    return (
      <main style={pageStyle}>
        <section style={panelStyle}>
          <p style={eyebrowStyle}>Backtesting</p>
          <h1 style={titleStyle}>Loading saved universes and prior backtests</h1>
        </section>
      </main>
    );
  }

  if (state === "error" || user == null) {
    return (
      <main style={pageStyle}>
        <section style={panelStyle}>
          <p style={eyebrowStyle}>Backtesting</p>
          <h1 style={titleStyle}>Backtests unavailable</h1>
          <p style={bodyStyle}>{error ?? "Unable to load backtests."}</p>
          <div style={actionRowStyle}>
            <Link href="/app" style={primaryLinkStyle}>
              Back to app
            </Link>
          </div>
        </section>
      </main>
    );
  }

  const selectedUniverse = universes.find((universe) => universe.id === selectedUniverseId) ?? null;
  const launchGuidance = buildBacktestGuidance({
    universeEntryCount: selectedUniverse?.entry_count ?? 0,
    portfolioSize,
    startDate,
    endDate,
    refreshCache,
    useCache,
  });

  return (
    <main style={pageStyle}>
      <section style={panelStyle}>
        <div style={headerRowStyle}>
          <div>
            <p style={eyebrowStyle}>Portfolio Research</p>
            <h1 style={titleStyle}>Backtest a saved universe</h1>
          </div>
        </div>

        <p style={bodyStyle}>
          Active workspace: <strong>{user.active_workspace?.name ?? "Unavailable"}</strong>. Start
          with the default rebalance assumptions, choose a sensible date range, and only open
          advanced settings when you need benchmark, filter, or cache overrides.
        </p>

        {error ? <p style={errorStyle}>{error}</p> : null}
        {draftNotice ? <p style={infoStyle}>{draftNotice}</p> : null}

        <div style={layoutStyle}>
          <div style={stackStyle}>
            <section style={sectionCardStyle}>
              <p style={sectionLabelStyle}>Launch a backtest</p>
              <div style={presetGridStyle}>
                {backtestPresets.map((preset) => (
                  <button key={preset.id} type="button" style={presetButtonStyle} onClick={() => applyPreset(preset.id)}>
                    <strong>{preset.label}</strong>
                    <span style={presetMetaStyle}>{preset.description}</span>
                  </button>
                ))}
              </div>
              {universes.length === 0 ? (
                <div style={{ display: "grid", gap: "0.75rem", marginTop: "1rem" }}>
                  <p style={bodyStyle}>You need a saved universe before you can launch backtests.</p>
                  <Link href="/app/universes" style={primaryLinkStyle}>
                    Create a universe
                  </Link>
                </div>
              ) : (
                <form onSubmit={handleLaunch} style={formStyle}>
                  <label style={fieldStyle}>
                    <span style={labelStyle}>Universe</span>
                    <select
                      value={selectedUniverseId ?? ""}
                      onChange={(event) => setSelectedUniverseId(Number(event.target.value))}
                      style={inputStyle}
                    >
                      {universes.map((universe) => (
                        <option key={universe.id} value={universe.id}>
                          {universe.name} ({universe.entry_count} names)
                        </option>
                      ))}
                    </select>
                  </label>
                  <div style={threeColumnStyle}>
                    <label style={fieldStyle}>
                      <span style={labelStyle}>Start date</span>
                      <input type="date" value={startDate} onChange={(event) => setStartDate(event.target.value)} style={inputStyle} />
                    </label>
                    <label style={fieldStyle}>
                      <span style={labelStyle}>End date</span>
                      <input type="date" value={endDate} onChange={(event) => setEndDate(event.target.value)} style={inputStyle} />
                    </label>
                  </div>
                  <div style={threeColumnStyle}>
                    <label style={fieldStyle}>
                      <span style={labelStyle}>Initial capital</span>
                      <input
                        type="number"
                        min={1}
                        value={initialCapital}
                        onChange={(event) => setInitialCapital(Number(event.target.value))}
                        style={inputStyle}
                      />
                    </label>
                    <label style={fieldStyle}>
                      <span style={labelStyle}>Portfolio size</span>
                      <input
                        type="number"
                        min={1}
                        max={200}
                        value={portfolioSize}
                        onChange={(event) => setPortfolioSize(Number(event.target.value))}
                        style={inputStyle}
                      />
                    </label>
                  </div>
                  <div style={threeColumnStyle}>
                    <div style={helperCardStyle}>
                      <strong>Default flow</strong>
                      <p style={helperTextStyle}>
                        Universe, date range, portfolio size, and capital are enough for a clean
                        first pass.
                      </p>
                    </div>
                    <button
                      type="button"
                      style={secondaryButtonStyle}
                      onClick={() => setShowAdvanced((currentValue) => !currentValue)}
                    >
                      {showAdvanced ? "Hide advanced settings" : "Show advanced settings"}
                    </button>
                  </div>
                  {showAdvanced ? (
                    <div style={advancedCardStyle}>
                      <div>
                        <p style={sectionLabelStyle}>Advanced settings</p>
                        <p style={advancedBodyStyle}>
                          Tune benchmark, rebalance cadence, filters, and cache controls only when
                          the defaults are not enough.
                        </p>
                      </div>
                      <div style={threeColumnStyle}>
                        <label style={fieldStyle}>
                          <span style={labelStyle}>Benchmark</span>
                          <input type="text" value={benchmark} onChange={(event) => setBenchmark(event.target.value)} style={inputStyle} />
                        </label>
                        <label style={fieldStyle}>
                          <span style={labelStyle}>Review frequency</span>
                          <input
                            type="text"
                            value={reviewFrequency}
                            onChange={(event) => setReviewFrequency(event.target.value)}
                            placeholder="W-FRI"
                            style={inputStyle}
                          />
                        </label>
                        <label style={fieldStyle}>
                          <span style={labelStyle}>Momentum mode</span>
                          <select
                            value={momentumMode}
                            onChange={(event) => setMomentumMode(event.target.value as "none" | "overlay" | "filter")}
                            style={inputStyle}
                          >
                            <option value="none">None</option>
                            <option value="overlay">Overlay</option>
                            <option value="filter">Filter</option>
                          </select>
                        </label>
                      </div>
                      <div style={threeColumnStyle}>
                        <label style={fieldStyle}>
                          <span style={labelStyle}>Sector allowlist</span>
                          <input
                            type="text"
                            value={sectorAllowlist}
                            onChange={(event) => setSectorAllowlist(event.target.value)}
                            placeholder="Technology, Healthcare"
                            style={inputStyle}
                          />
                        </label>
                        <label style={fieldStyle}>
                          <span style={labelStyle}>Minimum market cap</span>
                          <input
                            type="number"
                            min={0}
                            value={minMarketCap}
                            onChange={(event) => setMinMarketCap(event.target.value)}
                            placeholder="5000000000"
                            style={inputStyle}
                          />
                        </label>
                        <label style={fieldStyle}>
                          <span style={labelStyle}>Cache TTL hours</span>
                          <input
                            type="number"
                            min={0}
                            value={cacheTtlHours}
                            onChange={(event) => setCacheTtlHours(Number(event.target.value))}
                            style={inputStyle}
                          />
                        </label>
                      </div>
                      <div style={threeColumnStyle}>
                        <label style={checkboxFieldStyle}>
                          <input type="checkbox" checked={useCache} onChange={(event) => setUseCache(event.target.checked)} />
                          <span>Use cached provider data</span>
                        </label>
                        <label style={checkboxFieldStyle}>
                          <input
                            type="checkbox"
                            checked={refreshCache}
                            onChange={(event) => setRefreshCache(event.target.checked)}
                          />
                          <span>Refresh fundamentals cache first</span>
                        </label>
                      </div>
                    </div>
                  ) : null}
                  {launchGuidance.length > 0 ? (
                    <div style={guidanceCardStyle}>
                      <p style={sectionLabelStyle}>Launch guidance</p>
                      <div style={guidanceListStyle}>
                        {launchGuidance.map((item) => (
                          <p key={item} style={guidanceTextStyle}>
                            {item}
                          </p>
                        ))}
                      </div>
                    </div>
                  ) : null}
                  <button type="submit" style={buttonStyle} disabled={isLaunching}>
                    {isLaunching ? "Launching backtest..." : "Launch backtest"}
                  </button>
                </form>
              )}
            </section>
          </div>

          <aside style={sectionCardStyle}>
            <div style={statusHeaderStyle}>
              <div>
                <p style={sectionLabelStyle}>Recent backtests</p>
                <h2 style={summaryTitleStyle}>{backtests.length}</h2>
              </div>
              <span style={pillStyle}>Auto-polls active runs</span>
            </div>

            <div style={runListStyle}>
              {backtests.length === 0 ? (
                <p style={bodyStyle}>No backtests have been launched yet.</p>
              ) : (
                backtests.map((backtest) => (
                  <Link key={backtest.id} href={`/app/backtests/${backtest.id}`} style={runCardStyle}>
                    <div>
                      <strong>#{backtest.id}</strong>
                      <div style={metaStyle}>{backtest.universe.name}</div>
                      <div style={subtleMetaStyle}>
                        {backtest.start_date} to {backtest.end_date}
                      </div>
                    </div>
                    <span style={stateBadgeStyle(backtest.job.state)}>{backtest.job.state.replaceAll("_", " ")}</span>
                  </Link>
                ))
              )}
            </div>
          </aside>
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

function buildBacktestGuidance(payload: {
  universeEntryCount: number;
  portfolioSize: number;
  startDate: string;
  endDate: string;
  refreshCache: boolean;
  useCache: boolean;
}): string[] {
  const messages: string[] = [];
  const start = payload.startDate ? new Date(payload.startDate) : null;
  const end = payload.endDate ? new Date(payload.endDate) : null;
  const durationDays =
    start && end && !Number.isNaN(start.getTime()) && !Number.isNaN(end.getTime())
      ? Math.max(0, Math.round((end.getTime() - start.getTime()) / 86_400_000))
      : 0;
  if (payload.universeEntryCount > 250 && durationDays > 730) {
    messages.push("Large universes over long date ranges create heavier backtests and may take longer to finish.");
  }
  if (payload.universeEntryCount > 0 && payload.portfolioSize > Math.max(20, Math.floor(payload.universeEntryCount / 2))) {
    messages.push("A smaller portfolio size is usually easier to interpret when the universe itself is small.");
  }
  if (payload.refreshCache) {
    messages.push("Refreshing cache first improves freshness but usually increases runtime.");
  } else if (!payload.useCache) {
    messages.push("Disabling cache will force more live provider calls and can slow repeated backtests.");
  }
  return messages;
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
  padding: 0,
};

const panelStyle: CSSProperties = {
  width: "100%",
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

const layoutStyle: CSSProperties = {
  display: "grid",
  gap: "1.25rem",
  gridTemplateColumns: "minmax(0, 1.3fr) minmax(320px, 0.9fr)",
  marginTop: "2rem",
};

const stackStyle: CSSProperties = {
  display: "grid",
  gap: "1.25rem",
};

const sectionCardStyle: CSSProperties = {
  padding: "1.25rem",
  borderRadius: "22px",
  background: "#f8fbff",
  border: "1px solid rgba(73, 98, 128, 0.18)",
};

const presetGridStyle: CSSProperties = {
  display: "grid",
  gap: "0.75rem",
  gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
  marginTop: "1rem",
};

const presetButtonStyle: CSSProperties = {
  display: "grid",
  gap: "0.25rem",
  textAlign: "left",
  padding: "0.9rem 1rem",
  borderRadius: "16px",
  border: "1px solid rgba(73, 98, 128, 0.18)",
  background: "#fff",
  color: "#162132",
  cursor: "pointer",
};

const presetMetaStyle: CSSProperties = {
  color: "#5c728d",
  lineHeight: 1.4,
};

const sectionLabelStyle: CSSProperties = {
  margin: 0,
  fontSize: "0.82rem",
  letterSpacing: "0.12em",
  textTransform: "uppercase",
  color: "#5c728d",
};

const formStyle: CSSProperties = {
  display: "grid",
  gap: "0.9rem",
  marginTop: "1rem",
};

const fieldStyle: CSSProperties = {
  display: "grid",
  gap: "0.4rem",
};

const threeColumnStyle: CSSProperties = {
  display: "grid",
  gap: "0.9rem",
  gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
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

const buttonStyle: CSSProperties = {
  border: 0,
  borderRadius: "999px",
  padding: "0.9rem 1rem",
  background: "#162132",
  color: "#f5f7fb",
  cursor: "pointer",
  fontSize: "0.98rem",
};

const secondaryButtonStyle: CSSProperties = {
  ...buttonStyle,
  background: "#dde6f0",
  color: "#162132",
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

const helperCardStyle: CSSProperties = {
  display: "grid",
  gap: "0.35rem",
  padding: "0.95rem 1rem",
  borderRadius: "16px",
  background: "#eef4fb",
  color: "#203247",
};

const helperTextStyle: CSSProperties = {
  margin: 0,
  lineHeight: 1.5,
  color: "#496280",
};

const errorStyle: CSSProperties = {
  marginTop: "1rem",
  padding: "0.9rem 1rem",
  borderRadius: "16px",
  background: "#ffe5e0",
  color: "#8f2622",
};

const infoStyle: CSSProperties = {
  marginTop: "1rem",
  padding: "0.9rem 1rem",
  borderRadius: "16px",
  background: "#e6f1ff",
  color: "#0f4c81",
};

const advancedCardStyle: CSSProperties = {
  display: "grid",
  gap: "0.9rem",
  padding: "1rem",
  borderRadius: "18px",
  background: "#fff",
  border: "1px solid rgba(73, 98, 128, 0.18)",
};

const advancedBodyStyle: CSSProperties = {
  margin: "0.35rem 0 0",
  lineHeight: 1.5,
  color: "#5c728d",
};

const guidanceCardStyle: CSSProperties = {
  display: "grid",
  gap: "0.55rem",
  padding: "1rem",
  borderRadius: "18px",
  background: "#f5f9fd",
  border: "1px solid rgba(73, 98, 128, 0.18)",
};

const guidanceListStyle: CSSProperties = {
  display: "grid",
  gap: "0.45rem",
};

const guidanceTextStyle: CSSProperties = {
  margin: 0,
  color: "#496280",
  lineHeight: 1.5,
};

const statusHeaderStyle: CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  alignItems: "flex-start",
  gap: "1rem",
};

const summaryTitleStyle: CSSProperties = {
  margin: "0.45rem 0 0",
  fontSize: "1.8rem",
};

const runListStyle: CSSProperties = {
  display: "grid",
  gap: "0.75rem",
  marginTop: "1rem",
};

const runCardStyle: CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  gap: "0.75rem",
  alignItems: "center",
  padding: "1rem",
  borderRadius: "18px",
  background: "#fff",
  border: "1px solid rgba(73, 98, 128, 0.16)",
  textDecoration: "none",
  color: "#162132",
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
  padding: "0.4rem 0.7rem",
  borderRadius: "999px",
  background: "#e5edf6",
  color: "#3d556f",
  fontSize: "0.88rem",
};
