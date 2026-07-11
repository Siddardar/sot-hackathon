// Persists exposure reports in localStorage, keyed by a short hash, so a report
// can be re-opened by revisiting /{id}. Client-only (uses localStorage + crypto).

import type { Inference, ParseResponse } from "./api";

const PREFIX = "glasshouse:report:";
const INDEX_KEY = "glasshouse:reports";
const MAX_INDEX = 20;

export interface StoredReport {
  id: string;
  createdAt: number;
  source: string;
  parsed: ParseResponse;
  findings: Inference[];
}

export interface ReportIndexEntry {
  id: string;
  createdAt: number;
  title: string;
}

/** Short, URL-friendly random id (10 base36 chars). */
export function newReportId(): string {
  const bytes = new Uint8Array(8);
  crypto.getRandomValues(bytes);
  return Array.from(bytes, (b) => b.toString(36).padStart(2, "0")).join("").slice(0, 10);
}

function summarize(report: StoredReport): string {
  const c = report.parsed.conversations.length;
  const f = report.findings.length;
  return `${c} conversation${c === 1 ? "" : "s"} · ${f} finding${f === 1 ? "" : "s"}`;
}

/** Save a report + update the index. Returns false if storage rejected it (e.g. quota). */
export function saveReport(report: StoredReport): boolean {
  try {
    localStorage.setItem(PREFIX + report.id, JSON.stringify(report));
    const entry: ReportIndexEntry = {
      id: report.id,
      createdAt: report.createdAt,
      title: summarize(report),
    };
    const next = [entry, ...listReports().filter((e) => e.id !== report.id)].slice(0, MAX_INDEX);
    localStorage.setItem(INDEX_KEY, JSON.stringify(next));
    return true;
  } catch (err) {
    console.warn("[Glasshouse] could not persist report (storage full?)", err);
    return false;
  }
}

export function loadReport(id: string): StoredReport | null {
  try {
    const raw = localStorage.getItem(PREFIX + id);
    return raw ? (JSON.parse(raw) as StoredReport) : null;
  } catch {
    return null;
  }
}

export function listReports(): ReportIndexEntry[] {
  try {
    const raw = localStorage.getItem(INDEX_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? (parsed as ReportIndexEntry[]) : [];
  } catch {
    return [];
  }
}
