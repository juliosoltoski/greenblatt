"use client";

import { startTransition, useEffect, useState, type CSSProperties, type FormEvent } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import {
  ApiError,
  createAlertRule,
  deleteAlertRule,
  getCurrentUser,
  getUserNotificationPreference,
  getWorkspaceNotificationPreference,
  listAlertRules,
  listNotificationEvents,
  listStrategyTemplates,
  updateAlertRule,
  updateUserNotificationPreference,
  updateWorkspaceNotificationPreference,
  type AlertRule,
  type CurrentUser,
  type NotificationEvent,
  type StrategyTemplate,
  type UserNotificationPreference,
  type WorkspaceNotificationPreference,
} from "@/lib/api";

type LoadState = "loading" | "ready" | "error";

type AlertFormState = {
  name: string;
  description: string;
  eventType: AlertRule["event_type"];
  workflowKind: AlertRule["workflow_kind"];
  channel: AlertRule["channel"];
  strategyTemplateId: string;
  destinationEmail: string;
  destinationWebhookUrl: string;
  ticker: string;
  topNThreshold: string;
  isEnabled: boolean;
};

const initialFormState: AlertFormState = {
  name: "",
  description: "",
  eventType: "run_failed",
  workflowKind: "",
  channel: "email",
  strategyTemplateId: "",
  destinationEmail: "",
  destinationWebhookUrl: "",
  ticker: "",
  topNThreshold: "10",
  isEnabled: true,
};

