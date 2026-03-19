"use client";

import { startTransition, useEffect, useState, type CSSProperties, type FormEvent } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import {
  ApiError,
  getAccountSettings,
  updateCurrentUser,
  updateWorkspace,
  type AccountSettingsResponse,
  type CurrentUser,
} from "@/lib/api";

type LoadState = "loading" | "ready" | "error";

export function SettingsHub() {
  const router = useRouter();
  const [settings, setSettings] = useState<AccountSettingsResponse | null>(null);
  const [selectedWorkspaceId, setSelectedWorkspaceId] = useState<number | null>(null);
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [email, setEmail] = useState("");
  const [workspaceName, setWorkspaceName] = useState("");
  const [workspaceTimezone, setWorkspaceTimezone] = useState("");
  const [state, setState] = useState<LoadState>("loading");
  const [error, setError] = useState<string | null>(null);
  const [isSavingProfile, setIsSavingProfile] = useState(false);
  const [isSavingWorkspace, setIsSavingWorkspace] = useState(false);

  useEffect(() => {
    let active = true;

    async function load() {
      try {
        const payload = await getAccountSettings();
        if (!active) {
          return;
        }
        applyPayload(payload);
        setSelectedWorkspaceId(payload.workspace.summary.id);
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
        setError(loadError instanceof Error ? loadError.message : "Unable to load account settings.");
        setState("error");
      }
    }

    void load();

    return () => {
      active = false;
    };
  }, [router]);

  useEffect(() => {
    if (selectedWorkspaceId == null || state === "loading" || settings == null) {
      return;
    }
    if (selectedWorkspaceId === settings.workspace.summary.id) {
      return;
    }

    const workspaceId = selectedWorkspaceId;
    let active = true;

    async function reloadWorkspace() {
      try {
        const payload = await getAccountSettings(workspaceId);
        if (!active) {
          return;
        }
        applyPayload(payload);
      } catch (loadError) {
        if (!active) {
          return;
        }
        setError(loadError instanceof Error ? loadError.message : "Unable to reload workspace settings.");
      }
    }

    void reloadWorkspace();

    return () => {
      active = false;
    };
  }, [selectedWorkspaceId, settings, state]);

  function applyPayload(payload: AccountSettingsResponse) {
    setSettings(payload);
    setFirstName(payload.user.first_name);
    setLastName(payload.user.last_name);
    setEmail(payload.user.email);
    setWorkspaceName(payload.workspace.summary.name);
    setWorkspaceTimezone(payload.workspace.summary.timezone);
  }

  async function refreshSettings(workspaceId?: number) {
    const payload = await getAccountSettings(workspaceId ?? selectedWorkspaceId ?? undefined);
    applyPayload(payload);
    setSelectedWorkspaceId(payload.workspace.summary.id);
  }

  async function handleSaveProfile(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsSavingProfile(true);
    setError(null);
    try {
      const updatedUser = await updateCurrentUser({
        firstName,
        lastName,
        email,
      });
      await refreshSettings(updatedUser.active_workspace?.id ?? selectedWorkspaceId ?? undefined);
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : "Unable to save your profile.");
    } finally {
      setIsSavingProfile(false);
    }
  }

  async function handleSaveWorkspace(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (settings == null) {
      return;
    }
    setIsSavingWorkspace(true);
    setError(null);
    try {
      await updateWorkspace(settings.workspace.summary.id, {
        name: workspaceName,
        timezone: workspaceTimezone,
      });
      await refreshSettings(settings.workspace.summary.id);
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : "Unable to save workspace settings.");
    } finally {
      setIsSavingWorkspace(false);
    }
  }

  if (state === "loading") {
    return (
      <main style={pageStyle}>
        <section style={panelStyle}>
          <p style={eyebrowStyle}>Settings</p>
          <h1 style={titleStyle}>Loading account settings</h1>
          <p style={bodyStyle}>Collecting profile, workspace, plan, and support data.</p>
        </section>
      </main>
    );
  }

  if (state === "error" || settings == null) {
    return (
      <main style={pageStyle}>
        <section style={panelStyle}>
          <p style={eyebrowStyle}>Settings</p>
          <h1 style={titleStyle}>Settings unavailable</h1>
          <p style={bodyStyle}>{error ?? "Unable to load account settings."}</p>
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
            <p style={eyebrowStyle}>Settings</p>
            <h1 style={titleStyle}>Account, workspace, and plan readiness</h1>
            <p style={bodyStyle}>
              This page consolidates account profile edits, workspace settings, plan and quota
              visibility, and the current research-only/commercial-readiness notes.
            </p>
          </div>
          <Link href="/app/providers" style={ghostLinkStyle}>
            Provider ops
          </Link>
        </div>

        {error ? <p style={errorStyle}>{error}</p> : null}

        <label style={fieldStyle}>
          <span style={labelStyle}>Workspace</span>
          <select
            value={selectedWorkspaceId ?? ""}
            onChange={(event) => setSelectedWorkspaceId(Number(event.target.value))}
            style={inputStyle}
          >
            {settings.user.workspaces.map((workspace) => (
              <option key={workspace.id} value={workspace.id}>
                {workspace.name}
              </option>
            ))}
          </select>
        </label>

        <div style={gridStyle}>
          <section style={cardStyle}>
            <div style={cardHeaderStyle}>
              <div>
                <p style={sectionLabelStyle}>Profile</p>
                <h2 style={sectionTitleStyle}>{settings.user.display_name}</h2>
              </div>
            </div>
            <form onSubmit={handleSaveProfile} style={formStyle}>
              <div style={fieldGridStyle}>
                <label style={fieldStyle}>
                  <span style={labelStyle}>First name</span>
                  <input type="text" value={firstName} onChange={(event) => setFirstName(event.target.value)} style={inputStyle} />
                </label>
                <label style={fieldStyle}>
                  <span style={labelStyle}>Last name</span>
                  <input type="text" value={lastName} onChange={(event) => setLastName(event.target.value)} style={inputStyle} />
                </label>
              </div>
              <label style={fieldStyle}>
                <span style={labelStyle}>Email</span>
                <input type="email" value={email} onChange={(event) => setEmail(event.target.value)} style={inputStyle} />
              </label>
              <button type="submit" style={primaryButtonStyle} disabled={isSavingProfile}>
                {isSavingProfile ? "Saving..." : "Save profile"}
              </button>
            </form>
          </section>

          <section style={cardStyle}>
            <div style={cardHeaderStyle}>
              <div>
                <p style={sectionLabelStyle}>Workspace</p>
                <h2 style={sectionTitleStyle}>{settings.workspace.summary.name}</h2>
              </div>
              <span style={pillStyle}>{settings.plan.label}</span>
            </div>
            <form onSubmit={handleSaveWorkspace} style={formStyle}>
              <label style={fieldStyle}>
                <span style={labelStyle}>Workspace name</span>
                <input
                  type="text"
                  value={workspaceName}
                  onChange={(event) => setWorkspaceName(event.target.value)}
                  style={inputStyle}
                />
              </label>
              <label style={fieldStyle}>
                <span style={labelStyle}>Timezone</span>
                <input
                  type="text"
                  value={workspaceTimezone}
                  onChange={(event) => setWorkspaceTimezone(event.target.value)}
                  style={inputStyle}
                />
              </label>
              <button type="submit" style={secondaryButtonStyle} disabled={isSavingWorkspace}>
                {isSavingWorkspace ? "Saving..." : "Save workspace"}
              </button>
            </form>
          </section>
        </div>

        <div style={gridStyle}>
          <section style={cardStyle}>
            <div style={cardHeaderStyle}>
              <div>
                <p style={sectionLabelStyle}>Usage</p>
                <h2 style={sectionTitleStyle}>Workspace quotas and activity</h2>
              </div>
            </div>
            <div style={statsGridStyle}>
              <StatCard label="Members" value={String(settings.workspace.member_count)} detail="Workspace memberships" />
              <StatCard label="Active jobs" value={String(settings.workspace.active_jobs.total)} detail={`${settings.workspace.active_jobs.research} research jobs`} />
              <StatCard label="Universes" value={String(settings.workspace.resource_counts.universes)} detail="Saved research universes" />
              <StatCard label="Templates" value={String(settings.workspace.resource_counts.templates)} detail="Reusable launch presets" />
              <StatCard label="Schedules" value={String(settings.workspace.resource_counts.schedules)} detail="Automated strategies" />
              <StatCard label="Provider failures" value={String(settings.workspace.recent_activity.provider_failures_total)} detail="Historical provider failures" />
            </div>
            <div style={calloutStyle}>
              <strong>Concurrency defaults</strong>
              <p style={metaStyle}>
                Total jobs: {settings.workspace.limits.total_jobs}. Research jobs: {settings.workspace.limits.research_jobs}. Smoke
                jobs: {settings.workspace.limits.smoke_jobs}. These limits are visible now, but per-plan enforcement is still groundwork only.
              </p>
            </div>
          </section>

          <section style={cardStyle}>
            <div style={cardHeaderStyle}>
              <div>
                <p style={sectionLabelStyle}>Plan</p>
                <h2 style={sectionTitleStyle}>{settings.plan.label}</h2>
              </div>
            </div>
            <p style={bodyStyle}>{settings.plan.description}</p>
            <div style={stackStyle}>
              <DetailRow label="Seat guidance" value={settings.plan.seat_guidance} />
              <DetailRow label="Automation guidance" value={settings.plan.automation_guidance} />
              <DetailRow label="Current plan type" value={settings.plan.workspace_plan_type ?? settings.workspace.summary.plan_type} />
            </div>
            <div style={tagRowStyle}>
              {settings.plan.feature_flags.map((flag) => (
                <span key={flag} style={tagStyle}>
                  {flag}
                </span>
              ))}
            </div>
            <div style={planCatalogStyle}>
              {settings.plan_catalog.map((plan) => (
                <article
                  key={plan.key}
                  style={{
                    ...planCardStyle,
                    borderColor: plan.key === settings.plan.key ? "rgba(22, 33, 50, 0.35)" : "rgba(73, 98, 128, 0.14)",
                  }}
                >
                  <strong>{plan.label}</strong>
                  <p style={metaStyle}>{plan.description}</p>
                  <p style={metaStyle}>{plan.seat_guidance}</p>
                </article>
              ))}
            </div>
          </section>
        </div>

        <div style={gridStyle}>
          <section style={cardStyle}>
            <div style={cardHeaderStyle}>
              <div>
                <p style={sectionLabelStyle}>Commercial readiness</p>
                <h2 style={sectionTitleStyle}>Current product posture</h2>
              </div>
            </div>
            <div style={stackStyle}>
              <NoticeBlock title="Research-only positioning" body={settings.notices.research_only} />
              <NoticeBlock title="Provider usage" body={settings.notices.provider_usage} />
              <NoticeBlock title="Billing" body={settings.notices.billing} />
            </div>
            <div style={authListStyle}>
              <DetailRow
                label="Session auth"
                value={settings.auth_capabilities.session_auth_enabled ? "Enabled" : "Disabled"}
              />
              <DetailRow
                label="Social login"
                value={settings.auth_capabilities.social_login_enabled ? "Enabled" : "Not enabled"}
              />
              <DetailRow
                label="Billing"
                value={settings.auth_capabilities.billing_enabled ? "Enabled" : "Not enabled"}
              />
              <DetailRow label="Support contact" value={settings.notices.support_contact} />
            </div>
          </section>

          {settings.support_overview ? (
            <section style={cardStyle}>
              <div style={cardHeaderStyle}>
                <div>
                  <p style={sectionLabelStyle}>Support overview</p>
                  <h2 style={sectionTitleStyle}>Internal operator snapshot</h2>
                </div>
                <a href="http://localhost:8000/admin/" style={ghostLinkStyle}>
                  Django admin
                </a>
              </div>
              <div style={statsGridStyle}>
                <StatCard label="Users" value={String(settings.support_overview.user_count)} detail="All platform users" />
                <StatCard label="Workspaces" value={String(settings.support_overview.workspace_count)} detail="All workspaces" />
                <StatCard label="Active jobs" value={String(settings.support_overview.active_job_count)} detail="Queued or running" />
                <StatCard label="7d failures" value={String(settings.support_overview.failed_job_count_7d)} detail="Recent failed jobs" />
              </div>
              <div style={stackStyle}>
                {settings.support_overview.recent_failures.map((item) => (
                  <div key={`${item.job_id}-${item.updated_at}`} style={supportFailureStyle}>
                    <strong>#{item.job_id} · {item.job_type}</strong>
                    <div style={metaStyle}>{item.workspace_name}</div>
                    <div style={metaStyle}>{item.error_message ?? item.error_code ?? "Unknown failure"}</div>
                  </div>
                ))}
              </div>
            </section>
          ) : null}
        </div>
      </section>
    </main>
  );
}

