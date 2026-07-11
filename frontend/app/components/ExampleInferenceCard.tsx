export function ExampleInferenceCard() {
  return (
    <div className="rounded-[18px] border-[1.5px] border-hairline bg-surface p-9">
      <div className="mb-[14px] text-[12px] font-semibold uppercase tracking-[0.06em] text-accent">
        Example inference
      </div>

      <p className="mb-4 text-[15px] leading-[1.6] text-ink-soft">
        &ldquo;I&rsquo;ve been so tired lately, work is a lot right now and
        I&rsquo;m not sleeping great before my appointment next week.&rdquo;
      </p>

      <div className="my-4 h-px bg-hairline" />

      <div className="mb-1.5 text-[13px] font-semibold text-ink">
        Glasshouse inferred:
      </div>
      <div className="text-[14px] leading-[1.5] text-secondary">
        Possible burnout · upcoming medical visit · sleep disturbance
      </div>
    </div>
  );
}
