"use client";

import { startTransition, useEffect, useMemo, useState, type CSSProperties } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import {
  ApiError,
  createProfileUniverse,
  getCurrentUser,
  listBacktests,
  listScreens,
  listProviders,
  listStrategyTemplates,
  listUniverses,
  logout,
  type BacktestRun,
  type CurrentUser,
  type ProviderHealthResponse,
  type ScreenRun,
  type StrategyTemplate,
  type UniverseSummary,
} from "@/lib/api";
import { backtestPresets, screenPresets, starterUniverseProfiles } from "@/lib/workflowPresets";

type LoadState = "loading" | "ready" | "error";

export function AppShell() {
  const router = useRouter();
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [universes, setUniverses] = useState<UniverseSummary[]>([]);
  const [screens, setScreens] = useState<ScreenRun[]>([]);
  const [backtests, setBacktests] = useState<BacktestRun[]>([]);
  const [templates, setTemplates] = useState<StrategyTemplate[]>([]);
  const [providers, setProviders] = useState<ProviderHealthResponse | null>(null);
  const [state, setState] = useState<LoadState>("loading");
  const [error, setError] = useState<string | null>(null);
  const [creatingProfileKey, setCreatingProfileKey] = useState<string | null>(null);

  useEffect(() => {
    let active = true;

    async function load() {
      try {
        const currentUser = await getCurrentUser();
        const workspaceId = currentUser.active_workspace?.id;
        const [universePayload, screenPayload, backtestPayload, templatePayload, providerPayload] = await Promise.all([
          listUniverses(workspaceId),
          listScreens(workspaceId, { limit: 5 }),
          listBacktests(workspaceId, { limit: 5 }),
          listStrategyTemplates({ workspaceId, pageSize: 5 }),
          listProviders(),
        ]);
        if (!active) {
          return;
        }
        setUser(currentUser);
        setUniverses(universePayload.results);
        setScreens(screenPayload.results);
        setBacktests(backtestPayload.results);
        setTemplates(templatePayload.results);
        setProviders(providerPayload);
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
        setError(loadError instanceof Error ? loadError.message : "Unable to load the dashboard.");
        setState("error");
      }
    }

    void load();

    return () => {
      active = false;
    };
  }, [router]);

  const onboardingItems = useMemo(() => {
    const successfulScreen = screens.some((screen) => screen.job.state === "succeeded");
    const successfulBacktest = backtests.some((backtest) => backtest.job.state === "succeeded");
    return [
      {
        label: "Create a universe",
        description: "Start with a built-in profile if you do not already have a list.",
        href: "/app/universes",
        completed: universes.length > 0,
      },
      {
        label: "Run a screen",
        description: "Use a saved universe and keep the default launch settings first.",
        href: "/app/screens?preset=starter_us",
        completed: successfulScreen,
      },
      {
        label: "Backtest the shortlist",
        description: "Validate the workflow over time before automating it.",
        href: "/app/backtests?preset=starter_compact",
        completed: successfulBacktest,
      },
      {
        label: "Save a reusable template",
        description: "Promote a good run so it can be relaunched without rebuilding inputs.",
        href: "/app/templates",
        completed: templates.length > 0,
      },
    ];
  }, [backtests, screens, templates.length, universes.length]);

  async function handleLogout() {
    setError(null);
    try {
      await logout();
      startTransition(() => {
        router.replace("/login");
      });
    } catch (logoutError) {
      setError(logoutError instanceof Error ? logoutError.message : "Logout failed.");
    }
  }

  async function handleCreateStarterUniverse(profileKey: string) {
    if (user?.active_workspace == null) {
      setError("No active workspace is available.");
      return;
    }
    setCreatingProfileKey(profileKey);
    setError(null);
    try {
      const created = await createProfileUniverse({
        workspaceId: user.active_workspace.id,
        name: starterUniverseName(profileKey),
        description: "Starter universe created from the dashboard.",
        profileKey,
      });
      startTransition(() => {
        router.push(`/app/universes/${created.id}`);
      });
    } catch (createError) {
      setError(createError instanceof Error ? createError.message : "Unable to create the starter universe.");
    } finally {
      setCreatingProfileKey(null);
    }
  }

  if (state === "loading") {
    return (
      <main style={shellStyle}>
        <section style={panelStyle}>
          <p style={eyebrowStyle}>Dashboard</p>
          <h1 style={titleStyle}>Loading your workspace</h1>
          <p style={bodyStyle}>Gathering your latest research, templates, and market-data status.</p>
        </section>
      </main>
    );
  }

  if (state === "error") {
    return (
      <main style={shellStyle}>
        <section style={panelStyle}>
          <p style={eyebrowStyle}>Dashboard</p>
          <h1 style={titleStyle}>Dashboard unavailable</h1>
          <p style={bodyStyle}>{error ?? "Unable to load the dashboard."}</p>
          <Link href="/app/universes" style={linkButtonStyle}>
            Open universes
          </Link>
        </section>
      </main>
    );
  }

  if (user === null) {
    return null;
  }

  return (
    <main style={shellStyle}>
      <section style={panelStyle}>
        <div style={headerRowStyle}>
          <div>
            <p style={eyebrowStyle}>Dashboard</p>
            <h1 style={titleStyle}>Welcome back, {user.display_name}</h1>
            <p style={bodyStyle}>
              Move from idea to repeatable workflow in one place: refresh a universe, run a screen,
              pressure-test the shortlist in a backtest, then save the approach as a reusable
              template or schedule.
            </p>
          </div>
          <button type="button" style={secondaryButtonStyle} onClick={handleLogout}>
            Log out
          </button>
        </div>

        {error ? <p style={errorStyle}>{error}</p> : null}

        <div style={topGridStyle}>
          <section style={heroCardStyle}>
            <div style={cardHeaderStyle}>
              <div>
                <p style={cardLabelStyle}>Getting Started</p>
                <h2 style={cardTitleStyle}>Onboarding checklist</h2>
              </div>
              <span style={pillStyle}>
                {onboardingItems.filter((item) => item.completed).length}/{onboardingItems.length} complete
              </span>
            </div>
            <div style={checklistStyle}>
              {onboardingItems.map((item) => (
                <Link key={item.label} href={item.href} style={checklistItemStyle}>
                  <span style={item.completed ? completeDotStyle : pendingDotStyle} />
                  <div>
                    <strong>{item.label}</strong>
                    <div style={metaStyle}>{item.description}</div>
                  </div>
                </Link>
              ))}
            </div>
          </section>

          <section style={cardStyle}>
            <div style={cardHeaderStyle}>
              <div>
                <p style={cardLabelStyle}>Quick Start</p>
                <h2 style={cardTitleStyle}>Starter universes</h2>
              </div>
              <Link href="/app/universes" style={ghostLinkStyle}>
                Open universes
              </Link>
            </div>
            <div style={stackStyle}>
              {starterUniverseProfiles.map((profile) => (
                <div key={profile.key} style={quickRowStyle}>
                  <div>
                    <strong>{profile.label}</strong>
                    <div style={metaStyle}>{profile.description}</div>
                  </div>
                  <button
                    type="button"
                    style={buttonStyle}
                    onClick={() => void handleCreateStarterUniverse(profile.key)}
                    disabled={creatingProfileKey === profile.key}
                  >
                    {creatingProfileKey === profile.key ? "Creating..." : "Create"}
                  </button>
                </div>
              ))}
            </div>
          </section>
        </div>

        <div style={gridStyle}>
          <section style={cardStyle}>
            <div style={cardHeaderStyle}>
              <div>
                <p style={cardLabelStyle}>Safe Defaults</p>
                <h2 style={cardTitleStyle}>Starter presets</h2>
              </div>
            </div>
            <div style={presetGroupStyle}>
              <div style={stackStyle}>
                {screenPresets.map((preset) => (
                  <Link key={preset.id} href={`/app/screens?preset=${preset.id}`} style={presetLinkStyle}>
                    <strong>{preset.label}</strong>
                    <div style={metaStyle}>{preset.description}</div>
                  </Link>
                ))}
              </div>
              <div style={stackStyle}>
                {backtestPresets.map((preset) => (
                  <Link key={preset.id} href={`/app/backtests?preset=${preset.id}`} style={presetLinkStyle}>
                    <strong>{preset.label}</strong>
                    <div style={metaStyle}>{preset.description}</div>
                  </Link>
                ))}
              </div>
            </div>
          </section>

          <section style={cardStyle}>
            <div style={cardHeaderStyle}>
              <div>
                <p style={cardLabelStyle}>Data sources</p>
                <h2 style={cardTitleStyle}>Market data health</h2>
              </div>
              <Link href="/app/jobs" style={ghostLinkStyle}>
                Open jobs
              </Link>
            </div>
            <div style={stackStyle}>
              {providers?.providers.map((provider) => (
                <div key={provider.key} style={providerRowStyle}>
                  <div>
                    <strong>{provider.label}</strong>
                    <div style={metaStyle}>{provider.description}</div>
                    <div style={subtleMetaStyle}>{provider.detail || "Ready for use."}</div>
                  </div>
                  <span style={providerBadgeStyle(provider.state)}>
                    {provider.configured_default ? "default" : provider.configured_fallback ? "fallback" : provider.state}
                  </span>
                </div>
              ))}
            </div>
          </section>

          <section style={cardStyle}>
            <div style={cardHeaderStyle}>
              <div>
                <p style={cardLabelStyle}>Workspace</p>
                <h2 style={cardTitleStyle}>{user.active_workspace?.name ?? "No workspace"}</h2>
              </div>
              <Link href="/app/settings" style={ghostLinkStyle}>
                Open settings
              </Link>
            </div>
            <p style={metaStyle}>
              Role: <strong>{user.active_workspace?.role ?? "n/a"}</strong>
            </p>
            <p style={metaStyle}>
              Slug: <code>{user.active_workspace?.slug ?? "n/a"}</code>
            </p>
            <p style={metaStyle}>
              Account: <strong>{user.username}</strong> {user.email ? `· ${user.email}` : ""}
            </p>
            <div style={cardActionRowStyle}>
              <Link href="/app/history" style={linkButtonStyle}>
                History
              </Link>
              <Link href="/app/templates" style={ghostLinkStyle}>
                Templates
              </Link>
              <Link href="/app/alerts" style={ghostLinkStyle}>
                Alerts
              </Link>
            </div>
          </section>
        </div>

        <div style={activityGridStyle}>
          <RecentList
            title="Recent screens"
            emptyMessage="No screens yet. Start with a saved universe and the starter preset."
            items={screens.map((screen) => ({
              href: `/app/screens/${screen.id}`,
              title: `Screen #${screen.id}`,
              detail: `${screen.universe.name} · ${screen.job.state.replaceAll("_", " ")}`,
              accent: screen.is_starred ? "Starred" : `${screen.result_count} ranked`,
            }))}
            ctaHref="/app/screens?preset=starter_us"
            ctaLabel="Launch screen"
          />
          <RecentList
            title="Recent backtests"
            emptyMessage="No backtests yet. Reuse a screened universe and start with the compact preset."
            items={backtests.map((backtest) => ({
              href: `/app/backtests/${backtest.id}`,
              title: `Backtest #${backtest.id}`,
              detail: `${backtest.start_date} to ${backtest.end_date}`,
              accent:
                typeof backtest.summary.total_return === "number"
                  ? `${(backtest.summary.total_return * 100).toFixed(2)}% total return`
                  : backtest.job.state.replaceAll("_", " "),
            }))}
            ctaHref="/app/backtests?preset=starter_compact"
            ctaLabel="Launch backtest"
          />
          <RecentList
            title="Saved templates"
            emptyMessage="No templates yet. Save a strong run from history once the results look stable."
            items={templates.map((template) => ({
              href:
                template.workflow_kind === "screen"
                  ? `/app/screens?template_id=${template.id}`
                  : `/app/backtests?template_id=${template.id}`,
              title: template.name,
              detail: `${template.workflow_kind} · ${template.universe.name}`,
              accent: template.is_starred ? "Starred" : template.last_used_at ? "Used recently" : "New",
            }))}
            ctaHref="/app/templates"
            ctaLabel="Open templates"
          />
          <RecentList
            title="Saved universes"
            emptyMessage="No universes yet. Create one from a built-in profile or upload a file."
            items={universes.slice(0, 5).map((universe) => ({
              href: `/app/universes/${universe.id}`,
              title: universe.name,
              detail: `${universe.entry_count} names · ${universe.source_type.replaceAll("_", " ")}`,
              accent: universe.is_starred ? "Starred" : universe.profile_key ?? "Custom",
            }))}
            ctaHref="/app/universes"
            ctaLabel="Open universes"
          />
        </div>
      </section>
    </main>
  );
}

