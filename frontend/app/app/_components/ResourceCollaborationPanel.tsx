"use client";

import { useEffect, useState, type CSSProperties, type FormEvent } from "react";

import {
  ApiError,
  addCollectionItem,
  createResourceComment,
  createShareLink,
  deleteResourceComment,
  listCollections,
  listResourceComments,
  listShareLinks,
  revokeShareLink,
  type ResourceComment,
  type ResourceKind,
  type ShareLink,
  type WorkspaceCollection,
} from "@/lib/api";

type ResourceCollaborationPanelProps = {
  workspaceId: number | null | undefined;
  resourceKind: ResourceKind;
  resourceId: number;
};

export function ResourceCollaborationPanel({
  workspaceId,
  resourceKind,
  resourceId,
}: ResourceCollaborationPanelProps) {
  const [comments, setComments] = useState<ResourceComment[]>([]);
  const [shareLinks, setShareLinks] = useState<ShareLink[]>([]);
  const [collections, setCollections] = useState<WorkspaceCollection[]>([]);
  const [commentBody, setCommentBody] = useState("");
  const [shareLabel, setShareLabel] = useState("");
  const [shareScope, setShareScope] = useState<ShareLink["access_scope"]>("token");
  const [selectedCollectionId, setSelectedCollectionId] = useState("");
  const [collectionNote, setCollectionNote] = useState("");
  const [baseOrigin, setBaseOrigin] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  useEffect(() => {
    if (typeof window !== "undefined") {
      setBaseOrigin(window.location.origin);
    }
  }, []);

  useEffect(() => {
    if (!workspaceId) {
      return;
    }
    void refresh();
  }, [workspaceId, resourceId, resourceKind]);

  async function refresh() {
    if (!workspaceId) {
      return;
    }
    try {
      const [commentPayload, sharePayload, collectionPayload] = await Promise.all([
        listResourceComments({ workspaceId, resourceKind, resourceId, pageSize: 50 }),
        listShareLinks({ workspaceId, resourceKind, resourceId, pageSize: 20, includeInactive: true }),
        listCollections({ workspaceId, pageSize: 50 }),
      ]);
      setComments(commentPayload.results);
      setShareLinks(sharePayload.results);
      setCollections(collectionPayload.results);
    } catch (loadError) {
      setError(formatApiError(loadError, "Unable to load collaboration details."));
    }
  }

  async function handleCreateComment(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!commentBody.trim()) {
      return;
    }
    setBusy("comment");
    setError(null);
    try {
      await createResourceComment({ resourceKind, resourceId, body: commentBody.trim() });
      setCommentBody("");
      await refresh();
    } catch (createError) {
      setError(formatApiError(createError, "Unable to save the comment."));
    } finally {
      setBusy(null);
    }
  }

  async function handleDeleteComment(commentId: number) {
    setBusy(`comment-${commentId}`);
    setError(null);
    try {
      await deleteResourceComment(commentId);
      await refresh();
    } catch (deleteError) {
      setError(formatApiError(deleteError, "Unable to delete that comment."));
    } finally {
      setBusy(null);
    }
  }

  async function handleCreateShareLink(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy("share");
    setError(null);
    try {
      await createShareLink({
        resourceKind,
        resourceId,
        label: shareLabel.trim(),
        accessScope: shareScope,
      });
      setShareLabel("");
      await refresh();
    } catch (createError) {
      setError(formatApiError(createError, "Unable to create a share link."));
    } finally {
      setBusy(null);
    }
  }

  async function handleRevokeShareLink(shareLinkId: number) {
    setBusy(`share-${shareLinkId}`);
    setError(null);
    try {
      await revokeShareLink(shareLinkId);
      await refresh();
    } catch (revokeError) {
      setError(formatApiError(revokeError, "Unable to revoke this share link."));
    } finally {
      setBusy(null);
    }
  }

  async function handleAddToCollection(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedCollectionId) {
      return;
    }
    setBusy("collection");
    setError(null);
    try {
      await addCollectionItem(Number(selectedCollectionId), {
        resourceKind,
        resourceId,
        note: collectionNote.trim(),
      });
      setCollectionNote("");
      setSelectedCollectionId("");
      await refresh();
    } catch (collectionError) {
      setError(formatApiError(collectionError, "Unable to add this resource to the selected collection."));
    } finally {
      setBusy(null);
    }
  }

  return (
    <section style={panelStyle}>
      <div style={headerStyle}>
        <div>
          <p style={eyebrowStyle}>Collaboration</p>
          <h2 style={titleStyle}>Discussion, share links, and collections</h2>
        </div>
      </div>

      {error ? <p style={errorStyle}>{error}</p> : null}

      <div style={gridStyle}>
        <section style={cardStyle}>
          <h3 style={sectionTitleStyle}>Discussion</h3>
          <form onSubmit={handleCreateComment} style={stackStyle}>
            <textarea
              value={commentBody}
              onChange={(event) => setCommentBody(event.target.value)}
              placeholder="Add context for future reviewers."
              style={textareaStyle}
            />
            <button type="submit" style={buttonStyle} disabled={busy === "comment"}>
              {busy === "comment" ? "Saving..." : "Add comment"}
            </button>
          </form>
          <div style={stackStyle}>
            {comments.length === 0 ? <p style={emptyStyle}>No comments yet.</p> : null}
            {comments.map((comment) => (
              <article key={comment.id} style={itemCardStyle}>
                <div style={itemHeaderStyle}>
                  <strong>{comment.author_display_name ?? "Unknown user"}</strong>
                  <span style={metaStyle}>{formatTimestamp(comment.created_at)}</span>
                </div>
                <p style={bodyStyle}>{comment.body}</p>
                <button
                  type="button"
                  style={linkButtonStyle}
                  onClick={() => void handleDeleteComment(comment.id)}
                  disabled={busy === `comment-${comment.id}`}
                >
                  Remove
                </button>
              </article>
            ))}
          </div>
        </section>

        <section style={cardStyle}>
          <h3 style={sectionTitleStyle}>Read-only share links</h3>
          <form onSubmit={handleCreateShareLink} style={stackStyle}>
            <input
              value={shareLabel}
              onChange={(event) => setShareLabel(event.target.value)}
              placeholder="Optional label"
              style={inputStyle}
            />
            <select value={shareScope} onChange={(event) => setShareScope(event.target.value as ShareLink["access_scope"])} style={inputStyle}>
              <option value="token">Anyone with the link</option>
              <option value="workspace_member">Workspace members only</option>
            </select>
            <button type="submit" style={buttonStyle} disabled={busy === "share"}>
              {busy === "share" ? "Creating..." : "Create share link"}
            </button>
          </form>
          <div style={stackStyle}>
            {shareLinks.length === 0 ? <p style={emptyStyle}>No share links yet.</p> : null}
            {shareLinks.map((shareLink) => (
              <article key={shareLink.id} style={itemCardStyle}>
                <div style={itemHeaderStyle}>
                  <strong>{shareLink.label ?? shareLink.resource.title}</strong>
                  <span style={metaStyle}>{shareLink.is_active ? shareLink.access_scope : "inactive"}</span>
                </div>
                <p style={bodyStyle}>{baseOrigin}{shareLink.share_path}</p>
                <div style={buttonRowStyle}>
                  <button
                    type="button"
                    style={linkButtonStyle}
                    onClick={() => void navigator.clipboard.writeText(`${baseOrigin}${shareLink.share_path}`)}
                  >
                    Copy link
                  </button>
                  {shareLink.is_active ? (
                    <button
                      type="button"
                      style={linkButtonStyle}
                      onClick={() => void handleRevokeShareLink(shareLink.id)}
                      disabled={busy === `share-${shareLink.id}`}
                    >
                      Revoke
                    </button>
                  ) : null}
                </div>
              </article>
            ))}
          </div>
        </section>
      </div>

      <section style={cardStyle}>
        <h3 style={sectionTitleStyle}>Collections</h3>
        <form onSubmit={handleAddToCollection} style={inlineFormStyle}>
          <select
            value={selectedCollectionId}
            onChange={(event) => setSelectedCollectionId(event.target.value)}
            style={inputStyle}
          >
            <option value="">Select a collection</option>
            {collections.map((collection) => (
              <option key={collection.id} value={collection.id}>
                {collection.name}
              </option>
            ))}
          </select>
          <input
            value={collectionNote}
            onChange={(event) => setCollectionNote(event.target.value)}
            placeholder="Optional note"
            style={inputStyle}
          />
          <button type="submit" style={buttonStyle} disabled={busy === "collection" || !selectedCollectionId}>
            {busy === "collection" ? "Adding..." : "Add to collection"}
          </button>
        </form>
      </section>
    </section>
  );
}

