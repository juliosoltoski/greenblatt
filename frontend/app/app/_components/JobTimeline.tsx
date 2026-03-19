"use client";

import type { CSSProperties } from "react";

import type { JobEvent } from "@/lib/api";

type JobTimelineProps = {
  events: JobEvent[];
  emptyMessage?: string;
};

export function JobTimeline({ events, emptyMessage = "No timeline events yet." }: JobTimelineProps) {
  if (events.length === 0) {
    return <p style={emptyStyle}>{emptyMessage}</p>;
  }

  return (
    <div style={listStyle}>
      {events.map((event) => (
        <article key={event.id} style={cardStyle}>
          <div style={headerStyle}>
            <span style={badgeStyle(event.level)}>{event.level}</span>
            <span style={metaStyle}>{formatTimestamp(event.created_at)}</span>
          </div>
          <strong style={titleStyle}>{event.message}</strong>
          <p style={bodyStyle}>
            {event.event_type.replaceAll("_", " ")}
            {event.progress_percent != null ? ` · ${event.progress_percent}%` : ""}
          </p>
          {renderEventDetail(event)}
        </article>
      ))}
    </div>
  );
}

function formatTimestamp(value: string): string {
  try {
    return new Date(value).toLocaleString();
  } catch {
    return value;
  }
}

function renderEventDetail(event: JobEvent) {
  if (event.event_type === "provider_failure") {
    const providerName = typeof event.metadata.provider_name === "string" ? event.metadata.provider_name : "unknown";
    const workflow = typeof event.metadata.workflow === "string" ? event.metadata.workflow : "run";
    return <p style={detailStyle}>Provider issue: {providerName} during {workflow} execution.</p>;
  }
  if (event.event_type === "cancel_requested") {
    return <p style={detailStyle}>The worker will stop at the next safe cancellation checkpoint.</p>;
  }
  if (event.event_type === "retry_scheduled") {
    const countdown = typeof event.metadata.countdown_seconds === "number" ? event.metadata.countdown_seconds : null;
    return <p style={detailStyle}>Retry scheduled{countdown != null ? ` after ${countdown}s` : ""}.</p>;
  }
  return null;
}

const listStyle: CSSProperties = {
  display: "grid",
  gap: "0.75rem",
};

const cardStyle: CSSProperties = {
  display: "grid",
  gap: "0.35rem",
  padding: "0.85rem 0.95rem",
  borderRadius: "18px",
  background: "#f8fbff",
  border: "1px solid rgba(73, 98, 128, 0.12)",
};

const headerStyle: CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  gap: "0.75rem",
  alignItems: "center",
  flexWrap: "wrap",
};

const metaStyle: CSSProperties = {
  color: "#637990",
  fontSize: "0.82rem",
};

const titleStyle: CSSProperties = {
  fontSize: "0.98rem",
};

const bodyStyle: CSSProperties = {
  margin: 0,
  color: "#496280",
  fontSize: "0.9rem",
};

const emptyStyle: CSSProperties = {
  margin: 0,
  color: "#637990",
};

const detailStyle: CSSProperties = {
  margin: 0,
  color: "#5c728d",
  fontSize: "0.84rem",
};

function badgeStyle(level: JobEvent["level"]): CSSProperties {
  const palette =
    level === "error"
      ? { background: "#fde8e8", color: "#a12f2f" }
      : level === "warning"
        ? { background: "#fff4de", color: "#8a5a14" }
        : { background: "#e4f1ff", color: "#1a5b8a" };
  return {
    display: "inline-flex",
    alignItems: "center",
    justifyContent: "center",
    padding: "0.25rem 0.6rem",
    borderRadius: "999px",
    textTransform: "capitalize",
    fontSize: "0.78rem",
    ...palette,
  };
}