function RecentList({
  title,
  emptyMessage,
  items,
  ctaHref,
  ctaLabel,
}: {
  title: string;
  emptyMessage: string;
  items: Array<{ href: string; title: string; detail: string; accent: string }>;
  ctaHref: string;
  ctaLabel: string;
}) {
  return (
    <section style={cardStyle}>
      <div style={cardHeaderStyle}>
        <div>
          <p style={cardLabelStyle}>Recent activity</p>
          <h2 style={cardTitleStyle}>{title}</h2>
        </div>
        <Link href={ctaHref} style={ghostLinkStyle}>
          {ctaLabel}
        </Link>
      </div>
      {items.length === 0 ? (
        <p style={metaStyle}>{emptyMessage}</p>
      ) : (
        <div style={stackStyle}>
          {items.map((item) => (
            <Link key={`${item.href}:${item.title}`} href={item.href} style={recentItemStyle}>
              <div>
                <strong>{item.title}</strong>
                <div style={metaStyle}>{item.detail}</div>
              </div>
              <span style={recentAccentStyle}>{item.accent}</span>
            </Link>
          ))}
        </div>
      )}
    </section>
  );
}

function starterUniverseName(profileKey: string): string {
  switch (profileKey) {
    case "us_top_3000":
      return "Starter US broad market";
    case "sector_tech":
      return "Starter technology watchlist";
    case "eu_benelux_nordic":
      return "Starter Europe watchlist";
    default:
      return `Starter ${profileKey}`;
  }
}

