"use client";

import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { Report } from "../components/Report";
import { loadReport, type StoredReport } from "../lib/reportStore";

type LoadState =
  | { status: "loading" }
  | { status: "found"; report: StoredReport }
  | { status: "missing" };

export default function ReportPage() {
  const params = useParams<{ reportId: string }>();
  const reportId = params?.reportId;
  const [state, setState] = useState<LoadState>({ status: "loading" });

  useEffect(() => {
    if (!reportId) {
      setState({ status: "missing" });
      return;
    }
    // localStorage is client-only, so load after mount.
    const report = loadReport(reportId);
    setState(report ? { status: "found", report } : { status: "missing" });
  }, [reportId]);

  if (state.status === "loading") {
    return <Note title="Loading report…" />;
  }

  if (state.status === "missing") {
    return (
      <Note title="Report not found">
        This report isn’t saved on this device. Reports are stored locally in the browser that created
        them, so they can only be reopened there.
        <br />
        <a className="mt-4 inline-block text-accent underline" href="/">
          Back to Glasshouse
        </a>
      </Note>
    );
  }

  return (
    <Report
      parsed={state.report.parsed}
      findings={state.report.findings}
      createdAt={state.report.createdAt}
      mode={state.report.mode}
    />
  );
}

function Note({ title, children }: { title: string; children?: React.ReactNode }) {
  return (
    <div className="mx-auto flex min-h-screen max-w-[560px] flex-col justify-center px-6 py-20 text-center">
      <h1 className="mb-3 font-serif text-[26px] text-ink">{title}</h1>
      {children && <p className="text-[15px] leading-[1.6] text-secondary">{children}</p>}
    </div>
  );
}
