"use client";

import { startTransition, useEffect, useEffectEvent, useState, type CSSProperties, type FormEvent } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import {
  ApiError,
  cancelJob,
  getCurrentUser,
  getJob,
  launchSmokeJob,
  listJobEvents,
  listJobs,
  retryJob,
  type CurrentUser,
  type JobEvent,
  type JobRun,
} from "@/lib/api";
import { JobTimeline } from "@/app/app/_components/JobTimeline";
import { useJobStream } from "@/lib/jobStream";

type LoadState = "loading" | "ready" | "error";


export function JobHub() {
  const router = useRouter();
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [jobs, setJobs] = useState<JobRun[]>([]);
  const [selectedJob, setSelectedJob] = useState<JobRun | null>(null);
  const [events, setEvents] = useState<JobEvent[]>([]);
  const [state, setState] = useState<LoadState>("loading");
  const [error, setError] = useState<string | null>(null);
  const [stepCount, setStepCount] = useState(4);
  const [stepDelayMs, setStepDelayMs] = useState(750);
  const [failureMode, setFailureMode] = useState<"success" | "fail" | "retry_once">("success");
  const [isLaunching, setIsLaunching] = useState(false);
  const [jobAction, setJobAction] = useState<"cancel" | "retry" | null>(null);

  useEffect(() => {
    let active = true;

    async function load() {
      try {
        const currentUser = await getCurrentUser();
        const workspaceId = currentUser.active_workspace?.id;
        const jobPayload = await listJobs(workspaceId, 20);
        const eventPayload = jobPayload.results[0] ? await listJobEvents(jobPayload.results[0].id, 80) : null;
        if (!active) {
          return;
        }
        setUser(currentUser);
        setJobs(jobPayload.results);
        setSelectedJob(jobPayload.results[0] ?? null);
        setEvents(eventPayload?.results ?? []);
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
        setError(loadError instanceof Error ? loadError.message : "Unable to load jobs.");
        setState("error");
      }
    }

    void load();

    return () => {
      active = false;
    };
  }, [router]);

  const handleStreamJob = useEffectEvent((job: JobRun) => {
    setSelectedJob((current) => (current?.id === job.id ? job : current));
    setJobs((current) => {
      const found = current.some((item) => item.id === job.id);
      if (!found) {
        return [job, ...current];
      }
      return current.map((item) => (item.id === job.id ? job : item));
    });
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
    jobId: selectedJob?.id ?? null,
    enabled: state === "ready" && selectedJob != null && !selectedJob.is_terminal,
    onJob: handleStreamJob,
    onEvent: handleStreamEvent,
  });

  async function refreshJobs(workspaceId?: number, focusJobId: number | null = null) {
    const listPayload = await listJobs(workspaceId, 20);
    setJobs(listPayload.results);

    const nextSelectedId = focusJobId ?? selectedJob?.id ?? listPayload.results[0]?.id ?? null;
    if (nextSelectedId == null) {
      setSelectedJob(null);
      return;
    }
    const detail = await getJob(nextSelectedId);
    setSelectedJob(detail);
    const eventPayload = await listJobEvents(nextSelectedId, 80);
    setEvents(eventPayload.results);
  }

  async function handleLaunch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (user?.active_workspace == null) {
      setError("No active workspace is available.");
      return;
    }

    setIsLaunching(true);
    setError(null);
    try {
      const launched = await launchSmokeJob({
        workspaceId: user.active_workspace.id,
        stepCount,
        stepDelayMs,
        failureMode,
      });
      setSelectedJob(launched);
      await refreshJobs(user.active_workspace.id, launched.id);
    } catch (launchError) {
      setError(formatApiError(launchError, "Unable to launch smoke job."));
    } finally {
      setIsLaunching(false);
    }
  }

  async function handleSelectJob(jobId: number) {
    try {
      setError(null);
      const [detail, eventPayload] = await Promise.all([getJob(jobId), listJobEvents(jobId, 80)]);
      setSelectedJob(detail);
      setEvents(eventPayload.results);
    } catch (loadError) {
      setError(formatApiError(loadError, "Unable to load the selected job."));
    }
  }

  async function handleCancelSelectedJob() {
    if (selectedJob == null) {
      return;
    }
    setJobAction("cancel");
    setError(null);
    try {
      const updated = await cancelJob(selectedJob.id);
      setSelectedJob(updated);
      await refreshJobs(user?.active_workspace?.id, updated.id);
    } catch (cancelError) {
      setError(formatApiError(cancelError, "Unable to request job cancellation."));
    } finally {
      setJobAction(null);
    }
  }

  async function handleRetrySelectedJob() {
    if (selectedJob == null) {
      return;
    }
    setJobAction("retry");
    setError(null);
    try {
      const retried = await retryJob(selectedJob.id);
      setSelectedJob(retried);
      await refreshJobs(user?.active_workspace?.id, retried.id);
    } catch (retryError) {
      setError(formatApiError(retryError, "Unable to retry this job."));
    } finally {
      setJobAction(null);
    }
  }

  if (state === "loading") {
    return (
      <main style={pageStyle}>
        <section style={panelStyle}>
          <p style={eyebrowStyle}>Async Jobs</p>
          <h1 style={titleStyle}>Loading job framework</h1>
          <p style={bodyStyle}>Fetching your recent jobs and workspace context.</p>
        </section>
      </main>
    );
  }

  if (state === "error" || user == null) {
    return (
      <main style={pageStyle}>
        <section style={panelStyle}>
          <p style={eyebrowStyle}>Async Jobs</p>
          <h1 style={titleStyle}>Jobs unavailable</h1>
          <p style={bodyStyle}>{error ?? "Unable to load the job dashboard."}</p>
          <div style={actionRowStyle}>
            <Link href="/app" style={primaryLinkStyle}>
              Back to app
            </Link>
          </div>
        </section>
      </main>
    );
  }

  return (
    <main style={pageStyle}>
      <section style={panelStyle}>
        <div style={headerRowStyle}>
          <div>
            <p style={eyebrowStyle}>M4 Async Job Framework</p>
            <h1 style={titleStyle}>Launch and monitor background jobs</h1>
          </div>
          <div style={actionRowStyle}>
            <Link href="/app" style={ghostLinkStyle}>
              App shell
            </Link>
            <Link href="/app/universes" style={ghostLinkStyle}>
              Universes
            </Link>
            <a href="http://localhost:8000/admin/" style={ghostLinkStyle}>
              Django admin
            </a>
          </div>
        </div>

        <p style={bodyStyle}>
          Active workspace: <strong>{user.active_workspace?.name ?? "Unavailable"}</strong>. This
          smoke task exercises the first job pipeline end to end: API request, persisted job
          record, Celery execution, timeline events, retries, and live status streaming.
        </p>

        {error ? <p style={errorStyle}>{error}</p> : null}

        <div style={layoutStyle}>
          <div style={stackStyle}>
            <section style={sectionCardStyle}>
              <p style={sectionLabelStyle}>Smoke task launcher</p>
              <form onSubmit={handleLaunch} style={formStyle}>
                <label style={fieldStyle}>
                  <span style={labelStyle}>Step count</span>
                  <input
                    type="number"
                    min={1}
                    max={8}
                    value={stepCount}
                    onChange={(event) => setStepCount(Number(event.target.value))}
                    style={inputStyle}
                    required
                  />
                </label>
                <label style={fieldStyle}>
                  <span style={labelStyle}>Step delay (ms)</span>
                  <input
                    type="number"
                    min={0}
                    max={5000}
                    value={stepDelayMs}
                    onChange={(event) => setStepDelayMs(Number(event.target.value))}
                    style={inputStyle}
                    required
                  />
                </label>
                <label style={fieldStyle}>
                  <span style={labelStyle}>Failure mode</span>
                  <select
                    value={failureMode}
                    onChange={(event) => setFailureMode(event.target.value as "success" | "fail" | "retry_once")}
                    style={inputStyle}
                  >
                    <option value="success">Success</option>
                    <option value="retry_once">Retry once</option>
                    <option value="fail">Fail</option>
                  </select>
                </label>
                <button type="submit" style={buttonStyle} disabled={isLaunching}>
                  {isLaunching ? "Launching..." : "Launch smoke job"}
                </button>
              </form>
            </section>

            <section style={sectionCardStyle}>
              <div style={statusHeaderStyle}>
                <div>
                  <p style={sectionLabelStyle}>Selected job</p>
                  <h2 style={statusTitleStyle}>{selectedJob ? `#${selectedJob.id}` : "No job selected"}</h2>
                </div>
                {selectedJob ? <span style={stateBadgeStyle(selectedJob.state)}>{selectedJob.state.replaceAll("_", " ")}</span> : null}
              </div>

              {selectedJob ? (
                <div style={{ display: "grid", gap: "1rem" }}>
                  <div>
                    <div style={progressTrackStyle}>
                      <div
                        style={{
                          ...progressFillStyle,
                          width: `${Math.max(6, selectedJob.progress_percent)}%`,
                        }}
                      />
                    </div>
                    <div style={progressMetaStyle}>
                      <span>{selectedJob.progress_percent}%</span>
                      <span>{selectedJob.current_step || "Pending"}</span>
                    </div>
                  </div>

                  <div style={summaryGridStyle}>
                    <div style={summaryCardStyle}>
                      <p style={sectionLabelStyle}>Type</p>
                      <strong>{selectedJob.job_type}</strong>
                    </div>
                    <div style={summaryCardStyle}>
                      <p style={sectionLabelStyle}>Retries</p>
                      <strong>{selectedJob.retry_count}</strong>
                    </div>
                    <div style={summaryCardStyle}>
                      <p style={sectionLabelStyle}>Task id</p>
                      <code style={codeStyle}>{selectedJob.celery_task_id ?? "pending"}</code>
                    </div>
                  </div>

                  {selectedJob.error_message ? (
                    <div style={failureBoxStyle}>
                      <strong>{selectedJob.error_code ?? "job_failed"}</strong>
                      <p style={{ margin: "0.5rem 0 0" }}>{selectedJob.error_message}</p>
                    </div>
                  ) : null}

                  <div style={actionRowStyle}>
                    {!selectedJob.is_terminal ? (
                      <button type="button" style={buttonStyle} onClick={() => void handleCancelSelectedJob()} disabled={jobAction === "cancel"}>
                        {jobAction === "cancel" ? "Cancelling..." : "Request cancel"}
                      </button>
                    ) : null}
                    {selectedJob.is_terminal && selectedJob.job_type === "smoke_test" ? (
                      <button type="button" style={buttonStyle} onClick={() => void handleRetrySelectedJob()} disabled={jobAction === "retry"}>
                        {jobAction === "retry" ? "Retrying..." : "Retry smoke job"}
                      </button>
                    ) : null}
                    {selectedJob.cancellation_requested ? <span style={pillStyle}>Cancellation requested</span> : null}
                  </div>

                  <div style={detailGridStyle}>
                    <div style={detailCardStyle}>
                      <p style={sectionLabelStyle}>Requested payload</p>
                      <pre style={preStyle}>
                        {JSON.stringify((selectedJob.metadata.request ?? {}) as Record<string, unknown>, null, 2)}
                      </pre>
                    </div>
                    <div style={detailCardStyle}>
                      <p style={sectionLabelStyle}>Result / latest error</p>
                      <pre style={preStyle}>
                        {JSON.stringify(
                          {
                            result: selectedJob.metadata.result ?? null,
                            last_error: selectedJob.metadata.last_error ?? null,
                          },
                          null,
                          2,
                        )}
                      </pre>
                    </div>
                  </div>

                  <div style={detailCardStyle}>
                    <p style={sectionLabelStyle}>Timeline</p>
                    <JobTimeline events={events} emptyMessage="Timeline events will appear once the worker starts." />
                  </div>
                </div>
              ) : (
                <p style={bodyStyle}>Launch a smoke task to create your first tracked job.</p>
              )}
            </section>
          </div>

          <aside style={sidebarStyle}>
            <section style={sectionCardStyle}>
              <div style={sidebarHeaderStyle}>
                <div>
                  <p style={sectionLabelStyle}>Recent jobs</p>
                  <h2 style={statusTitleStyle}>{jobs.length}</h2>
                </div>
                <span style={pillStyle}>Streaming selected job</span>
              </div>

              <div style={jobListStyle}>
                {jobs.length === 0 ? (
                  <p style={bodyStyle}>No jobs have been launched in this workspace yet.</p>
                ) : (
                  jobs.map((job) => (
                    <button
                      key={job.id}
                      type="button"
                      onClick={() => void handleSelectJob(job.id)}
                      style={{
                        ...jobRowStyle,
                        borderColor: selectedJob?.id === job.id ? "rgba(22, 33, 50, 0.34)" : "rgba(73, 98, 128, 0.18)",
                      }}
                    >
                      <div style={{ textAlign: "left" }}>
                        <strong>#{job.id}</strong>
                        <div style={metaStyle}>
                          {job.job_type} | {job.state.replaceAll("_", " ")}
                        </div>
                        <div style={subtleMetaStyle}>{job.current_step || "Pending"}</div>
                      </div>
                      <span style={pillStyle}>{job.progress_percent}%</span>
                    </button>
                  ))
                )}
              </div>
            </section>
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

function stateBadgeStyle(state: JobRun["state"]): CSSProperties {
  const palette = {
    queued: { background: "#dde6f0", color: "#162132" },
    running: { background: "#e6f1ff", color: "#0f4c81" },
    succeeded: { background: "#e2f3e7", color: "#17663a" },
    failed: { background: "#ffe5e0", color: "#8f2622" },
    cancelled: { background: "#f1ecdf", color: "#6b5a19" },
    partial_failed: { background: "#fff2d9", color: "#8b5c00" },
  } satisfies Record<JobRun["state"], { background: string; color: string }>;
  return {
    padding: "0.45rem 0.75rem",
    borderRadius: "999px",
    textTransform: "capitalize",
    background: palette[state].background,
    color: palette[state].color,
  };
}

const pageStyle: CSSProperties = {
  minHeight: "100vh",
  padding: "2rem",
};

const panelStyle: CSSProperties = {
  width: "min(1360px, 100%)",
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

const layoutStyle: CSSProperties = {
  display: "grid",
  gap: "1.25rem",
  gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))",
  marginTop: "2rem",
};