function StatCard({ label, value, detail }: { label: string; value: string; detail: string }) {
  return (
    <div style={statCardStyle}>
      <span style={labelStyle}>{label}</span>
      <strong style={statValueStyle}>{value}</strong>
      <span style={metaStyle}>{detail}</span>
    </div>
  );
}

function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <div style={detailRowStyle}>
      <span style={labelStyle}>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function NoticeBlock({ title, body }: { title: string; body: string }) {
  return (
    <div style={noticeStyle}>
      <strong>{title}</strong>
      <p style={metaStyle}>{body}</p>
    </div>
  );
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
  display: "grid",
  gap: "1.5rem",
};

const headerRowStyle: CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  alignItems: "flex-start",
  gap: "1rem",
  flexWrap: "wrap",
};

const gridStyle: CSSProperties = {
  display: "grid",
  gap: "1rem",
  gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))",
};

const fieldGridStyle: CSSProperties = {
  display: "grid",
  gap: "0.85rem",
  gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
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

const formStyle: CSSProperties = {
  display: "grid",
  gap: "0.85rem",
};

const fieldStyle: CSSProperties = {
  display: "grid",
  gap: "0.45rem",
};

const inputStyle: CSSProperties = {
  width: "100%",
  borderRadius: "14px",
  border: "1px solid rgba(73, 98, 128, 0.22)",
  padding: "0.85rem 0.95rem",
  background: "#fff",
  fontSize: "0.98rem",
};

const statsGridStyle: CSSProperties = {
  display: "grid",
  gap: "0.85rem",
  gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))",
};

