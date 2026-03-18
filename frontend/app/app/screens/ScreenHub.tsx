"use client";

import { startTransition, useEffect, useState, type CSSProperties, type FormEvent } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import {
  ApiError,
  getCurrentUser,
  getScreenRun,
  getStrategyTemplate,
  launchScreen,
  listScreens,
  listUniverses,
  type CurrentUser,
  type ScreenRun,
  type StrategyTemplate,
  type UniverseSummary,
} from "@/lib/api";
import { getScreenPresetById, screenPresets } from "@/lib/workflowPresets";

type LoadState = "loading" | "ready" | "error";


type ScreenHubProps = {
  templateId: number | null;
  draftScreenRunId: number | null;
  presetId: string | null;
};


export function ScreenHub({ templateId, draftScreenRunId, presetId }: ScreenHubProps) {
  const router = useRouter();
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [universes, setUniverses] = useState<UniverseSummary[]>([]);
  const [screens, setScreens] = useState<ScreenRun[]>([]);
  const [state, setState] = useState<LoadState>("loading");
  const [error, setError] = useState<string | null>(null);
  const [selectedUniverseId, setSelectedUniverseId] = useState<number | null>(null);
  const [topN, setTopN] = useState(30);
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
        const [universePayload, screenPayload] = await Promise.all([
          listUniverses(workspaceId),
          listScreens(workspaceId, { limit: 20 }),
        ]);
        if (!active) {
          return;
        }
        setUser(currentUser);
        setUniverses(universePayload.results);
        setScreens(screenPayload.results);
        setSelectedUniverseId((currentValue) => currentValue ?? universePayload.results[0]?.id ?? null);
        if (templateId != null && Number.isFinite(templateId) && templateId > 0) {
          const template = await getStrategyTemplate(templateId);
          if (!active) {
            return;
          }
          applyTemplateDraft(template, universePayload.results);
        } else if (draftScreenRunId != null && Number.isFinite(draftScreenRunId) && draftScreenRunId > 0) {
          const priorRun = await getScreenRun(draftScreenRunId);
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
        setError(loadError instanceof Error ? loadError.message : "Unable to load screens.");
        setState("error");
      }
    }

    void load();

    return () => {
      active = false;
    };
  }, [draftScreenRunId, presetId, router, templateId]);

  useEffect(() => {
    if (user == null || state !== "ready") {
      return undefined;
    }
    if (!screens.some((screen) => !screen.job.is_terminal)) {
      return undefined;
    }

    const intervalId = window.setInterval(() => {
      void refreshScreens(user);
    }, 1500);

    return () => {
      window.clearInterval(intervalId);
    };
  }, [screens, state, user]);

  async function refreshScreens(currentUser: CurrentUser) {
    const workspaceId = currentUser.active_workspace?.id;
    const payload = await listScreens(workspaceId, { limit: 20 });
    setScreens(payload.results);
  }

  function applyTemplateDraft(template: StrategyTemplate, availableUniverses: UniverseSummary[]) {
    if (template.workflow_kind !== "screen") {
      setError("This template belongs to backtests, not screens.");
      return;
    }
    applyScreenConfig(template.universe.id, template.config, availableUniverses);
    setShowAdvanced(true);
    setDraftNotice(`Template applied: ${template.name}`);
  }

  function applyRunDraft(run: ScreenRun, availableUniverses: UniverseSummary[]) {
    applyScreenConfig(
      run.universe.id,
      {
        top_n: run.top_n,
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
    setDraftNotice(`Draft loaded from screen #${run.id}`);
  }

  function applyPreset(nextPresetId: string) {
    const preset = getScreenPresetById(nextPresetId);
    if (preset == null) {
      return;
    }
    setTopN(preset.topN);
    setMomentumMode(preset.momentumMode);
    setSectorAllowlist((preset.sectorAllowlist ?? []).join(", "));
    setMinMarketCap(preset.minMarketCap ? String(preset.minMarketCap) : "");
    setUseCache(preset.useCache ?? true);
    setRefreshCache(preset.refreshCache ?? false);
    setCacheTtlHours(preset.cacheTtlHours ?? 24);
    setShowAdvanced(Boolean(preset.sectorAllowlist?.length || preset.minMarketCap || preset.refreshCache));
    setDraftNotice(`Preset applied: ${preset.label}`);
  }

  function applyScreenConfig(universeId: number, config: Record<string, unknown>, availableUniverses: UniverseSummary[]) {
    const matchingUniverse = availableUniverses.find((universe) => universe.id === universeId);
    setSelectedUniverseId(matchingUniverse?.id ?? universeId);
    if (typeof config.top_n === "number") {
      setTopN(config.top_n);
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
      setError("Create or select a saved universe before launching a screen.");
      return;
    }

    setIsLaunching(true);
    setError(null);
    try {
      const created = await launchScreen({
        workspaceId: user.active_workspace.id,
        universeId: selectedUniverseId,
        topN,
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
      await refreshScreens(user);
      startTransition(() => {
        router.push(`/app/screens/${created.id}`);
      });
    } catch (launchError) {
      setError(formatApiError(launchError, "Unable to launch the screen."));
    } finally {
      setIsLaunching(false);
    }
  }

  if (state === "loading") {
    return (
      <main style={pageStyle}>
        <section style={panelStyle}>
          <p style={eyebrowStyle}>Screening</p>
          <h1 style={titleStyle}>Loading saved universes and prior runs</h1>
        </section>
      </main>
    );
  }

  if (state === "error" || user == null) {
    return (
      <main style={pageStyle}>
        <section style={panelStyle}>
          <p style={eyebrowStyle}>Screening</p>
          <h1 style={titleStyle}>Screens unavailable</h1>
          <p style={bodyStyle}>{error ?? "Unable to load screening."}</p>
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
  const launchGuidance = buildScreenGuidance({
    universeEntryCount: selectedUniverse?.entry_count ?? 0,
    topN,
    refreshCache,
    useCache,
  });

  return (
    <main style={pageStyle}>
      <section style={panelStyle}>
        <div style={headerRowStyle}>
          <div>
            <p style={eyebrowStyle}>Research</p>
            <h1 style={titleStyle}>Run a screen from a saved universe</h1>
          </div>
        </div>

        <p style={bodyStyle}>
          Active workspace: <strong>{user.active_workspace?.name ?? "Unavailable"}</strong>. Pick a
          saved universe, keep the default launch settings for a first pass, and only open advanced
          controls when you need sector filters or cache overrides.
        </p>

        {error ? <p style={errorStyle}>{error}</p> : null}
        {draftNotice ? <p style={infoStyle}>{draftNotice}</p> : null}

        <div style={layoutStyle}>
          <div style={stackStyle}>
            <section style={sectionCardStyle}>
              <p style={sectionLabelStyle}>Launch a screen</p>
              <div style={presetGridStyle}>
                {screenPresets.map((preset) => (
                  <button key={preset.id} type="button" style={presetButtonStyle} onClick={() => applyPreset(preset.id)}>
                    <strong>{preset.label}</strong>
                    <span style={presetMetaStyle}>{preset.description}</span>
                  </button>
                ))}
              </div>
              {universes.length === 0 ? (
                <div style={{ display: "grid", gap: "0.75rem", marginTop: "1rem" }}>
                  <p style={bodyStyle}>You need a saved universe before you can launch screening jobs.</p>
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
                  <div style={twoColumnStyle}>
                    <label style={fieldStyle}>
                      <span style={labelStyle}>Top N</span>
                      <input
                        type="number"
                        min={1}
                        max={500}
                        value={topN}
                        onChange={(event) => setTopN(Number(event.target.value))}
                        style={inputStyle}
                        required
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
                  <div style={twoColumnStyle}>
                    <div style={helperCardStyle}>
                      <strong>Default flow</strong>
                      <p style={helperTextStyle}>
                        Universe, `Top N`, and momentum mode are enough for most initial runs.
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
                      <div style={advancedHeaderStyle}>
                        <div>
                          <p style={sectionLabelStyle}>Advanced settings</p>
                          <p style={advancedBodyStyle}>
                            Use these when you need tighter filtering or want to override provider
                            cache behavior.
                          </p>
                        </div>
                      </div>
                      <div style={twoColumnStyle}>
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
                            placeholder="10000000000"
                            style={inputStyle}
                          />
                        </label>
                      </div>
                      <div style={twoColumnStyle}>
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
                      <label style={fieldStyle}>
                        <span style={labelStyle}>Cache TTL hours</span>
                        <input
                          type="number"
                          min={0}
                          step="1"
                          value={cacheTtlHours}
                          onChange={(event) => setCacheTtlHours(Number(event.target.value))}
                          style={inputStyle}
                        />
                      </label>
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
                    {isLaunching ? "Launching screen..." : "Launch screen"}
                  </button>
                </form>
              )}
            </section>

            <section style={sectionCardStyle}>
              <p style={sectionLabelStyle}>Saved universes ready to screen</p>
              <div style={runListStyle}>
                {universes.map((universe) => (
                  <div key={universe.id} style={listRowStyle}>
                    <div>
                      <strong>{universe.name}</strong>
                      <div style={metaStyle}>
                        {universe.source_type.replaceAll("_", " ")} | {universe.entry_count} names
                      </div>
                    </div>
                    <Link href={`/app/universes/${universe.id}`} style={ghostLinkStyle}>
                      Inspect
                    </Link>
                  </div>
                ))}
              </div>
            </section>
          </div>

          <aside style={sectionCardStyle}>
            <div style={statusHeaderStyle}>
              <div>
                <p style={sectionLabelStyle}>Recent screens</p>
                <h2 style={summaryTitleStyle}>{screens.length}</h2>
              </div>
              <span style={pillStyle}>Auto-polls active runs</span>
            </div>

            <div style={runListStyle}>
              {screens.length === 0 ? (
                <p style={bodyStyle}>No screen runs have been launched yet.</p>
              ) : (
                screens.map((screen) => (
                  <Link key={screen.id} href={`/app/screens/${screen.id}`} style={screenCardStyle}>
                    <div>
                      <strong>#{screen.id}</strong>
                      <div style={metaStyle}>{screen.universe.name}</div>
                      <div style={subtleMetaStyle}>
                        {screen.result_count} ranked | {screen.exclusion_count} excluded
                      </div>
                    </div>
                    <span style={stateBadgeStyle(screen.job.state)}>{screen.job.state.replaceAll("_", " ")}</span>
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

function buildScreenGuidance(payload: {
  universeEntryCount: number;
  topN: number;
  refreshCache: boolean;
  useCache: boolean;
}): string[] {
  const messages: string[] = [];
  if (payload.universeEntryCount > 1200) {
    messages.push("Large universes on free providers can take noticeably longer on the first run.");
  }
  if (payload.topN > 50 || (payload.universeEntryCount > 0 && payload.topN > Math.max(25, Math.floor(payload.universeEntryCount / 3)))) {
    messages.push("A smaller Top N is usually easier to review before you widen the shortlist.");
  }
  if (payload.refreshCache) {
    messages.push("Refreshing cache first improves freshness but usually increases runtime.");
  } else if (!payload.useCache) {
    messages.push("Disabling cache will force more live provider calls and may hit rate limits sooner.");
  }
  return messages;
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

const checkboxFieldStyle: CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: "0.55rem",
  padding: "0.9rem 1rem",
  borderRadius: "14px",
  border: "1px solid rgba(73, 98, 128, 0.18)",
  background: "#fff",
};

const twoColumnStyle: CSSProperties = {
  display: "grid",
  gap: "0.9rem",
  gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
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

const advancedHeaderStyle: CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  gap: "1rem",
  alignItems: "flex-start",
  flexWrap: "wrap",
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

const runListStyle: CSSProperties = {
  display: "grid",
  gap: "0.75rem",
  marginTop: "1rem",
};

const listRowStyle: CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  gap: "0.75rem",
  alignItems: "center",
  padding: "0.95rem 1rem",
  borderRadius: "18px",
  background: "#fff",
  border: "1px solid rgba(73, 98, 128, 0.16)",
};

const screenCardStyle: CSSProperties = {
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
