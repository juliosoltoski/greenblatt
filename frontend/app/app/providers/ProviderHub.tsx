"use client";

import {
  startTransition,
  useEffect,
  useState,
  type CSSProperties,
  type FormEvent,
} from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import {
  ApiError,
  getCurrentUser,
  getProviderDiagnostics,
  launchProviderCacheWarm,
  listUniverses,
  type CurrentUser,
  type JobRun,
  type ProviderDiagnosticEntry,
  type ProviderDiagnosticsResponse,
  type UniverseSummary,
} from "@/lib/api";

type LoadState = "loading" | "ready" | "error";

export function ProviderHub() {
  const router = useRouter();
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [diagnostics, setDiagnostics] =
    useState<ProviderDiagnosticsResponse | null>(null);
  const [universes, setUniverses] = useState<UniverseSummary[]>([]);
  const [selectedWorkspaceId, setSelectedWorkspaceId] = useState<number | null>(
    null,
  );
  const [selectedUniverseId, setSelectedUniverseId] = useState<number>(0);
  const [selectedProviderName, setSelectedProviderName] = useState<string>("");
  const [sampleSize, setSampleSize] = useState(100);
  const [refreshCache, setRefreshCache] = useState(false);
  const [state, setState] = useState<LoadState>("loading");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [isLaunching, setIsLaunching] = useState(false);
  const [isProbing, setIsProbing] = useState(false);
  const [lastJob, setLastJob] = useState<JobRun | null>(null);

  useEffect(() => {
    let active = true;

    async function loadInitial() {
      try {
        const currentUser = await getCurrentUser();
        const workspaceId =
          currentUser.active_workspace?.id ??
          currentUser.workspaces[0]?.id ??
          null;
        const [providerPayload, universePayload] = await Promise.all([
          getProviderDiagnostics(workspaceId ?? undefined, false),
          listUniverses(workspaceId ?? undefined),
        ]);
        if (!active) {
          return;
        }
        setUser(currentUser);
        setSelectedWorkspaceId(workspaceId);
        setDiagnostics(providerPayload);
        setUniverses(universePayload.results);
        setSelectedUniverseId(universePayload.results[0]?.id ?? 0);
        setSelectedProviderName(providerPayload.default_provider);
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
        setError(
          loadError instanceof Error
            ? loadError.message
            : "Unable to load data operations.",
        );
        setState("error");
      }
    }

    void loadInitial();

    return () => {
      active = false;
    };
  }, [router]);

  useEffect(() => {
    if (selectedWorkspaceId == null || state === "loading" || user == null) {
      return;
    }
    const workspaceId = selectedWorkspaceId;
    let active = true;

    async function loadWorkspaceData() {
      try {
        const [providerPayload, universePayload] = await Promise.all([
          getProviderDiagnostics(workspaceId, false),
          listUniverses(workspaceId),
        ]);
        if (!active) {
          return;
        }
        setDiagnostics(providerPayload);
        setUniverses(universePayload.results);
        setSelectedUniverseId((current) => {
          if (universePayload.results.some((item) => item.id === current)) {
            return current;
          }
          return universePayload.results[0]?.id ?? 0;
        });
        setSelectedProviderName(providerPayload.default_provider);
      } catch (loadError) {
        if (!active) {
          return;
        }
        setError(
          loadError instanceof Error
            ? loadError.message
            : "Unable to refresh data-source status.",
        );
      }
    }

    void loadWorkspaceData();

    return () => {
      active = false;
    };
  }, [selectedWorkspaceId, state, user]);

  async function handleProbeRefresh() {
    if (selectedWorkspaceId == null) {
      return;
    }
    setIsProbing(true);
    setError(null);
    setNotice(null);
    try {
      const payload = await getProviderDiagnostics(selectedWorkspaceId, true);
      setDiagnostics(payload);
      setNotice("Live checks refreshed.");
    } catch (probeError) {
      setError(
        probeError instanceof Error
          ? probeError.message
          : "Unable to run live checks.",
      );
    } finally {
      setIsProbing(false);
    }
  }

  async function handleCacheWarm(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (selectedWorkspaceId == null || selectedUniverseId <= 0) {
      setError("Select a workspace and universe before warming the cache.");
      return;
    }
    setIsLaunching(true);
    setError(null);
    setNotice(null);
    try {
      const job = await launchProviderCacheWarm({
        workspaceId: selectedWorkspaceId,
        universeId: selectedUniverseId,
        sampleSize,
        refreshCache,
        providerName: selectedProviderName,
      });
      setLastJob(job);
      const payload = await getProviderDiagnostics(selectedWorkspaceId, false);
      setDiagnostics(payload);
      setNotice("Cache warm job launched.");
    } catch (launchError) {
      setError(
        launchError instanceof Error
          ? launchError.message
          : "Unable to launch a cache warm job.",
      );
    } finally {
      setIsLaunching(false);
    }
  }

  if (state === "loading") {
    return (
      <main style={pageStyle}>
        <section style={panelStyle}>
          <p style={eyebrowStyle}>Providers</p>
          <h1 style={titleStyle}>Loading data coverage and health</h1>
          <p style={bodyStyle}>
            Checking data sources, recent issues, and maintenance status.
          </p>
        </section>
      </main>
    );
  }

  if (state === "error" || diagnostics == null || user == null) {
    return (
      <main style={pageStyle}>
        <section style={panelStyle}>
          <p style={eyebrowStyle}>Providers</p>
          <h1 style={titleStyle}>Data operations unavailable</h1>
          <p style={bodyStyle}>{error ?? "Unable to load data operations."}</p>
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
            <p style={eyebrowStyle}>Providers</p>
            <h1 style={titleStyle}>Keep data coverage reliable</h1>
            <p style={bodyStyle}>
              Review which data sources are ready for larger research runs,
              where recent issues are showing up, and which maintenance actions
              to use before heavier workloads start.
            </p>
          </div>
          <div style={actionRowStyle}>
            <button
              type="button"
              style={secondaryButtonStyle}
              onClick={() => void handleProbeRefresh()}
              disabled={isProbing}
            >
              {isProbing ? "Checking..." : "Run live checks"}
            </button>
            <Link href="/app/jobs" style={ghostLinkStyle}>
              Open jobs
            </Link>
          </div>
        </div>

        {error ? <p style={errorStyle}>{error}</p> : null}
        {notice ? <p style={inlineNoticeStyle}>{notice}</p> : null}

        <div style={toolbarStyle}>
          <label style={fieldStyle}>
            <span style={labelStyle}>Workspace</span>
            <select
              value={selectedWorkspaceId ?? ""}
              onChange={(event) =>
                setSelectedWorkspaceId(Number(event.target.value))
              }
              style={inputStyle}
            >
              {user.workspaces.map((workspace) => (
                <option key={workspace.id} value={workspace.id}>
                  {workspace.name}
                </option>
              ))}
            </select>
          </label>
          <div style={metaClusterStyle}>
            <SummaryStat
              label="Active jobs"
              value={String(diagnostics.workspace_usage.active_jobs.total)}
            />
            <SummaryStat
              label="Data jobs"
              value={String(
                diagnostics.workspace_usage.active_jobs.provider_operations,
              )}
            />
            <SummaryStat
              label="Recent issues"
              value={String(
                diagnostics.workspace_usage.recent_activity
                  .provider_failures_total,
              )}
            />
            <SummaryStat
              label="Primary source"
              value={diagnostics.default_provider}
            />
          </div>
        </div>

        <div style={sectionGridStyle}>
          <section style={cardStyle}>
            <div style={cardHeaderStyle}>
              <div>
                <p style={sectionLabelStyle}>Research-facing view</p>
                <h2 style={sectionTitleStyle}>
                  {diagnostics.providers.length} configured data sources
                </h2>
                <p style={metaStyle}>
                  Use this overview to spot the safest default source, fallback
                  coverage, and where a run may need extra caution.
                </p>
              </div>
            </div>
            <div style={stackStyle}>
              {diagnostics.providers.map((provider) => (
                <article key={provider.key} style={providerCardStyle}>
                  <div style={providerHeaderStyle}>
                    <div>
                      <h3 style={providerTitleStyle}>{provider.label}</h3>
                      <p style={metaStyle}>{provider.description}</p>
                    </div>
                    <span style={providerBadgeStyle(provider.state)}>
                      {provider.configured_default
                        ? "primary"
                        : provider.configured_fallback
                          ? "fallback"
                          : humanizeLabel(provider.state)}
                    </span>
                  </div>
                  <div style={detailsGridStyle}>
                    <DetailItem
                      label="Status"
                      value={humanizeLabel(provider.state)}
                    />
                    <DetailItem
                      label="Cost tier"
                      value={humanizeLabel(provider.cost_tier)}
                    />
                    <DetailItem
                      label="Best fit size"
                      value={
                        provider.recommended_candidate_limit == null
                          ? "n/a"
                          : `${provider.recommended_candidate_limit} names`
                      }
                    />
                    <DetailItem
                      label="Recent issues"
                      value={String(provider.recent_failure_count)}
                    />
                    <DetailItem
                      label="Throttle events"
                      value={String(provider.throttle_events)}
                    />
                    <DetailItem
                      label="Used by"
                      value={
                        provider.workflows.length > 0
                          ? provider.workflows.map(humanizeLabel).join(", ")
                          : "none"
                      }
                    />
                  </div>
                  <p style={detailBodyStyle}>{provider.rate_limit_profile}</p>
                  <p style={detailBodyStyle}>{provider.cache_advice}</p>
                  {provider.detail ? (
                    <p style={supportNoteStyle}>
                      Operator note: {provider.detail}
                    </p>
                  ) : null}
                  {provider.last_failure_message ? (
                    <p style={warningNoteStyle}>
                      Recent issue: {provider.last_failure_message}
                    </p>
                  ) : null}
                </article>
              ))}
            </div>
          </section>

          <section style={cardStyle}>
            <div style={cardHeaderStyle}>
              <div>
                <p style={sectionLabelStyle}>Operator tools</p>
                <h2 style={sectionTitleStyle}>
                  Run live checks and warm shared data
                </h2>
                <p style={metaStyle}>
                  Use these controls only when you need to verify live provider
                  status or prepare cached data before heavy activity.
                </p>
              </div>
            </div>
            <form onSubmit={handleCacheWarm} style={formStyle}>
              <label style={fieldStyle}>
                <span style={labelStyle}>Universe</span>
                <select
                  value={selectedUniverseId}
                  onChange={(event) =>
                    setSelectedUniverseId(Number(event.target.value))
                  }
                  style={inputStyle}
                >
                  {universes.length === 0 ? (
                    <option value={0}>No universes available</option>
                  ) : null}
                  {universes.map((universe) => (
                    <option key={universe.id} value={universe.id}>
                      {universe.name} ({universe.entry_count.toLocaleString()})
                    </option>
                  ))}
                </select>
              </label>
              <label style={fieldStyle}>
                <span style={labelStyle}>Data source</span>
                <select
                  value={selectedProviderName}
                  onChange={(event) =>
                    setSelectedProviderName(event.target.value)
                  }
                  style={inputStyle}
                >
                  {diagnostics.providers.map((provider) => (
                    <option key={provider.key} value={provider.key}>
                      {provider.label}
                    </option>
                  ))}
                </select>
              </label>
              <label style={fieldStyle}>
                <span style={labelStyle}>Sample size</span>
                <input
                  type="number"
                  min={1}
                  max={500}
                  step={1}
                  value={sampleSize}
                  onChange={(event) =>
                    setSampleSize(Number(event.target.value))
                  }
                  style={inputStyle}
                />
              </label>
              <label style={checkboxStyle}>
                <input
                  type="checkbox"
                  checked={refreshCache}
                  onChange={(event) => setRefreshCache(event.target.checked)}
                />
                <span>
                  Refresh existing snapshots instead of reusing recent cached
                  data.
                </span>
              </label>
              <button
                type="submit"
                style={primaryButtonStyle}
                disabled={isLaunching || universes.length === 0}
              >
                {isLaunching ? "Launching..." : "Warm cache"}
              </button>
            </form>

            {lastJob ? (
              <div style={inlineNoticeStyle}>
                <strong>Last warm-up:</strong> Job #{lastJob.id} is{" "}
                {humanizeLabel(lastJob.state)}.
              </div>
            ) : null}

            <div style={stackStyle}>
              <p style={sectionLabelStyle}>Operator notes</p>
              {diagnostics.recommendations.length === 0 ? (
                <p style={metaStyle}>No operator notes right now.</p>
              ) : (
                diagnostics.recommendations.map((item) => (
                  <div key={item} style={recommendationStyle}>
                    {item}
                  </div>
                ))
              )}
            </div>

            <div style={stackStyle}>
              <p style={sectionLabelStyle}>Recent warm-up jobs</p>
              {diagnostics.recent_cache_warm_jobs.length === 0 ? (
                <p style={metaStyle}>
                  No cache warm jobs have been launched in this workspace yet.
                </p>
              ) : (
                diagnostics.recent_cache_warm_jobs.map((job) => (
                  <Link key={job.id} href="/app/jobs" style={jobLinkStyle}>
                    <strong>#{job.id}</strong>
                    <span style={metaStyle}>
                      {humanizeLabel(job.state)} ·{" "}
                      {job.current_step || "Pending"}
                    </span>
                  </Link>
                ))
              )}
            </div>
          </section>
        </div>
      </section>
    </main>
  );
}

function SummaryStat({ label, value }: { label: string; value: string }) {
  return (
    <div style={statCardStyle}>
      <span style={labelStyle}>{label}</span>
      <strong style={statValueStyle}>{value}</strong>
    </div>
  );
}

function DetailItem({ label, value }: { label: string; value: string }) {
  return (
    <div style={detailItemStyle}>
      <span style={detailLabelStyle}>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function humanizeLabel(value: string): string {
  return value.replaceAll("_", " ");
}

function providerBadgeStyle(
  state: ProviderDiagnosticEntry["state"],
): CSSProperties {
  const palette = {
    ok: { background: "#e2f3e7", color: "#17663a" },
    warning: { background: "#fff2d9", color: "#8b5c00" },
    error: { background: "#ffe5e0", color: "#8f2622" },
    unconfigured: { background: "#dde6f0", color: "#162132" },
  } satisfies Record<
    ProviderDiagnosticEntry["state"],
    { background: string; color: string }
  >;

  return {
    padding: "0.45rem 0.7rem",
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

const toolbarStyle: CSSProperties = {
  display: "grid",
  gap: "1rem",
  gridTemplateColumns: "minmax(220px, 280px) minmax(0, 1fr)",
  marginTop: "1.5rem",
};

const sectionGridStyle: CSSProperties = {
  display: "grid",
  gap: "1rem",
  gridTemplateColumns: "minmax(0, 1.25fr) minmax(320px, 0.95fr)",
  marginTop: "1.5rem",
};

const cardStyle: CSSProperties = {
  padding: "1.25rem",
  borderRadius: "22px",
  background: "#f8fbff",
  border: "1px solid rgba(73, 98, 128, 0.18)",
  display: "grid",
  gap: "1rem",
  alignContent: "start",
};

const cardHeaderStyle: CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  alignItems: "flex-start",
  gap: "1rem",
  flexWrap: "wrap",
};

const providerCardStyle: CSSProperties = {
  padding: "1rem",
  borderRadius: "18px",
  background: "#fff",
  border: "1px solid rgba(73, 98, 128, 0.14)",
  display: "grid",
  gap: "0.85rem",
};

const providerHeaderStyle: CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  alignItems: "flex-start",
  gap: "1rem",
};

const providerTitleStyle: CSSProperties = {
  margin: 0,
  fontSize: "1.1rem",
};

const detailsGridStyle: CSSProperties = {
  display: "grid",
  gap: "0.65rem",
  gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))",
};

const detailItemStyle: CSSProperties = {
  display: "grid",
  gap: "0.25rem",
};

const detailLabelStyle: CSSProperties = {
  fontSize: "0.8rem",
  letterSpacing: "0.08em",
  textTransform: "uppercase",
  color: "#5c728d",
};

const metaClusterStyle: CSSProperties = {
  display: "grid",
  gap: "0.8rem",
  gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))",
};

