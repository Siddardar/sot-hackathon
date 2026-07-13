"use client";

import { useEffect, useState } from "react";

const DOT_STATES = ["", ".", "..", "..."];

export function GeneratingReportTitle() {
  const [dotIndex, setDotIndex] = useState(0);

  useEffect(() => {
    const interval = window.setInterval(() => {
      setDotIndex((index) => (index + 1) % DOT_STATES.length);
    }, 450);

    return () => window.clearInterval(interval);
  }, []);

  return (
    <h1 className="font-serif text-[44px] font-medium leading-[1.05] tracking-[-0.01em] sm:text-[56px] md:text-[72px] md:leading-[1.02]">
      Generating report
      <span className="inline-block w-[0.85em] text-left">{DOT_STATES[dotIndex]}</span>
    </h1>
  );
}
