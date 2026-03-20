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
  createRunSchedule,
  deleteRunSchedule,
  getCurrentUser,
  listRunSchedules,
  listStrategyTemplates,
  triggerRunSchedule,
  updateRunSchedule,
  type CurrentUser,
  type RunSchedule,
  type StrategyTemplate,
} from "@/lib/api";

type LoadState = "loading" | "ready" | "error";

type ScheduleFormState = {
  templateId: string;
  name: string;
  description: string;
  timezone: string;
  cronMinute: string;
  cronHour: string;
  cronDayOfWeek: string;
  cronDayOfMonth: string;
  cronMonthOfYear: string;
  notifyChannel: RunSchedule["notify_channel"];
  notifyEmail: string;
  notifyWebhookUrl: string;
  notifyOnSuccess: boolean;
  notifyOnFailure: boolean;
  reviewStatus: RunSchedule["review_status"];
  reviewNotes: string;
  isEnabled: boolean;
};

const initialFormState: ScheduleFormState = {
  templateId: "",
  name: "",
  description: "",
  timezone: "UTC",
  cronMinute: "0",
  cronHour: "13",
  cronDayOfWeek: "1-5",
  cronDayOfMonth: "*",
  cronMonthOfYear: "*",
  notifyChannel: "email",
  notifyEmail: "",
  notifyWebhookUrl: "",
  notifyOnSuccess: true,
  notifyOnFailure: true,
  reviewStatus: "draft",
  reviewNotes: "",
  isEnabled: true,
};