function formatTimestamp(value: string): string {
  try {
    return new Date(value).toLocaleString();
  } catch {
    return value;
  }
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

const panelStyle: CSSProperties = {
  display: "grid",
  gap: "1rem",
  padding: "1.1rem",
  borderRadius: "24px",
  background: "#ffffff",
  border: "1px solid rgba(73, 98, 128, 0.12)",
};

const headerStyle: CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  gap: "1rem",
  alignItems: "center",
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
  fontSize: "1.2rem",
};

const gridStyle: CSSProperties = {
  display: "grid",
  gap: "1rem",
  gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
};

const cardStyle: CSSProperties = {
  display: "grid",
  gap: "0.9rem",
  padding: "1rem",
  borderRadius: "20px",
  background: "#f8fbff",
  border: "1px solid rgba(73, 98, 128, 0.12)",
};

const sectionTitleStyle: CSSProperties = {
  margin: 0,
  fontSize: "1rem",
};

const stackStyle: CSSProperties = {
  display: "grid",
  gap: "0.75rem",
};

const inlineFormStyle: CSSProperties = {
  display: "grid",
  gap: "0.75rem",
  gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
};

const textareaStyle: CSSProperties = {
  minHeight: "110px",
  borderRadius: "16px",
  border: "1px solid rgba(73, 98, 128, 0.18)",
  padding: "0.85rem 0.95rem",
  resize: "vertical",
  background: "#ffffff",
};

const inputStyle: CSSProperties = {
  minHeight: "2.9rem",
  borderRadius: "14px",
  border: "1px solid rgba(73, 98, 128, 0.18)",
  padding: "0 0.85rem",
  background: "#ffffff",
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

const itemCardStyle: CSSProperties = {
  display: "grid",
  gap: "0.35rem",
  padding: "0.8rem 0.9rem",
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

const bodyStyle: CSSProperties = {
  margin: 0,
  color: "#324a63",
};

const metaStyle: CSSProperties = {
  color: "#637990",
  fontSize: "0.82rem",
};

const emptyStyle: CSSProperties = {
  margin: 0,
  color: "#637990",
};

const errorStyle: CSSProperties = {
  margin: 0,
  padding: "0.75rem 0.95rem",
  borderRadius: "16px",
  background: "#fff2f2",
  color: "#a12f2f",
};

const buttonRowStyle: CSSProperties = {
  display: "flex",
  gap: "0.75rem",
  flexWrap: "wrap",
};

const linkButtonStyle: CSSProperties = {
  border: "none",
  background: "transparent",
  color: "#1a5b8a",
  padding: 0,
  cursor: "pointer",
  textAlign: "left",
};
