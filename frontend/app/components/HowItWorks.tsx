const STEPS = [
  {
    number: "1",
    title: "Upload your chat",
    description: "A file export or pasted transcript — whatever you have.",
  },
  {
    number: "2",
    title: "Tell reads it like a model would",
    description: "Surfacing the inferences an LLM makes silently.",
  },
  {
    number: "3",
    title: "Take back control",
    description:
      "See exactly what you gave away, and decide what to change.",
  },
];

export function HowItWorks() {
  return (
    <section className="px-6 pb-[100px] pt-5 sm:px-14">
      <h2 className="mb-6 text-[13px] font-semibold uppercase tracking-[0.04em] text-accent">
        How it works
      </h2>

      {/* The 1px gap + hairline background shows through as dividers between cells */}
      <div className="grid grid-cols-1 gap-px overflow-hidden rounded-[14px] border border-hairline bg-hairline md:grid-cols-3">
        {STEPS.map((step) => (
          <div key={step.number} className="bg-background p-[34px]">
            <div className="mb-3 font-serif text-[34px] font-medium text-accent">
              {step.number}
            </div>
            <h3 className="mb-2 text-[17px] font-semibold text-ink">
              {step.title}
            </h3>
            <p className="text-[14px] leading-[1.55] text-muted">
              {step.description}
            </p>
          </div>
        ))}
      </div>
    </section>
  );
}