const statCardStyle: CSSProperties = {
  padding: "0.9rem 1rem",
  borderRadius: "16px",
  background: "#fff",
  border: "1px solid rgba(73, 98, 128, 0.14)",
  display: "grid",
  gap: "0.3rem",
};

const statValueStyle: CSSProperties = {
  fontSize: "1.15rem",
};

const calloutStyle: CSSProperties = {
  padding: "1rem",
  borderRadius: "16px",
  background: "#eef4fa",
  display: "grid",
  gap: "0.35rem",
};

const stackStyle: CSSProperties = {
  display: "grid",
  gap: "0.75rem",
};

const detailRowStyle: CSSProperties = {
  display: "grid",
  gap: "0.25rem",
};

const tagRowStyle: CSSProperties = {
  display: "flex",
  gap: "0.55rem",
  flexWrap: "wrap",
};

const tagStyle: CSSProperties = {
  padding: "0.45rem 0.7rem",
  borderRadius: "999px",
  background: "#dde6f0",
  color: "#162132",
};

const planCatalogStyle: CSSProperties = {
  display: "grid",
  gap: "0.85rem",
  gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
};

const planCardStyle: CSSProperties = {
  padding: "0.9rem 1rem",
  borderRadius: "16px",
  background: "#fff",
  border: "1px solid rgba(73, 98, 128, 0.14)",
  display: "grid",
  gap: "0.35rem",
};

const noticeStyle: CSSProperties = {
  padding: "0.95rem 1rem",
  borderRadius: "16px",
  background: "#fff",
  border: "1px solid rgba(73, 98, 128, 0.14)",
  display: "grid",
  gap: "0.35rem",
};

const authListStyle: CSSProperties = {
  display: "grid",
  gap: "0.75rem",
};

const supportFailureStyle: CSSProperties = {
  padding: "0.9rem 1rem",
  borderRadius: "16px",
  background: "#fff",
  border: "1px solid rgba(73, 98, 128, 0.14)",
  display: "grid",
  gap: "0.25rem",
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

const pillStyle: CSSProperties = {
  padding: "0.45rem 0.7rem",
  borderRadius: "999px",
  background: "#162132",
  color: "#f5f7fb",
  whiteSpace: "nowrap",
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

const errorStyle: CSSProperties = {
  color: "#9d1b1b",
};