const statCardStyle: CSSProperties = {
  padding: "0.9rem 1rem",
  borderRadius: "16px",
  background: "#f8fbff",
  border: "1px solid rgba(73, 98, 128, 0.18)",
  display: "grid",
  gap: "0.3rem",
};

const statValueStyle: CSSProperties = {
  fontSize: "1.15rem",
};

const formStyle: CSSProperties = {
  display: "grid",
  gap: "0.85rem",
};

const fieldStyle: CSSProperties = {
  display: "grid",
  gap: "0.45rem",
};

const checkboxStyle: CSSProperties = {
  display: "flex",
  gap: "0.55rem",
  alignItems: "flex-start",
  padding: "0.85rem 0.95rem",
  borderRadius: "14px",
  background: "#fff",
  border: "1px solid rgba(73, 98, 128, 0.18)",
  color: "#334862",
};

const inputStyle: CSSProperties = {
  width: "100%",
  borderRadius: "14px",
  border: "1px solid rgba(73, 98, 128, 0.22)",
  padding: "0.85rem 0.95rem",
  background: "#fff",
  fontSize: "0.98rem",
};

const stackStyle: CSSProperties = {
  display: "grid",
  gap: "0.75rem",
};

const recommendationStyle: CSSProperties = {
  padding: "0.9rem 1rem",
  borderRadius: "14px",
  background: "#eef4fa",
  color: "#203247",
};