export function AlertHub() {
  const router = useRouter();
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [templates, setTemplates] = useState<StrategyTemplate[]>([]);
  const [rules, setRules] = useState<AlertRule[]>([]);
  const [events, setEvents] = useState<NotificationEvent[]>([]);
  const [workspacePreference, setWorkspacePreference] = useState<WorkspaceNotificationPreference | null>(null);
  const [userPreference, setUserPreference] = useState<UserNotificationPreference | null>(null);
  const [notificationStatus, setNotificationStatus] = useState<NotificationEvent["status"] | "">("");
  const [state, setState] = useState<LoadState>("loading");
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState<AlertFormState>(initialFormState);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [activeRuleId, setActiveRuleId] = useState<number | null>(null);
  const [preferenceAction, setPreferenceAction] = useState<"workspace" | "user" | null>(null);

  useEffect(() => {
    let active = true;

    async function load() {
      try {
        const currentUser = await getCurrentUser();
        const workspaceId = currentUser.active_workspace?.id;
        const workspacePreferencePromise = workspaceId
          ? getWorkspaceNotificationPreference(workspaceId)
          : Promise.resolve(null);
        const userPreferencePromise = workspaceId ? getUserNotificationPreference(workspaceId) : Promise.resolve(null);
        const [templatePayload, rulePayload, eventPayload] = await Promise.all([
          listStrategyTemplates({ workspaceId, pageSize: 100 }),
          listAlertRules({ workspaceId, pageSize: 100 }),
          listNotificationEvents({ workspaceId, pageSize: 20, status: notificationStatus }),
        ]);
        const [workspacePreferencePayload, userPreferencePayload] = await Promise.all([
          workspacePreferencePromise,
          userPreferencePromise,
        ]);
        if (!active) {
          return;
        }
        setUser(currentUser);
        setTemplates(templatePayload.results);
        setRules(rulePayload.results);
        setEvents(eventPayload.results);
        setWorkspacePreference(workspacePreferencePayload);
        setUserPreference(userPreferencePayload);
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
        setError(loadError instanceof Error ? loadError.message : "Unable to load alerts.");
        setState("error");
      }
    }

    void load();

    return () => {
      active = false;
    };
  }, [notificationStatus, router]);

  async function refresh(currentUser: CurrentUser) {
    const workspaceId = currentUser.active_workspace?.id;
    const [templatePayload, rulePayload, eventPayload, workspacePreferencePayload, userPreferencePayload] = await Promise.all([
      listStrategyTemplates({ workspaceId, pageSize: 100 }),
      listAlertRules({ workspaceId, pageSize: 100 }),
      listNotificationEvents({ workspaceId, pageSize: 20, status: notificationStatus }),
      workspaceId ? getWorkspaceNotificationPreference(workspaceId) : Promise.resolve(null),
      workspaceId ? getUserNotificationPreference(workspaceId) : Promise.resolve(null),
    ]);
    setTemplates(templatePayload.results);
    setRules(rulePayload.results);
    setEvents(eventPayload.results);
    setWorkspacePreference(workspacePreferencePayload);
    setUserPreference(userPreferencePayload);
  }

  async function handleCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (user == null) {
      return;
    }
    setError(null);
    setIsSubmitting(true);
    try {
      await createAlertRule({
        workspaceId: user.active_workspace?.id,
        name: form.name.trim(),
        description: form.description.trim(),
        eventType: form.eventType,
        workflowKind: form.eventType === "ticker_entered_top_n" ? "screen" : form.workflowKind,
        channel: form.channel,
        strategyTemplateId: form.strategyTemplateId ? Number(form.strategyTemplateId) : null,
        destinationEmail: form.channel === "email" ? form.destinationEmail.trim() : "",
        destinationWebhookUrl: form.channel === "email" ? "" : form.destinationWebhookUrl.trim(),
        ticker: form.ticker.trim(),
        topNThreshold: form.topNThreshold ? Number(form.topNThreshold) : null,
        isEnabled: form.isEnabled,
      });
      setForm(initialFormState);
      await refresh(user);
    } catch (createError) {
      setError(formatApiError(createError, "Unable to create this alert."));
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleToggle(rule: AlertRule) {
    if (user == null) {
      return;
    }
    setActiveRuleId(rule.id);
    setError(null);
    try {
      await updateAlertRule(rule.id, { isEnabled: !rule.is_enabled });
      await refresh(user);
    } catch (updateError) {
      setError(formatApiError(updateError, "Unable to update this alert."));
    } finally {
      setActiveRuleId(null);
    }
  }

  async function handleQuickEdit(rule: AlertRule) {
    if (user == null) {
      return;
    }
    const nextName = window.prompt("Alert name", rule.name);
    if (nextName == null || nextName.trim() === "") {
      return;
    }
    const nextChannel = normalizeAlertChannel(
      window.prompt("Notification channel (email, slack_webhook, webhook)", rule.channel) ?? rule.channel,
      rule.channel,
    );
    const nextDestination = nextChannel === "email"
      ? window.prompt("Destination email", rule.destination_email) ?? rule.destination_email
      : window.prompt("Destination webhook URL", rule.destination_webhook_url ?? "") ?? rule.destination_webhook_url ?? "";
    const nextTicker = rule.event_type === "ticker_entered_top_n"
      ? window.prompt("Ticker", rule.ticker ?? "") ?? rule.ticker ?? ""
      : rule.ticker ?? "";
    const nextThreshold = rule.event_type === "ticker_entered_top_n"
      ? window.prompt("Top N threshold", String(rule.top_n_threshold ?? 10)) ?? String(rule.top_n_threshold ?? 10)
      : "";
    setActiveRuleId(rule.id);
    setError(null);
    try {
      await updateAlertRule(rule.id, {
        name: nextName.trim(),
        channel: nextChannel,
        destinationEmail: nextChannel === "email" ? nextDestination.trim() : "",
        destinationWebhookUrl: nextChannel === "email" ? "" : nextDestination.trim(),
        ticker: nextTicker.trim(),
        topNThreshold: nextThreshold ? Number(nextThreshold) : null,
      });
      await refresh(user);
    } catch (updateError) {
      setError(formatApiError(updateError, "Unable to update this alert."));
    } finally {
      setActiveRuleId(null);
    }
  }

  async function handleSaveWorkspacePreference(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (user == null || workspacePreference == null) {
      return;
    }
    setPreferenceAction("workspace");
    setError(null);
    try {
      const updated = await updateWorkspaceNotificationPreference({
        workspaceId: user.active_workspace?.id,
        defaultEmail: workspacePreference.default_email,
        emailEnabled: workspacePreference.email_enabled,
        slackEnabled: workspacePreference.slack_enabled,
        webhookEnabled: workspacePreference.webhook_enabled,
        slackWebhookUrl: workspacePreference.slack_webhook_url ?? "",
        genericWebhookUrl: workspacePreference.generic_webhook_url ?? "",
        digestEnabled: workspacePreference.digest_enabled,
        digestHourUtc: workspacePreference.digest_hour_utc,
        notifyOnRunSuccess: workspacePreference.notify_on_run_success,
        notifyOnRunFailure: workspacePreference.notify_on_run_failure,
      });
      setWorkspacePreference(updated);
    } catch (saveError) {
      setError(formatApiError(saveError, "Unable to update workspace notification preferences."));
    } finally {
      setPreferenceAction(null);
    }
  }

  async function handleSaveUserPreference(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (user == null || userPreference == null) {
      return;
    }
    setPreferenceAction("user");
    setError(null);
    try {
      const updated = await updateUserNotificationPreference({
        workspaceId: user.active_workspace?.id,
        deliveryEmail: userPreference.delivery_email,
        emailEnabled: userPreference.email_enabled,
        slackEnabled: userPreference.slack_enabled,
        webhookEnabled: userPreference.webhook_enabled,
        digestEnabled: userPreference.digest_enabled,
      });
      setUserPreference(updated);
    } catch (saveError) {
      setError(formatApiError(saveError, "Unable to update your notification preferences."));
    } finally {
      setPreferenceAction(null);
    }
  }

  async function handleDelete(rule: AlertRule) {
    if (user == null || !window.confirm(`Delete alert "${rule.name}"?`)) {
      return;
    }
    setActiveRuleId(rule.id);
    setError(null);
    try {
      await deleteAlertRule(rule.id);
      await refresh(user);
    } catch (deleteError) {
      setError(formatApiError(deleteError, "Unable to delete this alert."));
    } finally {
      setActiveRuleId(null);
    }
  }

  if (state === "loading") {
    return (
      <main style={pageStyle}>
        <section style={panelStyle}>
          <p style={eyebrowStyle}>Alerts</p>
          <h1 style={titleStyle}>Loading notifications and alert rules</h1>
        </section>
      </main>
    );
  }

  if (state === "error" || user == null) {
    return (
      <main style={pageStyle}>
        <section style={panelStyle}>
          <p style={eyebrowStyle}>Alerts</p>
          <h1 style={titleStyle}>Alerts unavailable</h1>
          <p style={bodyStyle}>{error ?? "Unable to load alert management."}</p>
          <Link href="/app" style={primaryLinkStyle}>
            Back to app
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
            <p style={eyebrowStyle}>Notifications</p>
            <h1 style={titleStyle}>Alert routing, digests, and delivery history</h1>
          </div>
          <div style={actionRowStyle}>
            <Link href="/app" style={ghostLinkStyle}>
              App shell
            </Link>
            <Link href="/app/schedules" style={ghostLinkStyle}>
              Schedules
            </Link>
            <Link href="/app/history" style={ghostLinkStyle}>
              History
            </Link>
          </div>
        </div>

        <p style={bodyStyle}>
          Route alerts by email, Slack webhook, or generic webhook. Workspace-level settings define
          default destinations and digests, while each user can opt into the channels they actually
          monitor.
        </p>

        {error ? <p style={errorStyle}>{error}</p> : null}

        <section style={sectionCardStyle}>
          <div style={cardHeaderStyle}>
            <div>
              <p style={sectionLabelStyle}>Create alert</p>
              <h2 style={cardTitleStyle}>Turn completed runs into proactive notifications</h2>
            </div>
            <span style={pillStyle}>{rules.filter((rule) => rule.is_enabled).length} enabled rules</span>
          </div>

          <form style={formGridStyle} onSubmit={handleCreate}>
            <label style={fieldStyle}>
              <span style={labelStyle}>Name</span>
              <input
                value={form.name}
                onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))}
                style={inputStyle}
                placeholder="Notify me on failures"
                required
              />
            </label>

            <label style={fieldStyle}>
              <span style={labelStyle}>Event type</span>
              <select
                value={form.eventType}
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    eventType: event.target.value as AlertRule["event_type"],
                    workflowKind: event.target.value === "ticker_entered_top_n" ? "screen" : current.workflowKind,
                  }))
                }
                style={inputStyle}
              >
                <option value="run_failed">Run failed</option>
                <option value="screen_completed">Screen completed</option>
                <option value="backtest_completed">Backtest completed</option>
                <option value="ticker_entered_top_n">Ticker entered top N</option>
              </select>
            </label>

            <label style={fieldStyle}>
              <span style={labelStyle}>Workflow scope</span>
              <select
                value={form.eventType === "ticker_entered_top_n" ? "screen" : form.workflowKind}
                onChange={(event) =>
                  setForm((current) => ({ ...current, workflowKind: event.target.value as AlertRule["workflow_kind"] }))
                }
                style={inputStyle}
                disabled={form.eventType === "ticker_entered_top_n"}
              >
                <option value="">Any workflow</option>
                <option value="screen">Screen only</option>
                <option value="backtest">Backtest only</option>
              </select>
            </label>

            <label style={fieldStyle}>
              <span style={labelStyle}>Notification channel</span>
              <select
                value={form.channel}
                onChange={(event) => setForm((current) => ({ ...current, channel: event.target.value as AlertRule["channel"] }))}
                style={inputStyle}
              >
                <option value="email">Email</option>
                <option value="slack_webhook">Slack webhook</option>
                <option value="webhook">Generic webhook</option>
              </select>
            </label>

            <label style={fieldStyle}>
              <span style={labelStyle}>Template scope</span>
              <select
                value={form.strategyTemplateId}
                onChange={(event) => setForm((current) => ({ ...current, strategyTemplateId: event.target.value }))}
                style={inputStyle}
              >
                <option value="">Any template</option>
                {templates.map((template) => (
                  <option key={template.id} value={template.id}>
                    {template.name} ({template.workflow_kind})
                  </option>
                ))}
              </select>
            </label>

            <label style={{ ...fieldStyle, gridColumn: "1 / -1" }}>
              <span style={labelStyle}>Description</span>
              <input
                value={form.description}
                onChange={(event) => setForm((current) => ({ ...current, description: event.target.value }))}
                style={inputStyle}
                placeholder="Optional context for operators"
              />
            </label>

            {form.channel === "email" ? (
              <label style={{ ...fieldStyle, gridColumn: "1 / -1" }}>
                <span style={labelStyle}>Destination email</span>
                <input
                  value={form.destinationEmail}
                  onChange={(event) => setForm((current) => ({ ...current, destinationEmail: event.target.value }))}
                  style={inputStyle}
                  placeholder={user.email || "falls back to the account email"}
                />
              </label>
            ) : (
              <label style={{ ...fieldStyle, gridColumn: "1 / -1" }}>
                <span style={labelStyle}>{form.channel === "slack_webhook" ? "Slack webhook URL" : "Generic webhook URL"}</span>
                <input
                  value={form.destinationWebhookUrl}
                  onChange={(event) => setForm((current) => ({ ...current, destinationWebhookUrl: event.target.value }))}
                  style={inputStyle}
                  placeholder="https://hooks.example.test/..."
                />
              </label>
            )}

            {form.eventType === "ticker_entered_top_n" ? (
              <>
                <label style={fieldStyle}>
                  <span style={labelStyle}>Ticker</span>
                  <input
                    value={form.ticker}
                    onChange={(event) => setForm((current) => ({ ...current, ticker: event.target.value.toUpperCase() }))}
                    style={inputStyle}
                    placeholder="AAPL"
                    required
                  />
                </label>
                <label style={fieldStyle}>
                  <span style={labelStyle}>Top N threshold</span>
                  <input
                    type="number"
                    min={1}
                    max={500}
                    value={form.topNThreshold}
                    onChange={(event) => setForm((current) => ({ ...current, topNThreshold: event.target.value }))}
                    style={inputStyle}
                    required
                  />
                </label>
              </>
            ) : null}

            <label style={toggleStyle}>
              <input
                type="checkbox"
                checked={form.isEnabled}
                onChange={(event) => setForm((current) => ({ ...current, isEnabled: event.target.checked }))}
              />
              <span>Enable rule immediately</span>
            </label>

            <div style={{ ...actionRowStyle, gridColumn: "1 / -1" }}>
              <button type="submit" style={buttonStyle} disabled={isSubmitting}>
                {isSubmitting ? "Creating..." : "Create alert"}
              </button>
              <span style={noteStyle}>Top-N alerts only evaluate successful screen runs, and digests run once per day at the configured UTC hour.</span>
            </div>
          </form>
        </section>

        <div style={layoutStyle}>
          <section style={sectionCardStyle}>
            <div style={cardHeaderStyle}>
              <div>
                <p style={sectionLabelStyle}>Notification preferences</p>
                <h2 style={cardTitleStyle}>Workspace defaults and personal opt-in</h2>
              </div>
              <span style={pillStyle}>{workspacePreference?.digest_enabled ? "Digest enabled" : "Digest paused"}</span>
            </div>

            <div style={preferenceGridStyle}>
              <form style={listStyle} onSubmit={handleSaveWorkspacePreference}>
                <div>
                  <p style={sectionLabelStyle}>Workspace defaults</p>
                  <p style={noteStyle}>
                    These settings define shared fallbacks for Slack, generic webhooks, and the
                    daily digest.
                  </p>
                </div>

                <label style={fieldStyle}>
                  <span style={labelStyle}>Default email</span>
                  <input
                    value={workspacePreference?.default_email ?? ""}
                    onChange={(event) =>
                      setWorkspacePreference((current) => (current ? { ...current, default_email: event.target.value } : current))
                    }
                    style={inputStyle}
                    placeholder={user.email || "ops@example.com"}
                  />
                </label>

                <label style={fieldStyle}>
                  <span style={labelStyle}>Slack webhook URL</span>
                  <input
                    value={workspacePreference?.slack_webhook_url ?? ""}
                    onChange={(event) =>
                      setWorkspacePreference((current) => (current ? { ...current, slack_webhook_url: event.target.value } : current))
                    }
                    style={inputStyle}
                    placeholder="https://hooks.slack.com/services/..."
                  />
                </label>

                <label style={fieldStyle}>
                  <span style={labelStyle}>Generic webhook URL</span>
                  <input
                    value={workspacePreference?.generic_webhook_url ?? ""}
                    onChange={(event) =>
                      setWorkspacePreference((current) => (current ? { ...current, generic_webhook_url: event.target.value } : current))
                    }
                    style={inputStyle}
                    placeholder="https://hooks.example.test/..."
                  />
                </label>

                <label style={fieldStyle}>
                  <span style={labelStyle}>Digest hour (UTC)</span>
                  <input
                    type="number"
                    min={0}
                    max={23}
                    value={workspacePreference?.digest_hour_utc ?? 9}
                    onChange={(event) =>
                      setWorkspacePreference((current) =>
                        current ? { ...current, digest_hour_utc: Number(event.target.value) } : current,
                      )
                    }
                    style={inputStyle}
                  />
                </label>

                <div style={checkboxGridStyle}>
                  <label style={toggleStyle}>
                    <input
                      type="checkbox"
                      checked={workspacePreference?.email_enabled ?? true}
                      onChange={(event) =>
                        setWorkspacePreference((current) =>
                          current ? { ...current, email_enabled: event.target.checked } : current,
                        )
                      }
                    />
                    <span>Email enabled</span>
                  </label>
                  <label style={toggleStyle}>
                    <input
                      type="checkbox"
                      checked={workspacePreference?.slack_enabled ?? true}
                      onChange={(event) =>
                        setWorkspacePreference((current) =>
                          current ? { ...current, slack_enabled: event.target.checked } : current,
                        )
                      }
                    />
                    <span>Slack enabled</span>
                  </label>
                  <label style={toggleStyle}>
                    <input
                      type="checkbox"
                      checked={workspacePreference?.webhook_enabled ?? true}
                      onChange={(event) =>
                        setWorkspacePreference((current) =>
                          current ? { ...current, webhook_enabled: event.target.checked } : current,
                        )
                      }
                    />
                    <span>Webhook enabled</span>
                  </label>
                  <label style={toggleStyle}>
                    <input
                      type="checkbox"
                      checked={workspacePreference?.digest_enabled ?? false}
                      onChange={(event) =>
                        setWorkspacePreference((current) =>
                          current ? { ...current, digest_enabled: event.target.checked } : current,
                        )
                      }
                    />
                    <span>Daily digest enabled</span>
                  </label>
                  <label style={toggleStyle}>
                    <input
                      type="checkbox"
                      checked={workspacePreference?.notify_on_run_success ?? true}
                      onChange={(event) =>
                        setWorkspacePreference((current) =>
                          current ? { ...current, notify_on_run_success: event.target.checked } : current,
                        )
                      }
                    />
                    <span>Notify on run success</span>
                  </label>
                  <label style={toggleStyle}>
                    <input
                      type="checkbox"
                      checked={workspacePreference?.notify_on_run_failure ?? true}
                      onChange={(event) =>
                        setWorkspacePreference((current) =>
                          current ? { ...current, notify_on_run_failure: event.target.checked } : current,
                        )
                      }
                    />
                    <span>Notify on run failure</span>
                  </label>
                </div>

                <div style={actionRowStyle}>
                  <button type="submit" style={buttonStyle} disabled={preferenceAction === "workspace" || workspacePreference == null}>
                    {preferenceAction === "workspace" ? "Saving..." : "Save workspace defaults"}
                  </button>
                  <span style={noteStyle}>
                    Last digest: {workspacePreference?.last_digest_sent_at ? new Date(workspacePreference.last_digest_sent_at).toLocaleString() : "never"}
                  </span>
                </div>
              </form>

              <form style={listStyle} onSubmit={handleSaveUserPreference}>
                <div>
                  <p style={sectionLabelStyle}>My preferences</p>
                  <p style={noteStyle}>
                    Personal preferences are opt-in switches. Slack and webhooks use the shared
                    workspace destinations unless a specific alert overrides them.
                  </p>
                </div>

                <label style={fieldStyle}>
                  <span style={labelStyle}>Delivery email</span>
                  <input
                    value={userPreference?.delivery_email ?? ""}
                    onChange={(event) =>
                      setUserPreference((current) => (current ? { ...current, delivery_email: event.target.value } : current))
                    }
                    style={inputStyle}
                    placeholder={user.email || "me@example.com"}
                  />
                </label>

                <div style={checkboxGridStyle}>
                  <label style={toggleStyle}>
                    <input
                      type="checkbox"
                      checked={userPreference?.email_enabled ?? true}
                      onChange={(event) =>
                        setUserPreference((current) => (current ? { ...current, email_enabled: event.target.checked } : current))
                      }
                    />
                    <span>Email alerts</span>
                  </label>
                  <label style={toggleStyle}>
                    <input
                      type="checkbox"
                      checked={userPreference?.slack_enabled ?? true}
                      onChange={(event) =>
                        setUserPreference((current) => (current ? { ...current, slack_enabled: event.target.checked } : current))
                      }
                    />
                    <span>Slack alerts</span>
                  </label>
                  <label style={toggleStyle}>
                    <input
                      type="checkbox"
                      checked={userPreference?.webhook_enabled ?? true}
                      onChange={(event) =>
                        setUserPreference((current) => (current ? { ...current, webhook_enabled: event.target.checked } : current))
                      }
                    />
                    <span>Webhook alerts</span>
                  </label>
                  <label style={toggleStyle}>
                    <input
                      type="checkbox"
                      checked={userPreference?.digest_enabled ?? false}
                      onChange={(event) =>
                        setUserPreference((current) => (current ? { ...current, digest_enabled: event.target.checked } : current))
                      }
                    />
                    <span>Receive digest email</span>
                  </label>
                </div>

                <div style={actionRowStyle}>
                  <button type="submit" style={buttonStyle} disabled={preferenceAction === "user" || userPreference == null}>
                    {preferenceAction === "user" ? "Saving..." : "Save my preferences"}
                  </button>
                </div>
              </form>
            </div>
          </section>

          <section style={sectionCardStyle}>
            <div style={cardHeaderStyle}>
              <div>
                <p style={sectionLabelStyle}>Alert rules</p>
                <h2 style={cardTitleStyle}>{rules.length.toLocaleString()} configured rules</h2>
              </div>
              <span style={pillStyle}>{rules.filter((rule) => rule.last_triggered_at).length} triggered</span>
            </div>
            <div style={listStyle}>
              {rules.length === 0 ? (
                <p style={bodyStyle}>No alert rules have been configured yet.</p>
              ) : (
                rules.map((rule) => (
                  <article key={rule.id} style={cardStyle}>
                    <div style={cardHeaderStyle}>
                      <div>
                        <p style={sectionLabelStyle}>{rule.event_type.replaceAll("_", " ")}</p>
                        <h3 style={cardTitleStyle}>{rule.name}</h3>
                        <p style={metaStyle}>
                          {rule.workflow_kind || "any workflow"} - {formatRuleDestination(rule, user)}
                        </p>
                      </div>
                      <span style={stateBadgeStyle(rule.is_enabled ? "enabled" : "paused")}>
                        {rule.is_enabled ? "enabled" : "paused"}
                      </span>
                    </div>
                    <p style={bodyStyle}>{rule.description || "No description provided."}</p>
                    <p style={metaStyle}>Channel: {rule.channel.replaceAll("_", " ")}</p>
                    {rule.ticker ? (
                      <p style={metaStyle}>
                        Target: {rule.ticker} in top {rule.top_n_threshold}
                      </p>
                    ) : null}
                    <p style={metaStyle}>
                      Template scope: {rule.strategy_template_id ? `template #${rule.strategy_template_id}` : "any template"}
                    </p>
                    <div style={actionRowStyle}>
                      <button type="button" style={ghostButtonStyle} onClick={() => void handleToggle(rule)}>
                        {rule.is_enabled ? "Pause" : "Enable"}
                      </button>
                      <button type="button" style={ghostButtonStyle} onClick={() => void handleQuickEdit(rule)}>
                        Quick edit
                      </button>
                      <button
                        type="button"
                        style={dangerButtonStyle}
                        onClick={() => void handleDelete(rule)}
                        disabled={activeRuleId === rule.id}
                      >
                        Delete
                      </button>
                    </div>
                  </article>
                ))
              )}
            </div>
          </section>

          <section style={sectionCardStyle}>
            <div style={cardHeaderStyle}>
              <div>
                <p style={sectionLabelStyle}>Recent notifications</p>
                <h2 style={cardTitleStyle}>{events.length.toLocaleString()} recent events</h2>
              </div>
              <label style={fieldStyle}>
                <span style={labelStyle}>Delivery status</span>
                <select
                  value={notificationStatus}
                  onChange={(event) => setNotificationStatus(event.target.value as NotificationEvent["status"] | "")}
                  style={inputStyle}
                >
                  <option value="">All</option>
                  <option value="sent">Sent</option>
                  <option value="failed">Failed</option>
                  <option value="skipped">Skipped</option>
                  <option value="pending">Pending</option>
                </select>
              </label>
            </div>

            <div style={listStyle}>
              {events.length === 0 ? (
                <p style={bodyStyle}>No notification events match the current filter.</p>
              ) : (
                events.map((notification) => (
                  <article key={notification.id} style={cardStyle}>
                    <div style={cardHeaderStyle}>
                      <div>
                        <p style={sectionLabelStyle}>{notification.event_type.replaceAll("_", " ")}</p>
                        <h3 style={cardTitleStyle}>{notification.subject}</h3>
                        <p style={metaStyle}>
                          {formatNotificationRecipient(notification)} - {new Date(notification.created_at).toLocaleString()}
                        </p>
                      </div>
                      <span style={stateBadgeStyle(notification.status)}>{notification.status}</span>
                    </div>
                    <p style={bodyStyle}>{notification.body}</p>
                    <p style={metaStyle}>Channel: {notification.channel.replaceAll("_", " ")}</p>
                    {notification.delivery_error ? <p style={errorStyle}>{notification.delivery_error}</p> : null}
                    <div style={actionRowStyle}>
                      {notification.screen_run_id ? (
                        <Link href={`/app/screens/${notification.screen_run_id}`} style={ghostLinkStyle}>
                          Open screen
                        </Link>
                      ) : null}
                      {notification.backtest_run_id ? (
                        <Link href={`/app/backtests/${notification.backtest_run_id}`} style={ghostLinkStyle}>
                          Open backtest
                        </Link>
                      ) : null}
                    </div>
                  </article>
                ))
              )}
            </div>
          </section>
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