export function ScheduleHub() {
  const router = useRouter();
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [templates, setTemplates] = useState<StrategyTemplate[]>([]);
  const [schedules, setSchedules] = useState<RunSchedule[]>([]);
  const [state, setState] = useState<LoadState>("loading");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [form, setForm] = useState<ScheduleFormState>(initialFormState);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [activeScheduleId, setActiveScheduleId] = useState<number | null>(null);

  useEffect(() => {
    let active = true;

    async function load() {
      try {
        const currentUser = await getCurrentUser();
        const workspaceId = currentUser.active_workspace?.id;
        const [templatePayload, schedulePayload] = await Promise.all([
          listStrategyTemplates({ workspaceId, pageSize: 100 }),
          listRunSchedules({ workspaceId, pageSize: 100 }),
        ]);
        if (!active) {
          return;
        }
        setUser(currentUser);
        setTemplates(templatePayload.results);
        setSchedules(schedulePayload.results);
        setForm((current) => ({
          ...current,
          timezone: currentUser.active_workspace?.timezone ?? "UTC",
        }));
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
            : "Unable to load schedules.",
        );
        setState("error");
      }
    }

    void load();

    return () => {
      active = false;
    };
  }, [router]);

  async function refresh(currentUser: CurrentUser) {
    const workspaceId = currentUser.active_workspace?.id;
    const [templatePayload, schedulePayload] = await Promise.all([
      listStrategyTemplates({ workspaceId, pageSize: 100 }),
      listRunSchedules({ workspaceId, pageSize: 100 }),
    ]);
    setTemplates(templatePayload.results);
    setSchedules(schedulePayload.results);
  }

  async function handleCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (user == null) {
      return;
    }
    setError(null);
    setNotice(null);
    setIsSubmitting(true);
    try {
      await createRunSchedule({
        workspaceId: user.active_workspace?.id,
        strategyTemplateId: Number(form.templateId),
        name: form.name.trim(),
        description: form.description.trim(),
        timezone: form.timezone.trim(),
        cronMinute: form.cronMinute.trim(),
        cronHour: form.cronHour.trim(),
        cronDayOfWeek: form.cronDayOfWeek.trim(),
        cronDayOfMonth: form.cronDayOfMonth.trim(),
        cronMonthOfYear: form.cronMonthOfYear.trim(),
        notifyChannel: form.notifyChannel,
        notifyEmail: form.notifyEmail.trim(),
        notifyWebhookUrl: form.notifyWebhookUrl.trim(),
        notifyOnSuccess: form.notifyOnSuccess,
        notifyOnFailure: form.notifyOnFailure,
        reviewStatus: form.reviewStatus,
        reviewNotes: form.reviewNotes.trim(),
        isEnabled: form.isEnabled,
      });
      setForm({
        ...initialFormState,
        timezone: user.active_workspace?.timezone ?? "UTC",
      });
      await refresh(user);
      setNotice(
        "Schedule saved. Your template is ready to run on a recurring cadence.",
      );
    } catch (createError) {
      setError(formatApiError(createError, "Unable to create schedule."));
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleToggle(schedule: RunSchedule) {
    if (user == null) {
      return;
    }
    setActiveScheduleId(schedule.id);
    setError(null);
    setNotice(null);
    try {
      await updateRunSchedule(schedule.id, { isEnabled: !schedule.is_enabled });
      await refresh(user);
      setNotice(schedule.is_enabled ? "Schedule paused." : "Schedule enabled.");
    } catch (updateError) {
      setError(formatApiError(updateError, "Unable to update this schedule."));
    } finally {
      setActiveScheduleId(null);
    }
  }

  async function handleQuickEdit(schedule: RunSchedule) {
    if (user == null) {
      return;
    }
    const nextName = window.prompt("Schedule name", schedule.name);
    if (nextName == null || nextName.trim() === "") {
      return;
    }
    const nextHour =
      window.prompt("Hour (24h)", schedule.cron_hour) ?? schedule.cron_hour;
    const nextMinute =
      window.prompt("Minute", schedule.cron_minute) ?? schedule.cron_minute;
    const nextDayOfWeek =
      window.prompt("Days of week", schedule.cron_day_of_week) ??
      schedule.cron_day_of_week;
    const nextChannel =
      window.prompt("Alert channel", schedule.notify_channel) ??
      schedule.notify_channel;
    const nextEmail =
      window.prompt("Alert email", schedule.notify_email) ??
      schedule.notify_email;
    const nextWebhook =
      window.prompt("Alert webhook URL", schedule.notify_webhook_url ?? "") ??
      schedule.notify_webhook_url ??
      "";
    const nextReviewStatus =
      window.prompt("Review status", schedule.review_status) ??
      schedule.review_status;
    setActiveScheduleId(schedule.id);
    setError(null);
    setNotice(null);
    try {
      await updateRunSchedule(schedule.id, {
        name: nextName.trim(),
        cronHour: nextHour.trim(),
        cronMinute: nextMinute.trim(),
        cronDayOfWeek: nextDayOfWeek.trim(),
        notifyChannel: nextChannel as RunSchedule["notify_channel"],
        notifyEmail: nextEmail.trim(),
        notifyWebhookUrl: nextWebhook.trim(),
        reviewStatus: nextReviewStatus as RunSchedule["review_status"],
      });
      await refresh(user);
      setNotice("Schedule updated.");
    } catch (updateError) {
      setError(formatApiError(updateError, "Unable to update this schedule."));
    } finally {
      setActiveScheduleId(null);
    }
  }

  async function handleTrigger(schedule: RunSchedule) {
    setActiveScheduleId(schedule.id);
    setError(null);
    setNotice(null);
    try {
      const launched = await triggerRunSchedule(schedule.id);
      startTransition(() => {
        router.push(
          launched.workflow_kind === "screen"
            ? `/app/screens/${launched.run.id}`
            : `/app/backtests/${launched.run.id}`,
        );
      });
    } catch (triggerError) {
      setError(
        formatApiError(triggerError, "Unable to trigger this schedule."),
      );
    } finally {
      setActiveScheduleId(null);
    }
  }

  async function handleDelete(schedule: RunSchedule) {
    if (
      user == null ||
      !window.confirm(`Delete schedule "${schedule.name}"?`)
    ) {
      return;
    }
    setActiveScheduleId(schedule.id);
    setError(null);
    setNotice(null);
    try {
      await deleteRunSchedule(schedule.id);
      await refresh(user);
      setNotice("Schedule deleted.");
    } catch (deleteError) {
      setError(formatApiError(deleteError, "Unable to delete this schedule."));
    } finally {
      setActiveScheduleId(null);
    }
  }

  if (state === "loading") {
    return (
      <main style={pageStyle}>
        <section style={panelStyle}>
          <p style={eyebrowStyle}>Schedules</p>
          <h1 style={titleStyle}>Loading recurring workflows</h1>
        </section>
      </main>
    );
  }

  if (state === "error" || user == null) {
    return (
      <main style={pageStyle}>
        <section style={panelStyle}>
          <p style={eyebrowStyle}>Schedules</p>
          <h1 style={titleStyle}>Schedules unavailable</h1>
          <p style={bodyStyle}>
            {error ?? "Unable to open your schedule workspace."}
          </p>
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
            <p style={eyebrowStyle}>Schedules</p>
            <h1 style={titleStyle}>
              Keep proven workflows running on schedule
            </h1>
          </div>
          <div style={actionRowStyle}>
            <Link href="/app/templates" style={ghostLinkStyle}>
              Open templates
            </Link>
            <Link href="/app/alerts" style={ghostLinkStyle}>
              Open alerts
            </Link>
            <Link href="/app" style={ghostLinkStyle}>
              Dashboard
            </Link>
          </div>
        </div>

        <p style={bodyStyle}>
          Attach a saved template to a recurring cadence so your best screens
          and backtests keep running without manual setup each week. Use manual
          launches when you want to test a new schedule before relying on it.
        </p>

        {error ? <p style={errorStyle}>{error}</p> : null}
        {notice ? <p style={infoStyle}>{notice}</p> : null}

        <section style={sectionCardStyle}>
          <div style={cardHeaderStyle}>
            <div>
              <p style={sectionLabelStyle}>Save schedule</p>
              <h2 style={cardTitleStyle}>
                Attach a template to a recurring cadence
              </h2>
            </div>
            <span style={pillStyle}>
              {templates.length} templates available
            </span>
          </div>

          {templates.length === 0 ? (
            <div style={emptyStateStyle}>
              <p style={bodyStyle}>
                No saved templates yet. Save a strong screen or backtest as a
                template first, then come back here to run it on a schedule.
              </p>
              <div style={actionRowStyle}>
                <Link href="/app/templates" style={primaryLinkStyle}>
                  Open templates
                </Link>
                <Link href="/app/history" style={ghostLinkStyle}>
                  Open history
                </Link>
              </div>
            </div>
          ) : (
            <form style={formGridStyle} onSubmit={handleCreate}>
              <label style={fieldStyle}>
                <span style={labelStyle}>Template</span>
                <select
                  value={form.templateId}
                  onChange={(event) =>
                    setForm((current) => ({
                      ...current,
                      templateId: event.target.value,
                    }))
                  }
                  style={inputStyle}
                  required
                >
                  <option value="">Select a saved template</option>
                  {templates.map((template) => (
                    <option key={template.id} value={template.id}>
                      {template.name} ({humanizeLabel(template.workflow_kind)})
                    </option>
                  ))}
                </select>
              </label>

              <label style={fieldStyle}>
                <span style={labelStyle}>Name</span>
                <input
                  value={form.name}
                  onChange={(event) =>
                    setForm((current) => ({
                      ...current,
                      name: event.target.value,
                    }))
                  }
                  style={inputStyle}
                  placeholder="Weekly US Magic Formula"
                  required
                />
              </label>

              <label style={{ ...fieldStyle, gridColumn: "1 / -1" }}>
                <span style={labelStyle}>Description</span>
                <input
                  value={form.description}
                  onChange={(event) =>
                    setForm((current) => ({
                      ...current,
                      description: event.target.value,
                    }))
                  }
                  style={inputStyle}
                  placeholder="Why this recurring run matters"
                />
              </label>

              <label style={fieldStyle}>
                <span style={labelStyle}>Timezone</span>
                <input
                  value={form.timezone}
                  onChange={(event) =>
                    setForm((current) => ({
                      ...current,
                      timezone: event.target.value,
                    }))
                  }
                  style={inputStyle}
                />
              </label>

              <label style={fieldStyle}>
                <span style={labelStyle}>Minute</span>
                <input
                  value={form.cronMinute}
                  onChange={(event) =>
                    setForm((current) => ({
                      ...current,
                      cronMinute: event.target.value,
                    }))
                  }
                  style={inputStyle}
                />
              </label>

              <label style={fieldStyle}>
                <span style={labelStyle}>Hour (24h)</span>
                <input
                  value={form.cronHour}
                  onChange={(event) =>
                    setForm((current) => ({
                      ...current,
                      cronHour: event.target.value,
                    }))
                  }
                  style={inputStyle}
                />
              </label>

              <label style={fieldStyle}>
                <span style={labelStyle}>Days of week</span>
                <input
                  value={form.cronDayOfWeek}
                  onChange={(event) =>
                    setForm((current) => ({
                      ...current,
                      cronDayOfWeek: event.target.value,
                    }))
                  }
                  style={inputStyle}
                />
              </label>

              <label style={fieldStyle}>
                <span style={labelStyle}>Day of month</span>
                <input
                  value={form.cronDayOfMonth}
                  onChange={(event) =>
                    setForm((current) => ({
                      ...current,
                      cronDayOfMonth: event.target.value,
                    }))
                  }
                  style={inputStyle}
                />
              </label>

              <label style={fieldStyle}>
                <span style={labelStyle}>Month</span>
                <input
                  value={form.cronMonthOfYear}
                  onChange={(event) =>
                    setForm((current) => ({
                      ...current,
                      cronMonthOfYear: event.target.value,
                    }))
                  }
                  style={inputStyle}
                />
              </label>

              <label style={{ ...fieldStyle, gridColumn: "1 / -1" }}>
                <span style={labelStyle}>Alert channel</span>
                <select
                  value={form.notifyChannel}
                  onChange={(event) =>
                    setForm((current) => ({
                      ...current,
                      notifyChannel: event.target
                        .value as RunSchedule["notify_channel"],
                    }))
                  }
                  style={inputStyle}
                >
                  <option value="email">Email</option>
                  <option value="slack_webhook">Slack webhook</option>
                  <option value="webhook">Generic webhook</option>
                </select>
              </label>

              <label style={{ ...fieldStyle, gridColumn: "1 / -1" }}>
                <span style={labelStyle}>
                  {form.notifyChannel === "email"
                    ? "Alert email"
                    : "Alert webhook URL"}
                </span>
                {form.notifyChannel === "email" ? (
                  <input
                    value={form.notifyEmail}
                    onChange={(event) =>
                      setForm((current) => ({
                        ...current,
                        notifyEmail: event.target.value,
                      }))
                    }
                    style={inputStyle}
                    placeholder={
                      user.email || "falls back to the account email"
                    }
                  />
                ) : (
                  <input
                    value={form.notifyWebhookUrl}
                    onChange={(event) =>
                      setForm((current) => ({
                        ...current,
                        notifyWebhookUrl: event.target.value,
                      }))
                    }
                    style={inputStyle}
                    placeholder="https://hooks.example.test/..."
                  />
                )}
              </label>

              <label style={fieldStyle}>
                <span style={labelStyle}>Review status</span>
                <select
                  value={form.reviewStatus}
                  onChange={(event) =>
                    setForm((current) => ({
                      ...current,
                      reviewStatus: event.target
                        .value as RunSchedule["review_status"],
                    }))
                  }
                  style={inputStyle}
                >
                  <option value="draft">Draft</option>
                  <option value="in_review">In review</option>
                  <option value="approved">Approved</option>
                  <option value="changes_requested">Changes requested</option>
                </select>
              </label>

              <label style={fieldStyle}>
                <span style={labelStyle}>Review notes</span>
                <input
                  value={form.reviewNotes}
                  onChange={(event) =>
                    setForm((current) => ({
                      ...current,
                      reviewNotes: event.target.value,
                    }))
                  }
                  style={inputStyle}
                  placeholder="Optional approval notes"
                />
              </label>

              <label style={toggleStyle}>
                <input
                  type="checkbox"
                  checked={form.notifyOnSuccess}
                  onChange={(event) =>
                    setForm((current) => ({
                      ...current,
                      notifyOnSuccess: event.target.checked,
                    }))
                  }
                />
                <span>Alert me when runs succeed</span>
              </label>

              <label style={toggleStyle}>
                <input
                  type="checkbox"
                  checked={form.notifyOnFailure}
                  onChange={(event) =>
                    setForm((current) => ({
                      ...current,
                      notifyOnFailure: event.target.checked,
                    }))
                  }
                />
                <span>Alert me when runs fail</span>
              </label>

              <label style={toggleStyle}>
                <input
                  type="checkbox"
                  checked={form.isEnabled}
                  onChange={(event) =>
                    setForm((current) => ({
                      ...current,
                      isEnabled: event.target.checked,
                    }))
                  }
                />
                <span>Enable schedule now</span>
              </label>

              <div style={{ ...actionRowStyle, gridColumn: "1 / -1" }}>
                <button
                  type="submit"
                  style={buttonStyle}
                  disabled={isSubmitting || form.templateId === ""}
                >
                  {isSubmitting ? "Saving..." : "Save schedule"}
                </button>
                <span style={noteStyle}>
                  Example workweek schedule: `0 13 * * 1-5` runs at 13:00 UTC
                  Monday through Friday.
                </span>
              </div>
            </form>
          )}
        </section>

        <section style={{ ...sectionCardStyle, marginTop: "1.5rem" }}>
          <div style={cardHeaderStyle}>
            <div>
              <p style={sectionLabelStyle}>Active schedules</p>
              <h2 style={cardTitleStyle}>
                {schedules.length.toLocaleString()} configured schedules
              </h2>
            </div>
            <span style={pillStyle}>
              {schedules.filter((schedule) => schedule.is_enabled).length}{" "}
              enabled
            </span>
          </div>

          <div style={listStyle}>
            {schedules.length === 0 ? (
              <p style={bodyStyle}>
                No recurring schedules yet. Save one above to keep a proven
                workflow running automatically and make reviews more repeatable.
              </p>
            ) : (
              schedules.map((schedule) => (
                <article key={schedule.id} style={cardStyle}>
                  <div style={cardHeaderStyle}>
                    <div>
                      <p style={sectionLabelStyle}>
                        {humanizeLabel(
                          schedule.strategy_template.workflow_kind,
                        )}
                      </p>
                      <h3 style={cardTitleStyle}>{schedule.name}</h3>
                      <p style={metaStyle}>
                        Template: {schedule.strategy_template.name} - Time zone{" "}
                        {schedule.timezone}
                      </p>
                    </div>
                    <div
                      style={{
                        display: "grid",
                        gap: "0.45rem",
                        justifyItems: "end",
                      }}
                    >
                      <span
                        style={stateBadgeStyle(
                          schedule.is_enabled ? "enabled" : "paused",
                        )}
                      >
                        {schedule.is_enabled ? "enabled" : "paused"}
                      </span>
                      <span style={pillStyle}>
                        {humanizeLabel(schedule.review_status)}
                      </span>
                    </div>
                  </div>

                  <p style={bodyStyle}>
                    {schedule.description ||
                      "Add a short note so teammates know why this schedule exists."}
                  </p>
                  <div style={statsGridStyle}>
                    <div style={statCardStyle}>
                      <strong>Cadence</strong>
                      <div style={metaStyle}>
                        {schedule.cron_minute} {schedule.cron_hour}{" "}
                        {schedule.cron_day_of_month}{" "}
                        {schedule.cron_month_of_year}{" "}
                        {schedule.cron_day_of_week}
                      </div>
                    </div>
                    <div style={statCardStyle}>
                      <strong>Alerts</strong>
                      <div style={metaStyle}>
                        {schedule.notify_channel === "email"
                          ? schedule.notify_email ||
                            user.email ||
                            "fallback account email"
                          : schedule.notify_webhook_url || "workspace defaults"}
                      </div>
                    </div>
                    <div style={statCardStyle}>
                      <strong>Last run</strong>
                      <div style={metaStyle}>
                        {schedule.last_launch_status
                          ? humanizeLabel(schedule.last_launch_status)
                          : "Never run yet"}
                        {schedule.last_run_id
                          ? ` - run #${schedule.last_run_id}`
                          : ""}
                      </div>
                    </div>
                  </div>

                  {schedule.last_error_message ? (
                    <p style={errorStyle}>{schedule.last_error_message}</p>
                  ) : null}

                  <div style={actionRowStyle}>
                    <button
                      type="button"
                      style={buttonStyle}
                      onClick={() => void handleTrigger(schedule)}
                      disabled={activeScheduleId === schedule.id}
                    >
                      {activeScheduleId === schedule.id
                        ? "Launching..."
                        : "Launch now"}
                    </button>
                    <button
                      type="button"
                      style={ghostButtonStyle}
                      onClick={() => void handleToggle(schedule)}
                    >
                      {schedule.is_enabled ? "Pause" : "Enable"}
                    </button>
                    <button
                      type="button"
                      style={ghostButtonStyle}
                      onClick={() => void handleQuickEdit(schedule)}
                    >
                      Edit cadence
                    </button>
                    <button
                      type="button"
                      style={dangerButtonStyle}
                      onClick={() => void handleDelete(schedule)}
                    >
                      Delete
                    </button>
                  </div>
                </article>
              ))
            )}
          </div>
        </section>
      </section>
    </main>
  );
}

function formatApiError(error: unknown, fallback: string): string {
  if (error instanceof ApiError) {
    return error.errors.length > 0
      ? `${error.message} ${error.errors.join(" ")}`
      : error.message;
  }
  return error instanceof Error ? error.message : fallback;
}

function humanizeLabel(value: string): string {
  return value.replaceAll("_", " ");
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
  lineHeight: 1.6,
  color: "#334862",
};

const sectionCardStyle: CSSProperties = {
  padding: "1.5rem",
  borderRadius: "24px",
  background: "#f8fbff",
  border: "1px solid rgba(73, 98, 128, 0.18)",
  marginTop: "1.5rem",
};

const cardStyle: CSSProperties = {
  padding: "1.25rem",
  borderRadius: "22px",
  background: "white",
  border: "1px solid rgba(73, 98, 128, 0.18)",
};

const cardHeaderStyle: CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  alignItems: "flex-start",
  gap: "1rem",
  flexWrap: "wrap",
};