const jobLinkStyle: CSSProperties = {
  display: "grid",
  gap: "0.2rem",
  padding: "0.85rem 0.95rem",
  borderRadius: "14px",
  background: "#fff",
  border: "1px solid rgba(73, 98, 128, 0.14)",
  color: "#162132",
  textDecoration: "none",
};

const inlineNoticeStyle: CSSProperties = {
  padding: "0.9rem 1rem",
  borderRadius: "14px",
  background: "#eef4fa",
  color: "#203247",
};

const primaryButtonStyle: CSSProperties = {
  border: 0,
  borderRadius: "999px",
  padding: "0.9rem 1.05rem",
  background: "#162132",
  color: "#f5f7fb",
  cursor: "pointer",
  fontSize: "0.98rem",
};

const secondaryButtonStyle: CSSProperties = {
  ...primaryButtonStyle,
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
  margin: "0.5rem 0 0.75rem",
  fontSize: "clamp(2rem, 4vw, 3rem)",
};

const bodyStyle: CSSProperties = {
  maxWidth: "56rem",
  lineHeight: 1.6,
  color: "#334862",
};

const labelStyle: CSSProperties = {
  fontSize: "0.8rem",
  letterSpacing: "0.08em",
  textTransform: "uppercase",
  color: "#5c728d",
};

const sectionLabelStyle: CSSProperties = {
  ...labelStyle,
  margin: 0,
};

const sectionTitleStyle: CSSProperties = {
  margin: "0.35rem 0 0",
  fontSize: "1.4rem",
};

const metaStyle: CSSProperties = {
  margin: 0,
  color: "#5c728d",
};

const detailBodyStyle: CSSProperties = {
  margin: 0,
  color: "#334862",
  lineHeight: 1.55,
};

const supportNoteStyle: CSSProperties = {
  margin: 0,
  color: "#5c728d",
  fontSize: "0.92rem",
};

const warningNoteStyle: CSSProperties = {
  margin: 0,
  color: "#8f2622",
  fontSize: "0.92rem",
};

const errorStyle: CSSProperties = {
  marginTop: "1rem",
  color: "#9d1b1b",
};