function providerBadgeStyle(state: string): CSSProperties {
  const palette: Record<string, { background: string; color: string }> = {
    ok: { background: "#e2f3e7", color: "#17663a" },
    warning: { background: "#fff2d9", color: "#8b5c00" },
    error: { background: "#ffe5e0", color: "#8f2622" },
    unconfigured: { background: "#dde6f0", color: "#203247" },
  };
  return {
    padding: "0.45rem 0.75rem",
    borderRadius: "999px",
    whiteSpace: "nowrap",
    background: palette[state]?.background ?? "#dde6f0",
    color: palette[state]?.color ?? "#203247",
  };
}

const shellStyle: CSSProperties = {
  padding: 0,
};

const panelStyle: CSSProperties = {
  width: "100%",
  borderRadius: "24px",
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
  maxWidth: "54rem",
  lineHeight: 1.6,
  color: "#334862",
};

const topGridStyle: CSSProperties = {
  display: "grid",
  gap: "1rem",
  gridTemplateColumns: "minmax(0, 1.15fr) minmax(320px, 0.85fr)",
  marginTop: "1.5rem",
};

const gridStyle: CSSProperties = {
  display: "grid",
  gap: "1rem",
  gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
  marginTop: "1rem",
};

const activityGridStyle: CSSProperties = {
  display: "grid",
  gap: "1rem",
  gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
  marginTop: "1rem",
};

