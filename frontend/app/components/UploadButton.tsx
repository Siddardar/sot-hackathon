"use client";

import { useEffect, useRef, useState } from "react";

import { analyze, parseExport, type ExportFiles } from "../lib/api";
import { newReportId, saveReport } from "../lib/reportStore";

type UploadMode = "json" | "zip" | "folder";

const ACCEPTED_FILE_TYPES = ".json,application/json,.zip,application/zip,application/x-zip-compressed";

/** Pick a file by basename from a folder selection, preferring the shallowest path. */
function pickFolderFile(files: File[], basename: string): File | undefined {
  const matches = files.filter(
    (f) => (f.webkitRelativePath || f.name).split("/").pop() === basename,
  );
  if (matches.length === 0) return undefined;
  return matches.sort(
    (a, b) =>
      (a.webkitRelativePath || a.name).split("/").length -
      (b.webkitRelativePath || b.name).split("/").length,
  )[0];
}

export function UploadButton() {
  const containerRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const folderInputRef = useRef<HTMLInputElement>(null);
  const [isOpen, setIsOpen] = useState(false);
  const [selectionLabel, setSelectionLabel] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [reportId, setReportId] = useState<string | null>(null);

  // Upload -> /parse -> /analyze -> persist the report and open it in a new tab.
  const runPipeline = async (parts: ExportFiles) => {
    setError(null);
    setReportId(null);
    try {
      setStatus("Uploading & parsing…");
      const parsed = await parseExport(parts);
      console.log("[Glasshouse] /parse response:", parsed);
      console.log(
        `[Glasshouse] format=${parsed.format} · conversations=${parsed.conversations.length}`,
      );
      if (parsed.account) console.log("[Glasshouse] account (users.json):", parsed.account);
      if (parsed.memory)
        console.log("[Glasshouse] provider memory (memories.json):", parsed.memory);

      // Analyze the whole folder: every conversation's (human) messages together.
      const allMessages = parsed.conversations.flatMap((c) => c.messages);
      if (allMessages.length === 0) {
        setStatus(null);
        setError("No messages were found to analyze.");
        return;
      }

      setStatus(
        `Analyzing ${parsed.conversations.length} conversations (${allMessages.length} messages)…`,
      );
      console.log(
        `[Glasshouse] analyzing ${parsed.conversations.length} conversations, ${allMessages.length} messages across 4 tier passes…`,
      );

      const inferences = await analyze(allMessages, {
        onMeta: (meta) =>
          console.log(
            `[Glasshouse] meta:`,
            meta,
            "tier_counts:",
            meta.tier_counts,
            meta.mock ? "(sample output — profiler in mock mode)" : "",
          ),
        onInference: (inf) =>
          console.log(
            `[Glasshouse] finding [${inf.tier}] ${inf.category_id} (${inf.subject ?? "self"}):`,
            inf,
          ),
        onError: (message) => console.error("[Glasshouse] analyze error:", message),
        onDone: (data) => console.log("[Glasshouse] done:", data),
      });

      console.log("[Glasshouse] full dossier:", inferences);

      // Persist the report locally and open it in a new tab at /{id}.
      const id = newReportId();
      const saved = saveReport({
        id,
        createdAt: Date.now(),
        source: parsed.format,
        parsed,
        findings: inferences,
      });
      setReportId(id);
      setStatus(
        saved
          ? `Done — ${inferences.length} findings.`
          : `Done — ${inferences.length} findings (couldn't save locally; use the link below now).`,
      );
      // Best-effort auto-open; the await above means popup blockers may stop it,
      // so the "Open report" link below is the reliable path.
      window.open(`/${id}`, "_blank", "noopener");
    } catch (err) {
      console.error("[Glasshouse] pipeline error:", err);
      setStatus(null);
      setError(err instanceof Error ? err.message : "Something went wrong.");
    }
  };

  useEffect(() => {
    const folderInput = folderInputRef.current;

    if (!folderInput) return;

    folderInput.setAttribute("webkitdirectory", "");
    folderInput.setAttribute("directory", "");
  }, []);

  useEffect(() => {
    if (!isOpen) return;

    const handleOutsidePointerDown = (event: PointerEvent) => {
      const container = containerRef.current;

      if (!container?.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };

    document.addEventListener("pointerdown", handleOutsidePointerDown);

    return () => {
      document.removeEventListener("pointerdown", handleOutsidePointerDown);
    };
  }, [isOpen]);

  const openPicker = (mode: UploadMode) => {
    setError(null);
    setIsOpen(false);

    if (mode === "folder") {
      folderInputRef.current?.click();
      return;
    }

    fileInputRef.current?.click();
  };

  const handleFileSelection = (event: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = event.target.files?.[0];

    if (!selectedFile) return;

    const lowerCaseName = selectedFile.name.toLowerCase();
    const isJson = lowerCaseName.endsWith(".json");
    const isZip = lowerCaseName.endsWith(".zip");

    if (!isJson && !isZip) {
      setSelectionLabel(null);
      setError("Choose a .json or .zip file.");
      event.target.value = "";
      return;
    }

    setSelectionLabel(selectedFile.name);
    setError(null);
    void runPipeline({ file: selectedFile });
    event.target.value = "";
  };

  const handleFolderSelection = (event: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFiles = Array.from(event.target.files ?? []);

    if (selectedFiles.length === 0) return;

    const firstPath = selectedFiles[0].webkitRelativePath;
    const folderName = firstPath.split("/")[0] || "Selected folder";

    const conversationsFile = pickFolderFile(selectedFiles, "conversations.json");
    if (!conversationsFile) {
      setSelectionLabel(null);
      setError("No conversations.json found in the selected folder.");
      event.target.value = "";
      return;
    }

    setSelectionLabel(`${folderName} (${selectedFiles.length} files)`);
    setError(null);
    void runPipeline({
      file: conversationsFile,
      users: pickFolderFile(selectedFiles, "users.json"),
      memories: pickFolderFile(selectedFiles, "memories.json"),
    });
    event.target.value = "";
  };

  return (
    <div ref={containerRef} className="relative">
      <input
        ref={fileInputRef}
        type="file"
        accept={ACCEPTED_FILE_TYPES}
        className="hidden"
        onChange={handleFileSelection}
      />
      <input
        ref={folderInputRef}
        type="file"
        multiple
        className="hidden"
        onChange={handleFolderSelection}
      />

      <button
        type="button"
        onClick={() => setIsOpen((current) => !current)}
        className="rounded-full bg-accent px-[30px] py-4 text-[15px] font-semibold text-accent-foreground transition-opacity hover:opacity-90 cursor-pointer"
        aria-haspopup="menu"
        aria-expanded={isOpen}
      >
        Upload a conversation
      </button>

      {isOpen && (
        <div
          role="menu"
          className="absolute left-0 top-[calc(100%+10px)] z-10 w-[230px] overflow-hidden rounded-[12px] border border-hairline bg-surface text-[14px] font-medium text-ink shadow-[0_18px_50px_rgba(36,31,26,0.14)]"
        >
          <button
            type="button"
            role="menuitem"
            onClick={() => openPicker("json")}
            className="block w-full cursor-pointer px-4 py-3 text-left transition-colors hover:bg-background"
          >
            JSON file
          </button>
          <button
            type="button"
            role="menuitem"
            onClick={() => openPicker("zip")}
            className="block w-full cursor-pointer border-t border-hairline px-4 py-3 text-left transition-colors hover:bg-background"
          >
            ZIP archive
          </button>
          <button
            type="button"
            role="menuitem"
            onClick={() => openPicker("folder")}
            className="block w-full cursor-pointer border-t border-hairline px-4 py-3 text-left transition-colors hover:bg-background"
          >
            Folder
          </button>
        </div>
      )}

      {(status || selectionLabel || error) && (
        <p
          className={`mt-3 max-w-[280px] text-[13px] ${
            error ? "text-accent" : "text-muted"
          }`}
        >
          {error ?? status ?? `Selected: ${selectionLabel}`}
        </p>
      )}

      {reportId && !error && (
        <a
          href={`/${reportId}`}
          target="_blank"
          rel="noopener noreferrer"
          className="mt-2 inline-block text-[13px] font-semibold text-accent underline underline-offset-2"
        >
          Open report ↗
        </a>
      )}
    </div>
  );
}
