const FAQ_ITEMS = [
  {
    question: "What file should I upload?",
    answer:
      "Upload the full export .zip when you have it. For Claude exports, you can also upload the conversations.json file or the unzipped export folder.",
  },
  {
    question: "Does this run locally?",
    answer:
      "Parsing happens in your browser first. The selected messages are sent to your configured backend so Gemini can generate the report.",
  },
  {
    question: "Why are there conservative and speculative modes?",
    answer:
      "Conservative mode sticks to clearer signals. Speculative mode includes weaker patterns, writing style, and broader guesses so you can see what a looser profiler might infer.",
  },
];

export function FAQ() {
  return (
    <section id="faq" className="scroll-mt-8 px-6 pb-[110px] sm:px-14">
      <h2 className="mb-6 text-[13px] font-semibold uppercase tracking-[0.04em] text-accent">
        FAQ
      </h2>

      <div className="grid gap-px overflow-hidden rounded-[14px] border border-hairline bg-hairline">
        {FAQ_ITEMS.map((item) => (
          <div key={item.question} className="bg-background p-[28px] sm:p-[34px]">
            <h3 className="mb-2 text-[17px] font-semibold text-ink">
              {item.question}
            </h3>
            <p className="max-w-[760px] text-[14px] leading-[1.55] text-muted">
              {item.answer}
            </p>
          </div>
        ))}
      </div>
    </section>
  );
}
