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
  listStrategyTemplates,
  listUniverses,
  logout,
  type BacktestRun,
  type CurrentUser,
  type ScreenRun,
  type StrategyTemplate,
  type UniverseSummary,
} from "@/lib/api";
import { backtestPresets, screenPresets, starterUniverseProfiles } from "@/lib/workflowPresets";

type LoadState = "loading" | "ready" | "error";

type RecentItem = {
  href: string;
  title: string;
  detail: string;
  accent: string;
};

type DashboardStat = {
  label: string;
  value: string;
  detail: string;
};

export function AppShell() {
  const router = useRouter();
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [universes, setUniverses] = useState<UniverseSummary[]>([]);
  const [screens, setScreens] = useState<ScreenRun[]>([]);
  const [backtests, setBacktests] = useState<BacktestRun[]>([]);
  const [templates, setTemplates] = useState<StrategyTemplate[]>([]);
  const [state, setState] = useState<LoadState>("loading");
  const [error, setError] = useState<string | null>(null);
  const [creatingProfileKey, setCreatingProfileKey] = useState<string | null>(null);

  useEffect(() => {
    let active = true;

    async function load() {
      try {
        const currentUser = await getCurrentUser();
        const workspaceId = currentUser.active_workspace?.id;
        const [universePayload, screenPayload, backtestPayload, templatePayload] =
          await Promise.all([
            listUniverses(workspaceId),
            listScreens(workspaceId, { limit: 5 }),
            listBacktests(workspaceId, { limit: 5 }),
            listStrategyTemplates({ workspaceId, pageSize: 5 }),
          ]);
        if (!active) {
          return;
        }
        setUser(currentUser);
        setUniverses(universePayload.results);
        setScreens(screenPayload.results);
        setBacktests(backtestPayload.results);
        setTemplates(templatePayload.results);
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
        setError(loadError instanceof Error ? loadError.message : "Unable to open your dashboard.");
        setState("error");
      }
    }

    void load();

    return () => {
      active = false;
    };
  }, [router]);

  const successfulScreenCount = screens.filter((screen) => screen.job.state === "succeeded").length;
  const successfulBacktestCount = backtests.filter(
    (backtest) => backtest.job.state === "succeeded",
  ).length;
  const displayName = user?.display_name || user?.username || "there";

  const onboardingItems = useMemo(
    () => [
      {
        label: "Add a universe",
        description: "Start from a built-in list or upload the names you already track.",
        href: "/app/universes",
        completed: universes.length > 0,
      },
      {
        label: "Run a screen",
        description: "Rank a saved universe and turn a broad list into a shortlist.",
        href: "/app/screens?preset=starter_us",
        completed: successfulScreenCount > 0,
      },
      {
        label: "Start a backtest",
        description: "Pressure-test the shortlist across history before you automate it.",
        href: "/app/backtests?preset=starter_compact",
        completed: successfulBacktestCount > 0,
      },
      {
        label: "Save a template",
        description: "Keep strong settings reusable so the next launch is one click away.",
        href: "/app/templates",
        completed: templates.length > 0,
      },
    ],
    [successfulBacktestCount, successfulScreenCount, templates.length, universes.length],
  );

  const dashboardStats = useMemo<DashboardStat[]>(
    () => [
      {
        label: "Saved universes",
        value: String(universes.length),
        detail:
          universes.length > 0 ? "Starting lists ready for new screens." : "Add your first research universe.",
      },
      {
        label: "Completed screens",
        value: String(successfulScreenCount),
        detail:
          successfulScreenCount > 0
            ? "Shortlists are ready to review."
            : "Run a ranking to surface candidates.",
      },
      {
        label: "Completed backtests",
        value: String(successfulBacktestCount),
        detail:
          successfulBacktestCount > 0
            ? "Historical validation is underway."
            : "Test a shortlist across history.",
      },
      {
        label: "Saved templates",
        value: String(templates.length),
        detail:
          templates.length > 0 ? "Reusable workflows are in place." : "Save your best setup for reuse.",
      },
    ],
    [successfulBacktestCount, successfulScreenCount, templates.length, universes.length],
  );

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
        description: "Built from a starter list on the dashboard.",
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
          <p style={eyebrowStyle}>Research dashboard</p>
          <h1 style={titleStyle}>Opening your workspace</h1>
          <p style={bodyStyle}>
            Pulling in your latest universes, screens, backtests, and saved templates.
          </p>
        </section>
      </main>
    );
  }

  if (state === "error") {
    return (
      <main style={shellStyle}>
        <section style={panelStyle}>
          <p style={eyebrowStyle}>Research dashboard</p>
          <h1 style={titleStyle}>Dashboard unavailable</h1>
          <p style={bodyStyle}>{error ?? "Unable to open your research dashboard."}</p>
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
            <p style={eyebrowStyle}>Research dashboard</p>
            <h1 style={titleStyle}>Welcome back, {displayName}</h1>
            <p style={bodyStyle}>
              Pick up where you left off: run a fresh screen, test a shortlist across history, and
              turn the strongest workflow into something reusable.
            </p>
          </div>
          <div style={headerActionsStyle}>
            <Link href="/app/screens?preset=starter_us" style={linkButtonStyle}>
              Run screen
            </Link>
            <Link href="/app/backtests?preset=starter_compact" style={ghostLinkStyle}>
              Start backtest
            </Link>
            <button type="button" style={outlineButtonStyle} onClick={handleLogout}>
              Log out
            </button>
          </div>
        </div>

        {error ? <p style={errorStyle}>{error}</p> : null}

        <div style={topGridStyle}>
          <section style={heroCardStyle}>
            <div style={cardHeaderStyle}>
              <div>
                <p style={cardLabelStyle}>Keep moving</p>
                <h2 style={cardTitleStyle}>Build a repeatable workflow</h2>
              </div>
              <span style={pillStyle}>
                {onboardingItems.filter((item) => item.completed).length}/{onboardingItems.length} complete
              </span>
            </div>
            <p style={sectionLeadStyle}>
              Use the same flow every time: define the list, run the ranking, pressure-test the
              shortlist, and save the approach once it earns a place in your routine.
            </p>
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
                <p style={cardLabelStyle}>Research at a glance</p>
                <h2 style={cardTitleStyle}>Current momentum</h2>
              </div>
              <Link href="/app/history" style={ghostLinkStyle}>
                Open history
              </Link>
            </div>
            <div style={summaryGridStyle}>
              {dashboardStats.map((item) => (
                <div key={item.label} style={summaryTileStyle}>
                  <div style={summaryValueStyle}>{item.value}</div>
                  <div style={summaryLabelStyle}>{item.label}</div>
                  <div style={metaStyle}>{item.detail}</div>
                </div>
              ))}
            </div>
          </section>
        </div>

        <div style={gridStyle}>
          <section style={cardStyle}>
            <div style={cardHeaderStyle}>
              <div>
                <p style={cardLabelStyle}>Starting lists</p>
                <h2 style={cardTitleStyle}>Build your first universe</h2>
              </div>
              <Link href="/app/universes" style={ghostLinkStyle}>
                Open universes
              </Link>
            </div>
            <p style={sectionLeadStyle}>
              Use a starter list when you want to move quickly without building inputs from
              scratch.
            </p>
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
                    {creatingProfileKey === profile.key ? "Adding..." : "Add universe"}
                  </button>
                </div>
              ))}
            </div>
          </section>

          <section style={cardStyle}>
            <div style={cardHeaderStyle}>
              <div>
                <p style={cardLabelStyle}>Fast launch</p>
                <h2 style={cardTitleStyle}>Start with a proven setup</h2>
              </div>
            </div>
            <p style={sectionLeadStyle}>
              Use a standard preset when you want to get into the research quickly and adjust from
              real results later.
            </p>
            <div style={presetGroupStyle}>
              <div style={presetColumnStyle}>
                <p style={miniLabelStyle}>Screen presets</p>
                <div style={stackStyle}>
                  {screenPresets.map((preset) => (
                    <Link key={preset.id} href={`/app/screens?preset=${preset.id}`} style={presetLinkStyle}>
                      <strong>{preset.label}</strong>
                      <div style={metaStyle}>{preset.description}</div>
                    </Link>
                  ))}
                </div>
              </div>
              <div style={presetColumnStyle}>
                <p style={miniLabelStyle}>Backtest presets</p>
                <div style={stackStyle}>
                  {backtestPresets.map((preset) => (
                    <Link key={preset.id} href={`/app/backtests?preset=${preset.id}`} style={presetLinkStyle}>
                      <strong>{preset.label}</strong>
                      <div style={metaStyle}>{preset.description}</div>
                    </Link>
                  ))}
                </div>
              </div>
            </div>
          </section>

          <section style={cardStyle}>
            <div style={cardHeaderStyle}>
              <div>
                <p style={cardLabelStyle}>Research account</p>
                <h2 style={cardTitleStyle}>{user.active_workspace?.name ?? "Research workspace"}</h2>
              </div>
              <Link href="/app/settings" style={ghostLinkStyle}>
                Open settings
              </Link>
            </div>
            <p style={sectionLeadStyle}>
              Keep saved research, templates, and alerts attached to one workspace so the work
              stays organized over time.
            </p>
            <div style={detailListStyle}>
              <div style={detailRowStyle}>
                <div>
                  <div style={detailLabelStyle}>Workspace access</div>
                  <strong>{humanizeLabel(user.active_workspace?.role ?? "member")}</strong>
                </div>
                <span style={recentAccentStyle}>Private workspace</span>
              </div>
              <div style={detailRowStyle}>
                <div>
                  <div style={detailLabelStyle}>Signed in as</div>
                  <strong>{user.username}</strong>
                  {user.email ? <div style={metaStyle}>{user.email}</div> : null}
                </div>
              </div>
            </div>
            <div style={cardActionRowStyle}>
              <Link href="/app/templates" style={linkButtonStyle}>
                Open templates
              </Link>
              <Link href="/app/history" style={ghostLinkStyle}>
                Open history
              </Link>
              <Link href="/app/alerts" style={ghostLinkStyle}>
                Open alerts
              </Link>
            </div>
          </section>
        </div>

        <div style={activityGridStyle}>
          <RecentList
            title="Recent screens"
            emptyMessage="No screens yet. Start with a saved universe and run your first ranking."
            items={screens.map((screen) => ({
              href: `/app/screens/${screen.id}`,
              title: `Screen #${screen.id}`,
              detail: `${screen.universe.name} · ${humanizeLabel(screen.job.state)}`,
              accent: screen.is_starred ? "Starred" : `${screen.result_count} ranked`,
            }))}
            ctaHref="/app/screens?preset=starter_us"
            ctaLabel="Run screen"
          />
          <RecentList
            title="Recent backtests"
            emptyMessage="No backtests yet. Test a shortlist across history once a screen looks worth investigating."
            items={backtests.map((backtest) => ({
              href: `/app/backtests/${backtest.id}`,
              title: `Backtest #${backtest.id}`,
              detail: `${backtest.start_date} to ${backtest.end_date}`,
              accent:
                typeof backtest.summary.total_return === "number"
                  ? `${(backtest.summary.total_return * 100).toFixed(2)}% total return`
                  : humanizeLabel(backtest.job.state),
            }))}
            ctaHref="/app/backtests?preset=starter_compact"
            ctaLabel="Start backtest"
          />
          <RecentList
            title="Saved templates"
            emptyMessage="No templates yet. Save a strong run once the setup feels worth repeating."
            items={templates.map((template) => ({
              href:
                template.workflow_kind === "screen"
                  ? `/app/screens?template_id=${template.id}`
                  : `/app/backtests?template_id=${template.id}`,
              title: template.name,
              detail: `${humanizeLabel(template.workflow_kind)} · ${template.universe.name}`,
              accent: template.is_starred ? "Starred" : template.last_used_at ? "Used recently" : "New",
            }))}
            ctaHref="/app/templates"
            ctaLabel="Open templates"
          />
          <RecentList
            title="Saved universes"
            emptyMessage="No universes yet. Add one from a starter list or upload your own names."
            items={universes.slice(0, 5).map((universe) => ({
              href: `/app/universes/${universe.id}`,
              title: universe.name,
              detail: `${universe.entry_count} names · ${humanizeLabel(universe.source_type)}`,
              accent: universe.is_starred ? "Starred" : universe.profile_key ? "Built-in list" : "Custom list",
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
  items: RecentItem[];
  ctaHref: string;
  ctaLabel: string;
}) {
  return (
    <section style={cardStyle}>
      <div style={cardHeaderStyle}>
        <div>
          <p style={cardLabelStyle}>Recent research</p>
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

function humanizeLabel(value: string): string {
  return value
    .split(/[_\s]+/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

const shellStyle: CSSProperties = {
  padding: 0,
};

const panelStyle: CSSProperties = {
  width: "100%",
  borderRadius: "24px",
  padding: "1.75rem",
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

const headerActionsStyle: CSSProperties = {
  display: "flex",
  gap: "0.65rem",
  flexWrap: "wrap",
  alignItems: "center",
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
  margin: "0.6rem 0 0",
  maxWidth: "54rem",
  lineHeight: 1.6,
  color: "#334862",
};

const topGridStyle: CSSProperties = {
  display: "grid",
  gap: "1rem",
  gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))",
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

const sectionLeadStyle: CSSProperties = {
  margin: 0,
  color: "#496280",
  lineHeight: 1.55,
};

const summaryGridStyle: CSSProperties = {
  display: "grid",
  gap: "0.75rem",
  gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))",
};

const summaryTileStyle: CSSProperties = {
  padding: "0.95rem 1rem",
  borderRadius: "16px",
  background: "#fff",
  border: "1px solid rgba(73, 98, 128, 0.16)",
};

const summaryValueStyle: CSSProperties = {
  fontSize: "1.75rem",
  fontWeight: 700,
  letterSpacing: "-0.04em",
};

const summaryLabelStyle: CSSProperties = {
  marginTop: "0.25rem",
  color: "#203247",
  fontWeight: 600,
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

const presetColumnStyle: CSSProperties = {
  display: "grid",
  gap: "0.65rem",
};

const miniLabelStyle: CSSProperties = {
  margin: 0,
  fontSize: "0.78rem",
  letterSpacing: "0.14em",
  textTransform: "uppercase",
  color: "#5c728d",
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

const detailListStyle: CSSProperties = {
  display: "grid",
  gap: "0.75rem",
};

const detailRowStyle: CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  gap: "0.75rem",
  alignItems: "center",
  padding: "0.9rem 1rem",
  borderRadius: "16px",
  background: "#fff",
  border: "1px solid rgba(73, 98, 128, 0.16)",
};

const detailLabelStyle: CSSProperties = {
  fontSize: "0.82rem",
  letterSpacing: "0.08em",
  textTransform: "uppercase",
  color: "#5c728d",
  marginBottom: "0.25rem",
};

const recentItemStyle: CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  gap: "0.75rem",
  alignItems: "flex-start",
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

const pillStyle: CSSProperties = {
  alignSelf: "flex-start",
  padding: "0.45rem 0.75rem",
  borderRadius: "999px",
  background: "#dde6f0",
  color: "#162132",
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

const outlineButtonStyle: CSSProperties = {
  border: "1px solid rgba(73, 98, 128, 0.22)",
  borderRadius: "999px",
  padding: "0.8rem 1rem",
  background: "rgba(255, 255, 255, 0.72)",
  color: "#162132",
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

const errorStyle: CSSProperties = {
  color: "#9d1b1b",
  marginTop: "1rem",
};