const sectionLabelStyle: CSSProperties = {
  margin: 0,
  textTransform: "uppercase",
  letterSpacing: "0.12em",
  color: "#496280",
  fontSize: "0.78rem",
};

const cardTitleStyle: CSSProperties = {
  margin: "0.35rem 0 0",
  fontSize: "1.35rem",
};

const listStyle: CSSProperties = {
  display: "grid",
  gap: "1rem",
  marginTop: "1.25rem",
};

const statsGridStyle: CSSProperties = {
  display: "grid",
  gap: "0.75rem",
  gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
  margin: "1rem 0",
};

const statCardStyle: CSSProperties = {
  padding: "0.85rem",
  borderRadius: "16px",
  background: "#f7fafc",
  border: "1px solid rgba(73, 98, 128, 0.12)",
};

const formGridStyle: CSSProperties = {
  display: "grid",
  gap: "1rem",
  gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
  marginTop: "1.25rem",
};

const fieldStyle: CSSProperties = {
  display: "grid",
  gap: "0.45rem",
};

const labelStyle: CSSProperties = {
  fontWeight: 600,
  color: "#35506b",
};

const inputStyle: CSSProperties = {
  borderRadius: "14px",
  border: "1px solid rgba(73, 98, 128, 0.22)",
  padding: "0.85rem 1rem",
  fontSize: "0.96rem",
  background: "white",
};