const stackStyle: CSSProperties = {
  display: "grid",
  gap: "1.25rem",
};

const sidebarStyle: CSSProperties = {
  display: "grid",
  alignContent: "start",
};

const sectionCardStyle: CSSProperties = {
  padding: "1.25rem",
  borderRadius: "22px",
  background: "#f8fbff",
  border: "1px solid rgba(73, 98, 128, 0.18)",
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

const actionRowStyle: CSSProperties = {
  display: "flex",
  gap: "0.75rem",
  flexWrap: "wrap",
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

const metaStyle: CSSProperties = {
  margin: "0.25rem 0",
  color: "#496280",
  lineHeight: 1.5,
};

const subtleMetaStyle: CSSProperties = {
  margin: "0.25rem 0 0",
  color: "#5c728d",
  lineHeight: 1.5,
  fontSize: "0.92rem",
};

const errorStyle: CSSProperties = {
  marginTop: "1rem",
  padding: "0.9rem 1rem",
  borderRadius: "16px",
  background: "#fff3f0",
  color: "#8f2622",
};

const statusHeaderStyle: CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  gap: "1rem",
  alignItems: "flex-start",
  flexWrap: "wrap",
};

const statusTitleStyle: CSSProperties = {
  margin: "0.45rem 0 0",
  fontSize: "1.8rem",
};

const progressTrackStyle: CSSProperties = {
  width: "100%",
  height: "14px",
  borderRadius: "999px",
  background: "#e7edf3",
  overflow: "hidden",
};

const progressFillStyle: CSSProperties = {
  height: "100%",
  borderRadius: "999px",
  background: "linear-gradient(90deg, #24548c 0%, #2f7ab9 100%)",
  transition: "width 200ms ease",
};

const progressMetaStyle: CSSProperties = {
  marginTop: "0.6rem",
  display: "flex",
  justifyContent: "space-between",
  gap: "1rem",
  color: "#496280",
};

const summaryGridStyle: CSSProperties = {
  display: "grid",
  gap: "0.85rem",
  gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
};

const summaryCardStyle: CSSProperties = {
  padding: "0.95rem",
  borderRadius: "18px",
  background: "#fff",
  border: "1px solid rgba(73, 98, 128, 0.18)",
};

const detailGridStyle: CSSProperties = {
  display: "grid",
  gap: "0.85rem",
  gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
};

const detailCardStyle: CSSProperties = {
  padding: "1rem",
  borderRadius: "18px",
  background: "#fff",
  border: "1px solid rgba(73, 98, 128, 0.18)",
};

const failureBoxStyle: CSSProperties = {
  padding: "1rem",
  borderRadius: "18px",
  background: "#fff3f0",
  color: "#8f2622",
};

const preStyle: CSSProperties = {
  margin: "0.85rem 0 0",
  padding: "0.95rem",
  borderRadius: "14px",
  background: "#162132",
  color: "#f5f7fb",
  overflowX: "auto",
  whiteSpace: "pre-wrap",
  wordBreak: "break-word",
  fontSize: "0.84rem",
  lineHeight: 1.5,
};

const codeStyle: CSSProperties = {
  fontSize: "0.82rem",
};

const sidebarHeaderStyle: CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  gap: "1rem",
  alignItems: "flex-start",
};

const pillStyle: CSSProperties = {
  padding: "0.35rem 0.6rem",
  borderRadius: "999px",
  background: "#dde6f0",
  color: "#162132",
  fontSize: "0.82rem",
};

const jobListStyle: CSSProperties = {
  display: "grid",
  gap: "0.75rem",
  marginTop: "1rem",
};

const jobRowStyle: CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  gap: "1rem",
  alignItems: "center",
  padding: "1rem",
  borderRadius: "18px",
  background: "#fff",
  border: "1px solid rgba(73, 98, 128, 0.18)",
  cursor: "pointer",
};