const cardStyle: CSSProperties = {
  padding: "1.25rem",
  borderRadius: "18px",
  background: "#f7fafc",
  border: "1px solid rgba(73, 98, 128, 0.18)",
  display: "grid",
  gap: "1rem",
};

const heroCardStyle: CSSProperties = {
  ...cardStyle,
  background: "linear-gradient(180deg, #f7fbff 0%, #eef4fb 100%)",
};

const cardHeaderStyle: CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  gap: "1rem",
  alignItems: "flex-start",
};

const cardActionRowStyle: CSSProperties = {
  display: "flex",
  gap: "0.65rem",
  flexWrap: "wrap",
};

const cardLabelStyle: CSSProperties = {
  margin: 0,
  fontSize: "0.82rem",
  letterSpacing: "0.12em",
  textTransform: "uppercase",
  color: "#5c728d",
};

const cardTitleStyle: CSSProperties = {
  margin: "0.5rem 0",
  fontSize: "1.4rem",
};

const checklistStyle: CSSProperties = {
  display: "grid",
  gap: "0.75rem",
};

const checklistItemStyle: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "20px minmax(0, 1fr)",
  gap: "0.85rem",
  alignItems: "start",
  padding: "0.9rem 1rem",
  borderRadius: "16px",
  background: "#fff",
  border: "1px solid rgba(73, 98, 128, 0.16)",
  textDecoration: "none",
};

