import { GeneratingReportClient } from "./GeneratingReportClient";

export default function GeneratingReportPage() {
  return (
    <main className="flex min-h-screen items-center justify-center px-6 text-ink">
      <GeneratingReportClient />
      <h1 className="font-serif text-[44px] font-medium leading-[1.05] tracking-[-0.01em] sm:text-[56px] md:text-[72px] md:leading-[1.02]">
        Generating report...
      </h1>
    </main>
  );
}