const toggleStyle: CSSProperties = {
  display: "flex",
  gap: "0.5rem",
  alignItems: "center",
  color: "#35506b",
};

const buttonStyle: CSSProperties = {
  border: "none",
  borderRadius: "999px",
  padding: "0.8rem 1.2rem",
  background: "#1f4f78",
  color: "white",
  cursor: "pointer",
};

const ghostButtonStyle: CSSProperties = {
  ...buttonStyle,
  background: "#eef4fa",
  color: "#1f4f78",
};

const dangerButtonStyle: CSSProperties = {
  ...buttonStyle,
  background: "#b23a2b",
};

const primaryLinkStyle: CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  justifyContent: "center",
  borderRadius: "999px",
  padding: "0.8rem 1.2rem",
  background: "#1f4f78",
  color: "white",
  textDecoration: "none",
};

const ghostLinkStyle: CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  justifyContent: "center",
  borderRadius: "999px",
  padding: "0.8rem 1.2rem",
  background: "#eef4fa",
  color: "#1f4f78",
  textDecoration: "none",
};

const pillStyle: CSSProperties = {
  borderRadius: "999px",
  padding: "0.45rem 0.8rem",
  background: "#eef4fa",
  color: "#35506b",
  fontSize: "0.85rem",
};

const metaStyle: CSSProperties = {
  color: "#4d6783",
  lineHeight: 1.5,
};

const noteStyle: CSSProperties = {
  color: "#4d6783",
  fontSize: "0.92rem",
};

const errorStyle: CSSProperties = {
  color: "#a33225",
  fontWeight: 600,
};

const infoStyle: CSSProperties = {
  marginTop: "1rem",
  padding: "0.9rem 1rem",
  borderRadius: "16px",
  background: "#e6f1ff",
  color: "#0f4c81",
};

const emptyStateStyle: CSSProperties = {
  display: "grid",
  gap: "1rem",
  marginTop: "1.25rem",
  padding: "1rem",
  borderRadius: "18px",
  background: "#ffffff",
  border: "1px solid rgba(73, 98, 128, 0.16)",
};

function stateBadgeStyle(label: string): CSSProperties {
  return {
    borderRadius: "999px",
    padding: "0.4rem 0.75rem",
    background: label === "enabled" ? "#d9f3e7" : "#fce8d9",
    color: label === "enabled" ? "#136b46" : "#8e4a19",
    textTransform: "uppercase",
    fontSize: "0.75rem",
    letterSpacing: "0.08em",
  };
}