function normalizeAlertChannel(rawValue: string, fallback: AlertRule["channel"]): AlertRule["channel"] {
  const normalized = rawValue.trim().toLowerCase();
  if (normalized === "email" || normalized === "slack_webhook" || normalized === "webhook") {
    return normalized;
  }
  return fallback;
}

function formatRuleDestination(rule: AlertRule, user: CurrentUser): string {
  if (rule.channel === "email") {
    return rule.destination_email || user.email || "fallback account email";
  }
  return rule.destination_webhook_url || "workspace default destination";
}

function formatNotificationRecipient(notification: NotificationEvent): string {
  if (notification.channel === "email" || notification.channel === "digest") {
    return notification.recipient_email ?? "no recipient";
  }
  return notification.recipient_webhook_url ?? "no destination";
}

const pageStyle: CSSProperties = {
  minHeight: "100vh",
  padding: "2rem",
};

const panelStyle: CSSProperties = {
  width: "min(1280px, 100%)",
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

const layoutStyle: CSSProperties = {
  display: "grid",
  gap: "1rem",
  gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))",
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

const formGridStyle: CSSProperties = {
  display: "grid",
  gap: "1rem",
  gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
  marginTop: "1.25rem",
};

const preferenceGridStyle: CSSProperties = {
  display: "grid",
  gap: "1.25rem",
  gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
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

const checkboxGridStyle: CSSProperties = {
  display: "grid",
  gap: "0.75rem",
  gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
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

function stateBadgeStyle(label: string): CSSProperties {
  const normalized = label.toLowerCase();
  const positive = normalized === "enabled" || normalized === "sent";
  const muted = normalized === "paused" || normalized === "skipped";
  return {
    borderRadius: "999px",
    padding: "0.4rem 0.75rem",
    background: positive ? "#d9f3e7" : muted ? "#f1f3f5" : "#fce8d9",
    color: positive ? "#136b46" : muted ? "#556372" : "#8e4a19",
    textTransform: "uppercase",
    fontSize: "0.75rem",
    letterSpacing: "0.08em",
  };
}
