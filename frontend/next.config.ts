import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Allow the dev server's dev-only assets/endpoints (client chunks, HMR) to be
  // requested through an ngrok tunnel. Without this, Next blocks these as
  // cross-origin, hydration never runs, and client interactivity (button
  // toggles, dialogs) silently stops working when accessed via ngrok.
  allowedDevOrigins: ["*.ngrok-free.app", "*.ngrok.app", "*.ngrok.io"],

  // NOTE: the /backend/* proxy is a streaming route handler at
  // app/backend/[...path]/route.ts, not a rewrite. Next's `rewrites` buffer
  // streaming responses, which breaks the /analyze SSE stream through a tunnel.
};

export default nextConfig;
