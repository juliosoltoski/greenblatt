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
  createCollection,
  deleteCollection,
  getCurrentUser,
  listActivityEvents,
  listCollections,
  updateCollection,
  type ActivityEvent,
  type CurrentUser,
  type WorkspaceCollection,
} from "@/lib/api";

type LoadState = "loading" | "ready" | "error";

export function CollaborationHub() {
  const router = useRouter();
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [collections, setCollections] = useState<WorkspaceCollection[]>([]);
  const [activity, setActivity] = useState<ActivityEvent[]>([]);
  const [state, setState] = useState<LoadState>("loading");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [isPinned, setIsPinned] = useState(true);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [isCreating, setIsCreating] = useState(false);

  useEffect(() => {
    let active = true;

    async function load() {
      try {
        const currentUser = await getCurrentUser();
        const workspaceId = currentUser.active_workspace?.id;
        const [collectionPayload, activityPayload] = await Promise.all([
          listCollections({ workspaceId, pageSize: 50 }),
          listActivityEvents({ workspaceId, pageSize: 40 }),
        ]);
        if (!active) {
          return;
        }
        setUser(currentUser);
        setCollections(collectionPayload.results);
        setActivity(activityPayload.results);
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
            : "Unable to load collaboration tools.",
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
    const [collectionPayload, activityPayload] = await Promise.all([
      listCollections({ workspaceId, pageSize: 50 }),
      listActivityEvents({ workspaceId, pageSize: 40 }),
    ]);
    setCollections(collectionPayload.results);
    setActivity(activityPayload.results);
  }

  async function handleCreateCollection(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (user == null || !name.trim()) {
      return;
    }
    setIsCreating(true);
    setError(null);
    setNotice(null);
    try {
      await createCollection({
        workspaceId: user.active_workspace?.id,
        name: name.trim(),
        description: description.trim(),
        isPinned,
      });
      setName("");
      setDescription("");
      setIsPinned(true);
      await refresh(user);
      setNotice("Collection saved.");
    } catch (createError) {
      setError(
        formatApiError(createError, "Unable to create that collection."),
      );
    } finally {
      setIsCreating(false);
    }
  }

  async function handleTogglePin(collection: WorkspaceCollection) {
    if (user == null) {
      return;
    }
    setBusyId(collection.id);
    setError(null);
    setNotice(null);
    try {
      await updateCollection(collection.id, {
        isPinned: !collection.is_pinned,
      });
      await refresh(user);
      setNotice(
        collection.is_pinned
          ? "Collection unpinned."
          : "Collection pinned to top.",
      );
    } catch (updateError) {
      setError(
        formatApiError(updateError, "Unable to update this collection."),
      );
    } finally {
      setBusyId(null);
    }
  }

  async function handleDelete(collection: WorkspaceCollection) {
    if (
      user == null ||
      !window.confirm(`Delete collection "${collection.name}"?`)
    ) {
      return;
    }
    setBusyId(collection.id);
    setError(null);
    setNotice(null);
    try {
      await deleteCollection(collection.id);
      await refresh(user);
      setNotice("Collection deleted.");
    } catch (deleteError) {
      setError(
        formatApiError(deleteError, "Unable to delete this collection."),
      );
    } finally {
      setBusyId(null);
    }
  }

  if (state === "loading") {
    return (
      <main style={pageStyle}>
        <section style={panelStyle}>
          <p style={eyebrowStyle}>Collaboration</p>
          <h1 style={titleStyle}>Loading shared research activity</h1>
        </section>
      </main>
    );
  }

  if (state === "error" || user == null) {
    return (
      <main style={pageStyle}>
        <section style={panelStyle}>
          <p style={eyebrowStyle}>Collaboration</p>
          <h1 style={titleStyle}>Collaboration unavailable</h1>
          <p style={bodyStyle}>
            {error ?? "Unable to open your collaboration workspace."}
          </p>
          <Link href="/app" style={ghostLinkStyle}>
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
            <p style={eyebrowStyle}>Collaboration</p>
            <h1 style={titleStyle}>Keep shared research organized</h1>
          </div>
          <div style={actionRowStyle}>
            <Link href="/app/templates" style={ghostLinkStyle}>
              Open templates
            </Link>
            <Link href="/app/history" style={ghostLinkStyle}>
              Open history
            </Link>
          </div>
        </div>

        <p style={bodyStyle}>
          Collections keep high-conviction work easy to find, while recent
          activity shows what moved across the workspace. Use both to keep
          shared research reviewable instead of scattered.
        </p>

        {error ? <p style={errorStyle}>{error}</p> : null}
        {notice ? <p style={infoStyle}>{notice}</p> : null}

        <div style={layoutStyle}>
          <section style={cardStyle}>
            <h2 style={cardTitleStyle}>Save collection</h2>
            <form style={formStyle} onSubmit={handleCreateCollection}>
              <input
                value={name}
                onChange={(event) => setName(event.target.value)}
                placeholder="Collection name"
                style={inputStyle}
              />
              <textarea
                value={description}
                onChange={(event) => setDescription(event.target.value)}
                placeholder="What belongs in this collection and why?"
                style={textareaStyle}
              />
              <label style={checkboxStyle}>
                <input
                  type="checkbox"
                  checked={isPinned}
                  onChange={(event) => setIsPinned(event.target.checked)}
                />
                <span>Pin collection to top</span>
              </label>
              <button type="submit" style={buttonStyle} disabled={isCreating}>
                {isCreating ? "Saving..." : "Save collection"}
              </button>
            </form>
          </section>

          <section style={cardStyle}>
            <h2 style={cardTitleStyle}>Collections</h2>
            <div style={listStyle}>
              {collections.length === 0 ? (
                <p style={bodyStyle}>
                  No collections yet. Save one to group related runs and
                  templates for faster review.
                </p>
              ) : null}
              {collections.map((collection) => (
                <article key={collection.id} style={itemCardStyle}>
                  <div style={itemHeaderStyle}>
                    <div>
                      <strong>{collection.name}</strong>
                      <p style={metaStyle}>
                        {collection.items.length} item
                        {collection.items.length === 1 ? "" : "s"}
                        {collection.is_pinned ? " · pinned" : ""}
                      </p>
                    </div>
                    <div style={actionRowStyle}>
                      <button
                        type="button"
                        style={linkButtonStyle}
                        onClick={() => void handleTogglePin(collection)}
                        disabled={busyId === collection.id}
                      >
                        {collection.is_pinned ? "Unpin" : "Pin to top"}
                      </button>
                      <button
                        type="button"
                        style={linkButtonStyle}
                        onClick={() => void handleDelete(collection)}
                        disabled={busyId === collection.id}
                      >
                        Delete
                      </button>
                    </div>
                  </div>
                  {collection.description ? (
                    <p style={bodyStyle}>{collection.description}</p>
                  ) : null}
                  <div style={chipRowStyle}>
                    {collection.items.slice(0, 4).map((item) => (
                      <Link
                        key={item.id}
                        href={item.resource.href}
                        style={chipStyle}
                      >
                        {item.resource.title}
                      </Link>
                    ))}
                  </div>
                </article>
              ))}
            </div>
          </section>
        </div>

        <section style={cardStyle}>
          <h2 style={cardTitleStyle}>Recent activity</h2>
          <div style={listStyle}>
            {activity.length === 0 ? (
              <p style={bodyStyle}>
                No shared activity yet. New runs, template saves, and collection
                updates will show up here.
              </p>
            ) : null}
            {activity.map((event) => (
              <article key={event.id} style={itemCardStyle}>
                <div style={itemHeaderStyle}>
                  <strong>{event.summary}</strong>
                  <span style={metaStyle}>
                    {formatTimestamp(event.created_at)}
                  </span>
                </div>
                <p style={metaStyle}>
                  {event.actor_display_name ?? "Unknown user"} ·{" "}
                  {humanizeLabel(event.verb)}
                </p>
              </article>
            ))}
          </div>
        </section>
      </section>
    </main>
  );
}

function formatTimestamp(value: string): string {
  try {
    return new Date(value).toLocaleString();
  } catch {
    return value;
  }
}

function humanizeLabel(value: string): string {
  return value.replaceAll("_", " ");
}

function formatApiError(error: unknown, fallback: string): string {
  if (error instanceof ApiError) {
    return error.message;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return fallback;
}

const pageStyle: CSSProperties = {
  display: "grid",
  gap: "1rem",
};

const panelStyle: CSSProperties = {
  display: "grid",
  gap: "1rem",
  padding: "1.2rem",
  borderRadius: "28px",
  background: "#ffffff",
  border: "1px solid rgba(73, 98, 128, 0.12)",
};

const headerRowStyle: CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  gap: "1rem",
  alignItems: "center",
  flexWrap: "wrap",
};

const eyebrowStyle: CSSProperties = {
  margin: 0,
  color: "#8a5a14",
  textTransform: "uppercase",
  letterSpacing: "0.12em",
  fontSize: "0.76rem",
};

const titleStyle: CSSProperties = {
  margin: "0.25rem 0 0",
  fontSize: "1.9rem",
};

const bodyStyle: CSSProperties = {
  margin: 0,
  color: "#496280",
  lineHeight: 1.6,
};

const errorStyle: CSSProperties = {
  margin: 0,
  padding: "0.75rem 0.95rem",
  borderRadius: "16px",
  background: "#fff2f2",
  color: "#a12f2f",
};

const infoStyle: CSSProperties = {
  margin: 0,
  padding: "0.75rem 0.95rem",
  borderRadius: "16px",
  background: "#e6f1ff",
  color: "#0f4c81",
};

const layoutStyle: CSSProperties = {
  display: "grid",
  gap: "1rem",
  gridTemplateColumns: "minmax(280px, 360px) minmax(0, 1fr)",
};

const cardStyle: CSSProperties = {
  display: "grid",
  gap: "1rem",
  padding: "1rem",
  borderRadius: "22px",
  background: "#f8fbff",
  border: "1px solid rgba(73, 98, 128, 0.12)",
};

const cardTitleStyle: CSSProperties = {
  margin: 0,
  fontSize: "1.05rem",
};

const formStyle: CSSProperties = {
  display: "grid",
  gap: "0.8rem",
};

const inputStyle: CSSProperties = {
  minHeight: "2.9rem",
  borderRadius: "14px",
  border: "1px solid rgba(73, 98, 128, 0.18)",
  padding: "0 0.9rem",
  background: "#ffffff",
};

const textareaStyle: CSSProperties = {
  minHeight: "120px",
  borderRadius: "16px",
  border: "1px solid rgba(73, 98, 128, 0.18)",
  padding: "0.85rem 0.95rem",
  resize: "vertical",
  background: "#ffffff",
};

const checkboxStyle: CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: "0.6rem",
  color: "#324a63",
};

const buttonStyle: CSSProperties = {
  minHeight: "2.8rem",
  borderRadius: "999px",
  border: "none",
  background: "#162132",
  color: "#f5f7fb",
  padding: "0 1rem",
  fontWeight: 600,
  cursor: "pointer",
};

const listStyle: CSSProperties = {
  display: "grid",
  gap: "0.8rem",
};

const itemCardStyle: CSSProperties = {
  display: "grid",
  gap: "0.35rem",
  padding: "0.85rem 0.95rem",
  borderRadius: "16px",
  background: "#ffffff",
  border: "1px solid rgba(73, 98, 128, 0.12)",
};

const itemHeaderStyle: CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  gap: "0.75rem",
  alignItems: "center",
  flexWrap: "wrap",
};

const metaStyle: CSSProperties = {
  margin: 0,
  color: "#637990",
  fontSize: "0.84rem",
};

const actionRowStyle: CSSProperties = {
  display: "flex",
  gap: "0.75rem",
  flexWrap: "wrap",
};

const ghostLinkStyle: CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  justifyContent: "center",
  minHeight: "2.6rem",
  padding: "0 0.9rem",
  borderRadius: "999px",
  border: "1px solid rgba(73, 98, 128, 0.18)",
  textDecoration: "none",
};

const linkButtonStyle: CSSProperties = {
  border: "none",
  background: "transparent",
  color: "#1a5b8a",
  padding: 0,
  cursor: "pointer",
};

const chipRowStyle: CSSProperties = {
  display: "flex",
  gap: "0.5rem",
  flexWrap: "wrap",
};

const chipStyle: CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  justifyContent: "center",
  minHeight: "2rem",
  padding: "0 0.7rem",
  borderRadius: "999px",
  background: "#edf4fb",
  textDecoration: "none",
  color: "#203247",
  fontSize: "0.85rem",
};
