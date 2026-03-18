"use client";

import { startTransition, useEffect, useState, type CSSProperties, type FormEvent } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import {
  ApiError,
  createManualUniverse,
  createProfileUniverse,
  createUploadedUniverse,
  getCurrentUser,
  getUniverseProfiles,
  listUniverses,
  type CurrentUser,
  type UniverseProfile,
  type UniverseSummary,
} from "@/lib/api";
import { readViewPreference, writeViewPreference } from "@/lib/viewPreferences";

type LoadState = "loading" | "ready" | "error";
type UniverseCreationMode = "profile" | "manual" | "upload";

const creationModeOptions: Array<{
  key: UniverseCreationMode;
  label: string;
  description: string;
}> = [
  {
    key: "profile",
    label: "Built-in profile",
    description: "Fastest way to get started",
  },
  {
    key: "manual",
    label: "Manual list",
    description: "Paste a custom watchlist",
  },
  {
    key: "upload",
    label: "Upload file",
    description: "Import a newline-delimited ticker file",
  },
];

export function UniverseHub() {
  const router = useRouter();
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [profiles, setProfiles] = useState<UniverseProfile[]>([]);
  const [universes, setUniverses] = useState<UniverseSummary[]>([]);
  const [state, setState] = useState<LoadState>("loading");
  const [error, setError] = useState<string | null>(null);
  const [manualName, setManualName] = useState("");
  const [manualDescription, setManualDescription] = useState("");
  const [manualTickers, setManualTickers] = useState("MSFT\nAAPL\nBRK.B");
  const [profileName, setProfileName] = useState("");
  const [profileDescription, setProfileDescription] = useState("");
  const [selectedProfileKey, setSelectedProfileKey] = useState("");
  const [uploadName, setUploadName] = useState("");
  const [uploadDescription, setUploadDescription] = useState("");
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [isSubmitting, setIsSubmitting] = useState<"manual" | "profile" | "upload" | null>(null);
  const [creationMode, setCreationMode] = useState<UniverseCreationMode>("profile");
  const [starredOnly, setStarredOnly] = useState(false);

  useEffect(() => {
    const preference = readViewPreference<{ starredOnly: boolean }>("universe-hub", { starredOnly: false });
    setStarredOnly(preference.starredOnly);
  }, []);

  useEffect(() => {
    writeViewPreference("universe-hub", { starredOnly });
  }, [starredOnly]);

  useEffect(() => {
    let active = true;

    async function load() {
      try {
        const currentUser = await getCurrentUser();
        const workspaceId = currentUser.active_workspace?.id;
        const [profileResults, universeResults] = await Promise.all([
          getUniverseProfiles(),
          listUniverses(workspaceId, { starredOnly }),
        ]);
        if (!active) {
          return;
        }
        setUser(currentUser);
        setProfiles(profileResults);
        setUniverses(universeResults.results);
        setSelectedProfileKey((currentValue) => currentValue || profileResults[0]?.key || "");
        setProfileName((currentValue) => currentValue || selectedProfileLabel(profileResults[0]?.key || "", profileResults));
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
        setError(loadError instanceof Error ? loadError.message : "Unable to load universes.");
        setState("error");
      }
    }

    void load();

    return () => {
      active = false;
    };
  }, [router, starredOnly]);

  async function refreshUniverses(currentUser: CurrentUser) {
    const workspaceId = currentUser.active_workspace?.id;
    const payload = await listUniverses(workspaceId, { starredOnly });
    setUniverses(payload.results);
  }

  async function handleManualSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (user?.active_workspace == null) {
      setError("No active workspace is available.");
      return;
    }

    setIsSubmitting("manual");
    setError(null);
    try {
      const created = await createManualUniverse({
        workspaceId: user.active_workspace.id,
        name: manualName,
        description: manualDescription,
        manualTickers,
      });
      await refreshUniverses(user);
      startTransition(() => {
        router.push(`/app/universes/${created.id}`);
      });
    } catch (submitError) {
      setError(formatApiError(submitError, "Manual universe creation failed."));
    } finally {
      setIsSubmitting(null);
    }
  }

  async function handleProfileSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (user?.active_workspace == null) {
      setError("No active workspace is available.");
      return;
    }

    setIsSubmitting("profile");
    setError(null);
    try {
      const created = await createProfileUniverse({
        workspaceId: user.active_workspace.id,
        name: profileName || selectedProfileLabel(selectedProfileKey, profiles),
        description: profileDescription,
        profileKey: selectedProfileKey,
      });
      await refreshUniverses(user);
      startTransition(() => {
        router.push(`/app/universes/${created.id}`);
      });
    } catch (submitError) {
      setError(formatApiError(submitError, "Built-in universe creation failed."));
    } finally {
      setIsSubmitting(null);
    }
  }

  async function handleUploadSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (user?.active_workspace == null) {
      setError("No active workspace is available.");
      return;
    }
    if (uploadFile == null) {
      setError("Choose a newline-delimited ticker file before uploading.");
      return;
    }

    setIsSubmitting("upload");
    setError(null);
    try {
      const created = await createUploadedUniverse({
        workspaceId: user.active_workspace.id,
        name: uploadName,
        description: uploadDescription,
        uploadFile,
      });
      await refreshUniverses(user);
      startTransition(() => {
        router.push(`/app/universes/${created.id}`);
      });
    } catch (submitError) {
      setError(formatApiError(submitError, "Uploaded universe creation failed."));
    } finally {
      setIsSubmitting(null);
    }
  }

  if (state === "loading") {
    return (
      <main style={pageStyle}>
        <section style={panelStyle}>
          <p style={eyebrowStyle}>Universe Management</p>
          <h1 style={titleStyle}>Loading workspace universes</h1>
          <p style={bodyStyle}>Fetching built-in profiles, saved universes, and your active workspace.</p>
        </section>
      </main>
    );
  }

  if (state === "error" || user == null) {
    return (
      <main style={pageStyle}>
        <section style={panelStyle}>
          <p style={eyebrowStyle}>Universe Management</p>
          <h1 style={titleStyle}>Universe loading failed</h1>
          <p style={bodyStyle}>{error ?? "Unable to load the universe workspace."}</p>
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
            <p style={eyebrowStyle}>Research Inputs</p>
            <h1 style={titleStyle}>Create a universe without leaving the app</h1>
          </div>
        </div>

        <p style={bodyStyle}>
          Active workspace: <strong>{user.active_workspace?.name ?? "Unavailable"}</strong>. Save a
          built-in profile for the quickest start, or switch to manual and upload modes when you
          need a custom list. The saved universe becomes reusable across screens, backtests,
          templates, and schedules.
        </p>

        {error ? <p style={errorStyle}>{error}</p> : null}

        <div style={layoutStyle}>
          <section style={stackStyle}>
            <div style={sectionCardStyle}>
              <div style={modeHeaderStyle}>
                <div>
                  <p style={sectionLabelStyle}>Create a universe</p>
                  <h2 style={sectionTitleStyle}>Choose the starting point that fits the job</h2>
                  <p style={subtleMetaStyle}>
                    Most first-time users should start with a built-in profile, then only switch to
                    a custom source when they already know the target ticker set.
                  </p>
                </div>
                <div style={modeSwitchStyle}>
                  {creationModeOptions.map((option) => (
                    <button
                      key={option.key}
                      type="button"
                      style={creationMode === option.key ? activeModeButtonStyle : modeButtonStyle}
                      onClick={() => setCreationMode(option.key)}
                    >
                      <span>{option.label}</span>
                      <small style={modeDescriptionStyle}>{option.description}</small>
                    </button>
                  ))}
                </div>
              </div>

              {creationMode === "profile" ? (
                <div style={modeSectionStyle}>
                  <form onSubmit={handleProfileSubmit} style={formStyle}>
                    <label style={fieldStyle}>
                      <span style={labelStyle}>Saved universe name</span>
                      <input
                        type="text"
                        value={profileName}
                        onChange={(event) => setProfileName(event.target.value)}
                        placeholder="Technology profile"
                        style={inputStyle}
                        required
                      />
                    </label>
                    <label style={fieldStyle}>
                      <span style={labelStyle}>Description</span>
                      <input
                        type="text"
                        value={profileDescription}
                        onChange={(event) => setProfileDescription(event.target.value)}
                        placeholder="Saved from the built-in profile catalog"
                        style={inputStyle}
                      />
                    </label>
                    <label style={fieldStyle}>
                      <span style={labelStyle}>Profile</span>
                      <select
                        value={selectedProfileKey}
                        onChange={(event) => setSelectedProfileKey(event.target.value)}
                        style={inputStyle}
                      >
                        {profiles.map((profile) => (
                          <option key={profile.key} value={profile.key}>
                            {profile.key}
                          </option>
                        ))}
                      </select>
                    </label>
                    <button type="submit" style={buttonStyle} disabled={isSubmitting === "profile"}>
                      {isSubmitting === "profile" ? "Saving profile..." : "Save built-in universe"}
                    </button>
                  </form>

                  <div style={profileGridStyle}>
                    {profiles.map((profile) => (
                      <article
                        key={profile.key}
                        style={{
                          ...profileCardStyle,
                          borderColor:
                            selectedProfileKey === profile.key ? "rgba(22, 33, 50, 0.38)" : "rgba(73, 98, 128, 0.18)",
                        }}
                      >
                        <div style={profileHeaderStyle}>
                          <strong>{profile.key}</strong>
                          {profile.estimated_entry_count ? (
                            <span style={pillStyle}>{profile.estimated_entry_count.toLocaleString()} names</span>
                          ) : null}
                        </div>
                        <p style={metaStyle}>{profile.description}</p>
                        <p style={subtleMetaStyle}>Source: {profile.source}</p>
                        {profile.preview_tickers.length > 0 ? (
                          <div style={tickerWrapStyle}>
                            {profile.preview_tickers.map((ticker) => (
                              <span key={ticker} style={tickerChipStyle}>
                                {ticker}
                              </span>
                            ))}
                          </div>
                        ) : (
                          <p style={subtleMetaStyle}>{profile.resolution_note}</p>
                        )}
                      </article>
                    ))}
                  </div>
                </div>
              ) : null}

              {creationMode === "manual" ? (
                <div style={modeSectionStyle}>
                  <div style={helperCardStyle}>
                    <strong>Best for focused watchlists</strong>
                    <p style={helperTextStyle}>
                      Paste one ticker per line when you already know the exact names you want to
                      research.
                    </p>
                  </div>
                  <form onSubmit={handleManualSubmit} style={formStyle}>
                    <label style={fieldStyle}>
                      <span style={labelStyle}>Universe name</span>
                      <input
                        type="text"
                        value={manualName}
                        onChange={(event) => setManualName(event.target.value)}
                        placeholder="High conviction ideas"
                        style={inputStyle}
                        required
                      />
                    </label>
                    <label style={fieldStyle}>
                      <span style={labelStyle}>Description</span>
                      <input
                        type="text"
                        value={manualDescription}
                        onChange={(event) => setManualDescription(event.target.value)}
                        placeholder="Manually curated tickers"
                        style={inputStyle}
                      />
                    </label>
                    <label style={fieldStyle}>
                      <span style={labelStyle}>Tickers</span>
                      <textarea
                        value={manualTickers}
                        onChange={(event) => setManualTickers(event.target.value)}
                        rows={7}
                        style={textareaStyle}
                        required
                      />
                    </label>
                    <button type="submit" style={buttonStyle} disabled={isSubmitting === "manual"}>
                      {isSubmitting === "manual" ? "Creating universe..." : "Create manual universe"}
                    </button>
                  </form>
                </div>
              ) : null}

              {creationMode === "upload" ? (
                <div style={modeSectionStyle}>
                  <div style={helperCardStyle}>
                    <strong>Best for imports</strong>
                    <p style={helperTextStyle}>
                      Use a newline-delimited text file when the source list already exists outside
                      the app.
                    </p>
                  </div>
                  <form onSubmit={handleUploadSubmit} style={formStyle}>
                    <label style={fieldStyle}>
                      <span style={labelStyle}>Universe name</span>
                      <input
                        type="text"
                        value={uploadName}
                        onChange={(event) => setUploadName(event.target.value)}
                        placeholder="Imported watchlist"
                        style={inputStyle}
                        required
                      />
                    </label>
                    <label style={fieldStyle}>
                      <span style={labelStyle}>Description</span>
                      <input
                        type="text"
                        value={uploadDescription}
                        onChange={(event) => setUploadDescription(event.target.value)}
                        placeholder="Uploaded from a newline-delimited text file"
                        style={inputStyle}
                      />
                    </label>
                    <label style={fieldStyle}>
                      <span style={labelStyle}>Ticker file</span>
                      <input
                        type="file"
                        accept=".txt,.csv,.lst,text/plain"
                        onChange={(event) => setUploadFile(event.target.files?.[0] ?? null)}
                        style={fileInputStyle}
                        required
                      />
                    </label>
                    <button type="submit" style={buttonStyle} disabled={isSubmitting === "upload"}>
                      {isSubmitting === "upload" ? "Uploading..." : "Create uploaded universe"}
                    </button>
                  </form>
                </div>
              ) : null}
            </div>

            <div style={sectionCardStyle}>
              <p style={sectionLabelStyle}>When to use each option</p>
              <div style={profileGridStyle}>
                <article style={profileCardStyle}>
                  <strong>Built-in profiles</strong>
                  <p style={subtleMetaStyle}>
                    Best default for broad coverage and first-time users.
                  </p>
                </article>
                <article style={profileCardStyle}>
                  <strong>Manual lists</strong>
                  <p style={subtleMetaStyle}>
                    Best for a short list of conviction names or a hand-curated watchlist.
                  </p>
                </article>
                <article style={profileCardStyle}>
                  <strong>Uploads</strong>
                  <p style={subtleMetaStyle}>
                    Best when the source ticker list already exists outside the app.
                  </p>
                </article>
              </div>
            </div>
          </section>

          <aside style={sidebarStyle}>
            <div style={sectionCardStyle}>
              <div style={sidebarHeaderStyle}>
                <div>
                  <p style={sectionLabelStyle}>Saved universes</p>
                  <h2 style={sidebarTitleStyle}>{universes.length}</h2>
                </div>
                <label style={filterPillStyle}>
                  <input type="checkbox" checked={starredOnly} onChange={(event) => setStarredOnly(event.target.checked)} />
                  <span>Starred only</span>
                </label>
              </div>
              <div style={universeListStyle}>
                {universes.length === 0 ? (
                  <p style={subtleMetaStyle}>No universes saved yet for this workspace.</p>
                ) : (
                  universes.map((universe) => (
                    <Link key={universe.id} href={`/app/universes/${universe.id}`} style={universeRowStyle}>
                      <div>
                        <div style={universeTitleRowStyle}>
                          <strong>{universe.name}</strong>
                          {universe.is_starred ? <span style={miniStarStyle}>Starred</span> : null}
                        </div>
                        <div style={metaStyle}>
                          {universe.source_type.replaceAll("_", " ")} · {universe.entry_count} tickers
                        </div>
                        {universe.tags.length > 0 ? (
                          <div style={tickerWrapStyle}>
                            {universe.tags.map((tag) => (
                              <span key={tag} style={miniTagStyle}>
                                {tag}
                              </span>
                            ))}
                          </div>
                        ) : null}
                        {universe.preview_tickers.length > 0 ? (
                          <div style={tickerWrapStyle}>
                            {universe.preview_tickers.map((ticker) => (
                              <span key={ticker} style={miniTickerChipStyle}>
                                {ticker}
                              </span>
                            ))}
                          </div>
                        ) : null}
                      </div>
                      <span style={arrowStyle}>View</span>
                    </Link>
                  ))
                )}
              </div>
            </div>
          </aside>
        </div>
      </section>
    </main>
  );
}