const completeDotStyle: CSSProperties = {
  width: "0.9rem",
  height: "0.9rem",
  borderRadius: "999px",
  background: "#17663a",
  marginTop: "0.2rem",
};

const pendingDotStyle: CSSProperties = {
  width: "0.9rem",
  height: "0.9rem",
  borderRadius: "999px",
  background: "#c5d2e0",
  marginTop: "0.2rem",
};

const stackStyle: CSSProperties = {
  display: "grid",
  gap: "0.75rem",
};

const quickRowStyle: CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  gap: "0.75rem",
  alignItems: "center",
  padding: "0.85rem 0.95rem",
  borderRadius: "16px",
  background: "#fff",
  border: "1px solid rgba(73, 98, 128, 0.16)",
};

const presetGroupStyle: CSSProperties = {
  display: "grid",
  gap: "0.75rem",
  gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
};

const presetLinkStyle: CSSProperties = {
  display: "grid",
  gap: "0.3rem",
  padding: "0.9rem 1rem",
  borderRadius: "16px",
  background: "#fff",
  border: "1px solid rgba(73, 98, 128, 0.16)",
  textDecoration: "none",
};

const providerRowStyle: CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  gap: "0.75rem",
  alignItems: "flex-start",
  padding: "0.9rem 1rem",
  borderRadius: "16px",
  background: "#fff",
  border: "1px solid rgba(73, 98, 128, 0.16)",
};

const recentItemStyle: CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  gap: "0.75rem",
  alignItems: "center",
  padding: "0.9rem 1rem",
  borderRadius: "16px",
  background: "#fff",
  border: "1px solid rgba(73, 98, 128, 0.16)",
  textDecoration: "none",
};

const recentAccentStyle: CSSProperties = {
  padding: "0.35rem 0.6rem",
  borderRadius: "999px",
  background: "#e7eef6",
  color: "#203247",
  whiteSpace: "nowrap",
};

const metaStyle: CSSProperties = {
  margin: "0.2rem 0",
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

const secondaryButtonStyle: CSSProperties = {
  border: 0,
  borderRadius: "999px",
  padding: "0.75rem 1rem",
  background: "#162132",
  color: "#f5f7fb",
  cursor: "pointer",
};

const buttonStyle: CSSProperties = {
  border: 0,
  borderRadius: "999px",
  padding: "0.8rem 1rem",
  background: "#162132",
  color: "#f5f7fb",
  cursor: "pointer",
  textDecoration: "none",
};

const linkButtonStyle: CSSProperties = {
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

const errorStyle: CSSProperties = {
  color: "#9d1b1b",
  marginTop: "1rem",
};
