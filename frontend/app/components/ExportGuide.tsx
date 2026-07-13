"use client";

import Image, { type StaticImageData } from "next/image";
import { useState } from "react";

import claudeScreenshot from "../../screenshots/screenshot-claude.png";
import chatgptScreenshot from "../../screenshots/screenshot-gpt.png";

type Provider = "chatgpt" | "claude";

interface ExportGuideContent {
  label: string;
  screenshotLabel: string;
  screenshot: StaticImageData;
  steps: string[];
}

const EXPORT_GUIDES: Record<Provider, ExportGuideContent> = {
  chatgpt: {
    label: "ChatGPT",
    screenshotLabel: "ChatGPT export screen",
    screenshot: chatgptScreenshot,
    steps: [
      "Open ChatGPT and click your profile in the bottom-left",
      "Go to Settings -> Data controls",
      'Click "Export data" and confirm',
      "Wait for the email download link, then download the .zip",
      "Upload the .zip!",
    ],
  },
  claude: {
    label: "Claude",
    screenshotLabel: "Claude export screen",
    screenshot: claudeScreenshot,
    steps: [
      "Open Claude and click your initials in the bottom-left",
      "Go to Settings -> Privacy",
      'Click "Export data" and confirm',
      "Wait for Anthropic to email your export link and download the .zip",
      "Upload the .zip!",
    ],
  },
};

const PROVIDERS: Provider[] = ["chatgpt", "claude"];

export function ExportGuide() {
  const [provider, setProvider] = useState<Provider>("claude");
  const guide = EXPORT_GUIDES[provider];

  return (
    <div id="export-guide" className="mt-14 scroll-mt-8">
      <div className="mb-8 flex flex-col gap-5 md:flex-row md:items-start md:justify-between">
        <div>
          <p className="mb-3 text-[12px] font-bold uppercase tracking-[0.12em] text-accent">
            Don&apos;t have a file yet?
          </p>
          <h3 className="font-serif text-[30px] font-semibold leading-tight text-ink sm:text-[36px]">
            How to export your chats
          </h3>
        </div>

        <div className="relative z-10 inline-flex w-fit rounded-full bg-[#f1e9df] p-1">
          {PROVIDERS.map((item) => {
            const active = provider === item;
            return (
              <button
                key={item}
                type="button"
                onClick={() => setProvider(item)}
                className={`touch-manipulation rounded-full px-5 py-2.5 text-[14px] font-bold transition-colors cursor-pointer sm:px-7 ${
                  active
                    ? "bg-accent text-accent-foreground shadow-sm"
                    : "text-muted hover:text-ink"
                }`}
              >
                {EXPORT_GUIDES[item].label}
              </button>
            );
          })}
        </div>
      </div>

      <div className="grid gap-8 lg:grid-cols-[minmax(0,0.9fr)_minmax(360px,1.1fr)] lg:items-stretch">
        <ol className="space-y-6">
          {guide.steps.map((step, index) => (
            <li key={step} className="grid grid-cols-[42px_minmax(0,1fr)] gap-4">
              <div className="flex flex-col items-center">
                <span className="font-serif text-[34px] font-medium leading-none text-accent">
                  {index + 1}
                </span>
                {index < guide.steps.length - 1 && (
                  <span className="mt-2 h-6 w-px bg-hairline" aria-hidden="true" />
                )}
              </div>
              <div className="pt-1.5 text-[17px] font-semibold leading-[1.45] text-ink">
                {step}
              </div>
            </li>
          ))}
        </ol>

        <figure className="relative min-h-[260px] overflow-hidden rounded-[22px] border-2 border-dashed border-[#d8c8b4] bg-surface/45 sm:min-h-[340px] lg:min-h-full">
          <Image
            src={guide.screenshot}
            alt={`Screenshot: ${guide.screenshotLabel}`}
            fill
            className="pointer-events-none object-cover object-top"
            sizes="(min-width: 1024px) 52vw, 100vw"
            priority={false}
          />
        </figure>
      </div>

      <p className="mx-auto mt-8 max-w-[780px] text-center text-[14px] font-normal leading-[1.55] text-muted">
        Disclaimer: Exports can take a few minutes or days to arrive by email. If you are using Claude you can upload the conversation.json file as well.
      </p>
    </div>
  );
}