function selectedProfileLabel(profileKey: string, profiles: UniverseProfile[]): string {
  return profiles.find((profile) => profile.key === profileKey)?.key ?? "Saved built-in universe";
}

function formatApiError(error: unknown, fallback: string): string {
  if (error instanceof ApiError) {
    return error.errors.length > 0 ? `${error.message} ${error.errors.join(" ")}` : error.message;
  }
  return error instanceof Error ? error.message : fallback;
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

const sidebarHeaderStyle: CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  alignItems: "flex-start",
  gap: "1rem",
};

const filterPillStyle: CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  gap: "0.45rem",
  padding: "0.45rem 0.7rem",
  borderRadius: "999px",
  background: "#dde6f0",
  color: "#162132",
  fontSize: "0.82rem",
};

const sidebarTitleStyle: CSSProperties = {
  margin: "0.4rem 0 0",
  fontSize: "2rem",
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

const sectionTitleStyle: CSSProperties = {
  margin: "0.55rem 0 0",
  fontSize: "1.55rem",
};

const modeHeaderStyle: CSSProperties = {
  display: "grid",
  gap: "1rem",
};

const modeSwitchStyle: CSSProperties = {
  display: "grid",
  gap: "0.75rem",
  gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
  marginTop: "0.35rem",
};

const modeButtonStyle: CSSProperties = {
  display: "grid",
  gap: "0.25rem",
  textAlign: "left",
  padding: "0.95rem 1rem",
  borderRadius: "16px",
  border: "1px solid rgba(73, 98, 128, 0.18)",
  background: "#fff",
  color: "#162132",
  cursor: "pointer",
};

const activeModeButtonStyle: CSSProperties = {
  ...modeButtonStyle,
  background: "#162132",
  color: "#f5f7fb",
  borderColor: "#162132",
};

const modeDescriptionStyle: CSSProperties = {
  color: "inherit",
  opacity: 0.8,
};

const modeSectionStyle: CSSProperties = {
  display: "grid",
  gap: "1rem",
  marginTop: "1.2rem",
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

const textareaStyle: CSSProperties = {
  ...inputStyle,
  resize: "vertical",
  minHeight: "8rem",
};

const fileInputStyle: CSSProperties = {
  ...inputStyle,
  padding: "0.6rem 0.7rem",
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

const metaStyle: CSSProperties = {
  margin: "0.25rem 0",
  color: "#496280",
  lineHeight: 1.5,
};

const subtleMetaStyle: CSSProperties = {
  margin: "0.35rem 0 0",
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

const profileGridStyle: CSSProperties = {
  display: "grid",
  gap: "0.85rem",
  gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
  marginTop: "1.25rem",
};

const profileCardStyle: CSSProperties = {
  padding: "1rem",
  borderRadius: "18px",
  background: "#fff",
  border: "1px solid rgba(73, 98, 128, 0.18)",
};

const profileHeaderStyle: CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  gap: "0.75rem",
  alignItems: "center",
};

const pillStyle: CSSProperties = {
  padding: "0.35rem 0.6rem",
  borderRadius: "999px",
  background: "#dde6f0",
  color: "#162132",
  fontSize: "0.82rem",
};

const tickerWrapStyle: CSSProperties = {
  display: "flex",
  flexWrap: "wrap",
  gap: "0.45rem",
  marginTop: "0.9rem",
};

const tickerChipStyle: CSSProperties = {
  padding: "0.35rem 0.55rem",
  borderRadius: "999px",
  background: "#edf3f8",
  fontSize: "0.8rem",
};

const miniTickerChipStyle: CSSProperties = {
  ...tickerChipStyle,
  background: "#f2f6fb",
};

const universeListStyle: CSSProperties = {
  display: "grid",
  gap: "0.85rem",
  marginTop: "1rem",
};

const universeRowStyle: CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  gap: "1rem",
  textDecoration: "none",
  padding: "1rem",
  borderRadius: "18px",
  background: "#fff",
  border: "1px solid rgba(73, 98, 128, 0.18)",
};

const universeTitleRowStyle: CSSProperties = {
  display: "flex",
  gap: "0.5rem",
  alignItems: "center",
  flexWrap: "wrap",
};

const miniStarStyle: CSSProperties = {
  padding: "0.2rem 0.45rem",
  borderRadius: "999px",
  background: "#fff4cc",
  color: "#8b5c00",
  fontSize: "0.76rem",
};

const miniTagStyle: CSSProperties = {
  padding: "0.22rem 0.45rem",
  borderRadius: "999px",
  background: "#dde6f0",
  color: "#334862",
  fontSize: "0.76rem",
};

const arrowStyle: CSSProperties = {
  whiteSpace: "nowrap",
  color: "#496280",
  alignSelf: "center",
};
