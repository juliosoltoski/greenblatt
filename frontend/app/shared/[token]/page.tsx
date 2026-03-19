"use client";

import { useEffect, useState, type CSSProperties } from "react";
import Link from "next/link";

import { ApiError, getSharedResource, type SharedResourceResponse } from "@/lib/api";

type SharedPageProps = {
  params: Promise<{ token: string }>;
};

type LoadState = "loading" | "ready" | "error";

export default function SharedResourcePage({ params }: SharedPageProps) {
  const [token, setToken] = useState<string | null>(null);
  const [state, setState] = useState<LoadState>("loading");
  const [payload, setPayload] = useState<SharedResourceResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;

    async function load() {
      const resolved = await params;
      if (!active) {
        return;
      }
      setToken(resolved.token);
      try {
        const shared = await getSharedResource(resolved.token);
        if (!active) {
          return;
        }
        setPayload(shared);
        setState("ready");
      } catch (loadError) {
        if (!active) {
          return;
        }
        setError(loadError instanceof ApiError ? loadError.message : "Unable to load this shared resource.");
        setState("error");
      }
    }

    void load();
    return () => {
      active = false;
    };
  }, [params]);

  return (
    <main style={pageStyle}>
      <section style={panelStyle}>
        <p style={eyebrowStyle}>Shared resource</p>
        {state === "loading" ? <h1 style={titleStyle}>Loading share link</h1> : null}
        {state === "error" ? (
          <>
            <h1 style={titleStyle}>Share link unavailable</h1>
            <p style={bodyStyle}>{error ?? "Unable to load this shared resource."}</p>
            <p style={metaStyle}>Token: {token ?? "n/a"}</p>
          </>
        ) : null}
        {state === "ready" && payload ? (
          <>
            <h1 style={titleStyle}>{payload.shared_resource.reference.title}</h1>
            <p style={bodyStyle}>
              {payload.shared_resource.reference.subtitle} · Workspace {payload.workspace_name}
            </p>
            <div style={chipRowStyle}>
              <span style={chipStyle}>{payload.share_link.access_scope.replaceAll("_", " ")}</span>
              <span style={chipStyle}>{payload.shared_resource.resource_kind.replaceAll("_", " ")}</span>
            </div>
            <pre style={preStyle}>{JSON.stringify(payload.shared_resource.payload, null, 2)}</pre>
            <Link href="/login" style={linkStyle}>
              Sign in to open the full app
            </Link>
          </>
        ) : null}
      </section>
    </main>
  );
}

const pageStyle: CSSProperties = {
  minHeight: "100vh",
  display: "grid",
  placeItems: "center",
  padding: "2rem 1rem",
};

const panelStyle: CSSProperties = {
  width: "min(960px, 100%)",
  display: "grid",
  gap: "1rem",
  padding: "1.5rem",
  borderRadius: "28px",
  background: "#ffffff",
  border: "1px solid rgba(73, 98, 128, 0.12)",
};

const eyebrowStyle: CSSProperties = {
  margin: 0,
  color: "#8a5a14",
  textTransform: "uppercase",
  letterSpacing: "0.12em",
  fontSize: "0.76rem",
};

const titleStyle: CSSProperties = {
  margin: 0,
  fontSize: "2rem",
};

const bodyStyle: CSSProperties = {
  margin: 0,
  color: "#496280",
  lineHeight: 1.6,
};

const metaStyle: CSSProperties = {
  margin: 0,
  color: "#637990",
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
  padding: "0 0.75rem",
  borderRadius: "999px",
  background: "#eef4fa",
  color: "#203247",
};

const preStyle: CSSProperties = {
  margin: 0,
  padding: "1rem",
  borderRadius: "18px",
  background: "#162132",
  color: "#f5f7fb",
  overflowX: "auto",
  fontSize: "0.88rem",
};

const linkStyle: CSSProperties = {
  color: "#1a5b8a",
  textDecoration: "none",
};
