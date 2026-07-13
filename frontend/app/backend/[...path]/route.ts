import { NextRequest } from "next/server";

// Node runtime so we can reach the backend on localhost, and never cache.
export const runtime = "nodejs";
export const dynamic = "force-dynamic";
export const fetchCache = "force-no-store";

// Where the FastAPI backend actually listens. Server-side only, so it stays on
// localhost even when the frontend is reached through an ngrok tunnel.
const BACKEND_ORIGIN = process.env.BACKEND_ORIGIN ?? "http://localhost:8000";

/**
 * Same-origin proxy to the local backend so the app works through an ngrok
 * tunnel with a single tunnel and no CORS. Implemented as a route handler
 * rather than a Next `rewrite` because rewrites buffer streaming responses,
 * which stalls the /analyze SSE stream until it times out over the tunnel.
 * Here we pipe the upstream body straight through so events flush as they
 * arrive.
 */
async function proxy(
  req: NextRequest,
  ctx: { params: Promise<{ path?: string[] }> },
) {
  const { path = [] } = await ctx.params;
  const target = `${BACKEND_ORIGIN}/${path.join("/")}${req.nextUrl.search}`;

  const headers = new Headers(req.headers);
  headers.delete("host");
  headers.delete("connection");
  headers.delete("content-length");
  // Ask the backend not to gzip — compression forces response buffering, which
  // defeats SSE streaming.
  headers.delete("accept-encoding");

  const hasBody = req.method !== "GET" && req.method !== "HEAD";
  const body = hasBody ? await req.arrayBuffer() : undefined;

  const upstream = await fetch(target, {
    method: req.method,
    headers,
    body,
    redirect: "manual",
    cache: "no-store",
  });

  // Stream the body through untouched; strip length/encoding (they no longer
  // match once we pipe) and add anti-buffering hints for any hop in front.
  const resHeaders = new Headers(upstream.headers);
  resHeaders.delete("content-length");
  resHeaders.delete("content-encoding");
  resHeaders.set("Cache-Control", "no-cache, no-transform");
  resHeaders.set("X-Accel-Buffering", "no");

  return new Response(upstream.body, {
    status: upstream.status,
    statusText: upstream.statusText,
    headers: resHeaders,
  });
}

export const GET = proxy;
export const POST = proxy;
export const PUT = proxy;
export const PATCH = proxy;
export const DELETE = proxy;
export const OPTIONS = proxy;
export const HEAD = proxy;
