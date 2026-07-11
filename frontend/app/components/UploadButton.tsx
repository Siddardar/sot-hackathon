"use client";

export function UploadButton() {
  // Upload / analysis is intentionally a no-op for now — the backend that runs
  // the inference isn't wired up yet. This is where the file picker + analysis
  // flow will be triggered once it exists.
  const handleUpload = () => {};

  return (
    <button
      type="button"
      onClick={handleUpload}
      className="rounded-full bg-accent px-[30px] py-4 text-[15px] font-semibold text-accent-foreground transition-opacity hover:opacity-90 cursor-pointer"
    >
      Upload a conversation
    </button>
  );
}
