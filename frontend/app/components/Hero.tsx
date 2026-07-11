import { ExampleInferenceCard } from "./ExampleInferenceCard";
import { UploadButton } from "./UploadButton";

export function Hero() {
  return (
    <section className="grid grid-cols-1 items-end gap-14 px-6 pb-20 pt-20 sm:px-14 md:grid-cols-[1.3fr_1fr] md:gap-[60px] md:pt-24">
      <div>
        <h1 className="mb-7 font-serif text-[44px] font-medium leading-[1.05] tracking-[-0.01em] text-ink sm:text-[56px] md:text-[72px] md:leading-[1.02]">
          Your words say
          <br />
          more than you meant.
        </h1>

        <p className="mb-10 max-w-[520px] text-[19px] leading-[1.6] text-secondary">
          An LLM can guess your income, your health, who you love — from a few
          sentences you thought were casual. Glasshouse makes those guesses
          visible,
          so you stay in control of what you give away.
        </p>

        <div className="flex flex-wrap items-center gap-4">
          <UploadButton />
          <span className="text-[13px] text-faint">
            Runs privately in your browser
          </span>
        </div>
      </div>

      <ExampleInferenceCard />
    </section>
  );
}
