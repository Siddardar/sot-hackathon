// Derives the exposure-report view model from a parse result + findings.
// Pure (no DOM), so it can run on the client during render.

import type { Conversation, Inference, Message, ParseResponse, Tier } from "./api";

export interface TierMeta {
  key: Tier;
  label: string; // section header, e.g. "Sensitive · GDPR Article 9"
  short: string; // legend label, e.g. "Sensitive"
  accent: string; // bar / quote-border color
  badgeBg: string;
  badgeText: string;
  weight: number; // leakage-score points per finding
}

// Ordered by severity (highest first) — this is the display order.
export const TIER_ORDER: Tier[] = ["D", "C", "B", "A"];

export const TIER_META: Record<Tier, TierMeta> = {
  D: { key: "D", label: "Sensitive · GDPR Article 9", short: "Sensitive (Art. 9)", accent: "#c1543a", badgeBg: "#f6ddd5", badgeText: "#9a3a26", weight: 5 },
  C: { key: "C", label: "Compound inference", short: "Compound", accent: "#c0862f", badgeBg: "#f4e6c9", badgeText: "#855415", weight: 3 },
  B: { key: "B", label: "Direct inference", short: "Direct", accent: "#4f74a6", badgeBg: "#dde7f3", badgeText: "#33517d", weight: 2 },
  A: { key: "A", label: "Explicit disclosure", short: "Explicit", accent: "#9a7b2e", badgeBg: "#efe7cf", badgeText: "#6f5a1e", weight: 1 },
};

export interface Severity {
  label: string;
  tone: string;
  blurb: string;
}

export interface TierRow {
  tier: Tier;
  count: number;
  points: number;
  barPct: number;
}

export interface TierGroup {
  tier: Tier;
  meta: TierMeta;
  findings: Inference[];
}

export interface ReportData {
  findings: Inference[];
  conversations: Conversation[];
  messages: Message[];
  labelOf: (messageId: string) => string;
  groups: TierGroup[];
  tierRows: TierRow[];
  score: number;
  severity: Severity;
  totals: { findings: number; categories: number; sensitive: number };
  topMessages: { label: string; count: number }[];
  recommendations: string[];
  source: string;
  date: string;
}

export function prettyCategory(id: string): string {
  return id.replace(/_/g, " ");
}

function severityLabel(score: number): { label: string; tone: string } {
  if (score <= 0) return { label: "No exposure detected", tone: "#4a9d6b" };
  if (score <= 8) return { label: "Limited exposure", tone: "#4a9d6b" };
  if (score <= 20) return { label: "Moderate exposure", tone: "#c0862f" };
  if (score <= 40) return { label: "High exposure", tone: "#d0692f" };
  return { label: "Severe exposure", tone: "#c1543a" };
}

function formatUtc(ms: number): string {
  // e.g. "2026-07-11 15:08 UTC"
  return new Date(ms).toISOString().replace("T", " ").slice(0, 16) + " UTC";
}

export function buildReport(
  parsed: ParseResponse,
  findings: Inference[],
  opts: { createdAt?: number } = {},
): ReportData {
  const conversations = parsed.conversations;
  const messages = conversations.flatMap((c) => c.messages);

  // Stable short labels (m0, m1, …) in transcript order.
  const labelMap = new Map<string, string>();
  messages.forEach((m, i) => labelMap.set(m.id, `m${i}`));
  const labelOf = (id: string) => labelMap.get(id) ?? id;

  const groups: TierGroup[] = TIER_ORDER.map((tier) => ({
    tier,
    meta: TIER_META[tier],
    findings: findings.filter((f) => f.tier === tier),
  })).filter((g) => g.findings.length > 0);

  const rawRows = TIER_ORDER.map((tier) => {
    const count = findings.filter((f) => f.tier === tier).length;
    return { tier, count, points: count * TIER_META[tier].weight };
  });
  const maxPoints = Math.max(0, ...rawRows.map((r) => r.points));
  const tierRows: TierRow[] = rawRows.map((r) => ({
    ...r,
    barPct: maxPoints > 0 ? Math.round((r.points / maxPoints) * 100) : 0,
  }));

  const score = rawRows.reduce((sum, r) => sum + r.points, 0);
  const sev = severityLabel(score);

  const sensitive = findings.filter((f) => f.tier === "D").length;
  const categories = new Set(findings.map((f) => f.category_id)).size;

  // Most-cited messages (by number of findings quoting them).
  const cites = new Map<string, number>();
  for (const f of findings) {
    for (const ev of f.evidence) {
      cites.set(ev.message_id, (cites.get(ev.message_id) ?? 0) + 1);
    }
  }
  const topMessages = [...cites.entries()]
    .sort((a, b) => b[1] - a[1])
    .slice(0, 3)
    .map(([id, count]) => ({ label: labelOf(id), count }));

  const sensitiveCategories = [
    ...new Set(findings.filter((f) => f.tier === "D").map((f) => prettyCategory(f.category_id))),
  ];

  const blurb =
    findings.length === 0
      ? "No inferences were extracted from these conversations."
      : sensitive > 0
        ? `This history exposes ${sensitive} sensitive attribute${sensitive === 1 ? "" : "s"} (${sensitiveCategories.join(", ")}) alongside enough detail to identify you and your context. Treat it as high risk if shared or breached.`
        : `No special-category data surfaced, but the ${findings.length} inference${findings.length === 1 ? "" : "s"} below still build an identifying picture of you and your context. Treat an exported history as sensitive.`;

  const recommendations: string[] = [];
  if (sensitive > 0) {
    recommendations.push(
      `This history reveals special category information (${sensitiveCategories.join(", ")}). These are the details most worth keeping out of a general assistant, or reserving for a local model.`,
    );
  } else {
    recommendations.push(
      "No special-category (GDPR Article 9) data was detected, but the profile below still identifies you and your context — keep that in mind before sharing this history.",
    );
  }
  if (topMessages.length > 0) {
    recommendations.push(
      `The messages carrying the most exposure are ${topMessages.map((t) => t.label).join(", ")}. Redacting or rephrasing these removes a large share of the profile.`,
    );
  }
  recommendations.push(
    "Turning off chat history or memory would stop this profile accumulating across sessions, which is what turns separate topics into one detailed picture.",
    "Treat an exported chat history like a diary. If you would not hand the file to a stranger, do not upload it, share it, or leave it in a synced folder.",
  );

  return {
    findings,
    conversations,
    messages,
    labelOf,
    groups,
    tierRows,
    score,
    severity: { label: sev.label, tone: sev.tone, blurb },
    totals: { findings: findings.length, categories, sensitive },
    topMessages,
    recommendations,
    source: parsed.format,
    date: formatUtc(opts.createdAt ?? Date.now()),
  };
}
