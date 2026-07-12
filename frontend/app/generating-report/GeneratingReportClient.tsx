"use client";

import { useEffect } from "react";

const PENDING_REPORT_KEY = "glasshouse:pending-report-id";

export function GeneratingReportClient() {
  useEffect(() => {
    const redirectIfReady = () => {
      const reportId = localStorage.getItem(PENDING_REPORT_KEY);
      if (reportId) {
        localStorage.removeItem(PENDING_REPORT_KEY);
        window.location.href = `/${reportId}`;
      }
    };

    redirectIfReady();
    const interval = window.setInterval(redirectIfReady, 500);
    window.addEventListener("storage", redirectIfReady);

    return () => {
      window.clearInterval(interval);
      window.removeEventListener("storage", redirectIfReady);
    };
  }, []);

  return null;
}
