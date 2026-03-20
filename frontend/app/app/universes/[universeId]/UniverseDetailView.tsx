"use client";

import { startTransition, useEffect, useState, type CSSProperties, type FormEvent } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { ApiError, deleteUniverse, getCurrentUser, getUniverse, updateUniverse, type UniverseDetail } from "@/lib/api";

type LoadState = "loading" | "ready" | "error";

type UniverseDetailViewProps = {
  universeId: number;
};


export function UniverseDetailView({ universeId }: UniverseDetailViewProps) {
  const router = useRouter();
  const [universe, setUniverse] = useState<UniverseDetail | null>(null);
  const [state, setState] = useState<LoadState>("loading");
  const [error, setError] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [isStarred, setIsStarred] = useState(false);
  const [tagsText, setTagsText] = useState("");
  const [notes, setNotes] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  useEffect(() => {
    let active = true;

    async function load() {
      try {
        await getCurrentUser();
        const payload = await getUniverse(universeId);
        if (!active) {
          return;
        }
        setUniverse(payload);
        setName(payload.name);
        setDescription(payload.description);
        setIsStarred(payload.is_starred);
        setTagsText(payload.tags.join(", "));
        setNotes(payload.notes);
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
        setError(loadError instanceof Error ? loadError.message : "Unable to load universe detail.");
        setState("error");
      }
    }

    void load();

    return () => {
      active = false;
    };
  }, [router, universeId]);

  async function handleSave(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsSaving(true);
    setError(null);
    try {
      const payload = await updateUniverse(universeId, {
        name,
        description,
        isStarred,
        tags: tagsText
          .split(",")
          .map((item) => item.trim())
          .filter(Boolean),
        notes,
      });
      setUniverse(payload);
      setName(payload.name);
      setDescription(payload.description);
      setIsStarred(payload.is_starred);
      setTagsText(payload.tags.join(", "));
      setNotes(payload.notes);
    } catch (saveError) {
      setError(formatApiError(saveError, "Unable to update the universe."));
    } finally {
      setIsSaving(false);
    }
  }

  async function handleDelete() {
    if (!window.confirm("Delete this universe? This removes the saved ticker list for the workspace.")) {
      return;
    }
    setIsDeleting(true);
    setError(null);
    try {
      await deleteUniverse(universeId);
      startTransition(() => {
        router.replace("/app/universes");
      });
    } catch (deleteError) {
      setError(formatApiError(deleteError, "Unable to delete the universe."));
      setIsDeleting(false);
    }
  }

  if (state === "loading") {
    return (
      <main style={pageStyle}>
        <section style={panelStyle}>
          <p style={eyebrowStyle}>Universe</p>
          <h1 style={titleStyle}>Loading saved universe</h1>
        </section>
      </main>
    );
  }

  if (state === "error" || universe == null) {
    return (
      <main style={pageStyle}>
        <section style={panelStyle}>
          <p style={eyebrowStyle}>Universe</p>
          <h1 style={titleStyle}>Universe unavailable</h1>
          <p style={bodyStyle}>{error ?? "Unable to load this universe."}</p>
          <div style={actionRowStyle}>
            <Link href="/app/universes" style={primaryLinkStyle}>
              Back to universes
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
            <p style={eyebrowStyle}>Universe</p>
            <h1 style={titleStyle}>{universe.name}</h1>
          </div>
          <div style={actionRowStyle}>
            <Link href="/app/screens" style={ghostLinkStyle}>
              Run screen
            </Link>
            <Link href="/app/backtests" style={ghostLinkStyle}>
              Start backtest
            </Link>
            <Link href="/app/universes" style={ghostLinkStyle}>
              All universes
            </Link>
            <Link href="/app" style={ghostLinkStyle}>
              Dashboard
            </Link>
          </div>
        </div>

        <p style={bodyStyle}>
          This saved universe is the starting list for future screens and backtests. Review the
          notes, tags, and source details here before you reuse it across the workspace.
        </p>

        {error ? <p style={errorStyle}>{error}</p> : null}

        <div style={summaryGridStyle}>
          <div style={summaryCardStyle}>
            <p style={sectionLabelStyle}>Universe size</p>
            <h2 style={summaryTitleStyle}>{universe.entry_count.toLocaleString()}</h2>
            <p style={metaStyle}>Saved {new Date(universe.created_at).toLocaleString()}</p>
          </div>
          <div style={summaryCardStyle}>
            <p style={sectionLabelStyle}>Profile / upload</p>
            <h2 style={summaryTitleStyle}>{universe.profile_key ?? universe.source_upload?.original_filename ?? "Manual"}</h2>
            <p style={metaStyle}>
              {universe.source_upload
                ? `${universe.source_upload.size_bytes.toLocaleString()} bytes · ${universe.source_upload.storage_backend}`
                : "Created inside the workspace"}
            </p>
          </div>
          <div style={summaryCardStyle}>
            <p style={sectionLabelStyle}>Research status</p>
            <h2 style={summaryTitleStyle}>{universe.is_starred ? "Starred" : "Standard"}</h2>
            <p style={metaStyle}>
              {universe.tags.length > 0 ? universe.tags.join(", ") : "Add tags to group related research."}
            </p>
          </div>
        </div>

        <div style={layoutStyle}>
          <div style={sectionCardStyle}>
            <p style={sectionLabelStyle}>Metadata</p>
            <form onSubmit={handleSave} style={formStyle}>
              <label style={fieldStyle}>
                <span style={labelStyle}>Universe name</span>
                <input
                  type="text"
                  value={name}
                  onChange={(event) => setName(event.target.value)}
                  style={inputStyle}
                  required
                />
              </label>
              <label style={fieldStyle}>
                <span style={labelStyle}>Description</span>
                <textarea
                  value={description}
                  onChange={(event) => setDescription(event.target.value)}
                  rows={4}
                  style={textareaStyle}
                />
              </label>
              <label style={fieldStyle}>
                <span style={labelStyle}>Tags</span>
                <input
                  type="text"
                  value={tagsText}
                  onChange={(event) => setTagsText(event.target.value)}
                  placeholder="starter, review, favorite"
                  style={inputStyle}
                />
              </label>
              <label style={fieldStyle}>
                <span style={labelStyle}>Research notes</span>
                <textarea
                  value={notes}
                  onChange={(event) => setNotes(event.target.value)}
                  rows={6}
                  style={textareaStyle}
                />
              </label>
              <label style={checkboxFieldStyle}>
                <input type="checkbox" checked={isStarred} onChange={(event) => setIsStarred(event.target.checked)} />
                <span>Star this universe so it stands out in the dashboard and lists</span>
              </label>
              <div style={actionRowStyle}>
                <button type="submit" style={buttonStyle} disabled={isSaving}>
                  {isSaving ? "Saving..." : "Save changes"}
                </button>
                <button type="button" style={dangerButtonStyle} onClick={handleDelete} disabled={isDeleting}>
                  {isDeleting ? "Deleting..." : "Delete universe"}
                </button>
              </div>
            </form>
          </div>

          <div style={sectionCardStyle}>
            <div style={previewHeaderStyle}>
              <div>
                <p style={sectionLabelStyle}>Ticker preview</p>
                <h2 style={previewTitleStyle}>{universe.entries.length} resolved names</h2>
              </div>
              <span style={pillStyle}>{universe.source_type.replaceAll("_", " ")}</span>
            </div>
            <div style={tableWrapperStyle}>
              <table style={tableStyle}>
                <thead>
                  <tr>
                    <th style={headerCellStyle}>#</th>
                    <th style={headerCellStyle}>Ticker</th>
                    <th style={headerCellStyle}>Raw</th>
                  </tr>
                </thead>
                <tbody>
                  {universe.entries.map((entry) => (
                    <tr key={entry.id}>
                      <td style={cellStyle}>{entry.position}</td>
                      <td style={tickerCellStyle}>{entry.normalized_ticker}</td>
                      <td style={cellStyle}>{entry.raw_ticker}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
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
};

const summaryGridStyle: CSSProperties = {
  display: "grid",
  gap: "1rem",
  gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))",
  marginTop: "1.5rem",
};

const summaryCardStyle: CSSProperties = {
  padding: "1.1rem",
  borderRadius: "20px",
  background: "#f8fbff",
  border: "1px solid rgba(73, 98, 128, 0.18)",
};

const summaryTitleStyle: CSSProperties = {
  margin: "0.45rem 0",
  fontSize: "1.7rem",
};

const layoutStyle: CSSProperties = {
  display: "grid",
  gap: "1rem",
  marginTop: "1.5rem",
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

const textareaStyle: CSSProperties = {
  ...inputStyle,
  resize: "vertical",
  minHeight: "6rem",
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

const dangerButtonStyle: CSSProperties = {
  ...buttonStyle,
  background: "#8f2622",
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

const errorStyle: CSSProperties = {
  marginTop: "1rem",
  padding: "0.9rem 1rem",
  borderRadius: "16px",
  background: "#fff3f0",
  color: "#8f2622",
};

const previewHeaderStyle: CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  gap: "1rem",
  alignItems: "flex-start",
  flexWrap: "wrap",
};

const previewTitleStyle: CSSProperties = {
  margin: "0.45rem 0 0",
  fontSize: "1.7rem",
};

const pillStyle: CSSProperties = {
  padding: "0.35rem 0.6rem",
  borderRadius: "999px",
  background: "#dde6f0",
  color: "#162132",
  fontSize: "0.82rem",
  textTransform: "capitalize",
};

const tableWrapperStyle: CSSProperties = {
  overflowX: "auto",
  marginTop: "1rem",
  borderRadius: "16px",
  border: "1px solid rgba(73, 98, 128, 0.18)",
  background: "#fff",
};

const tableStyle: CSSProperties = {
  width: "100%",
  borderCollapse: "collapse",
};

const headerCellStyle: CSSProperties = {
  textAlign: "left",
  padding: "0.9rem",
  fontSize: "0.82rem",
  letterSpacing: "0.12em",
  textTransform: "uppercase",
  color: "#5c728d",
  borderBottom: "1px solid rgba(73, 98, 128, 0.18)",
};

const cellStyle: CSSProperties = {
  padding: "0.9rem",
  borderBottom: "1px solid rgba(73, 98, 128, 0.12)",
  color: "#334862",
};

const tickerCellStyle: CSSProperties = {
  ...cellStyle,
  fontWeight: 700,
  color: "#162132",
};
