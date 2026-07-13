import { GeneratingReportClient } from "./GeneratingReportClient";
import { GeneratingReportTitle } from "./GeneratingReportTitle";

export default function GeneratingReportPage() {
  return (
    <main className="flex min-h-screen items-center justify-center px-6 text-ink">
      <GeneratingReportClient />
      <GeneratingReportTitle />
    </main>
  );
}
