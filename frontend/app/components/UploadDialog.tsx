"use client";

import { useEffect, useRef, useState } from "react";

import { analyze, parseExport, type AnalysisMode, type ExportFiles } from "../lib/api";
import { newReportId, saveReport } from "../lib/reportStore";

const ACCEPTED_FILE_TYPES = ".json,application/json,.zip,application/zip,application/x-zip-compressed";
const PENDING_REPORT_KEY = "glasshouse:pending-report-id";

interface UploadDialogProps {
  onClose: () => void;
}

interface ModeOption {
  value: AnalysisMode;
  label: string;
  description: string;
}

const MODE_OPTIONS: ModeOption[] = [
  {
    value: "conservative",
    label: "Conservative",
    description: "Surfaces clear, better-supported inferences only.",
  },
  {
    value: "speculative",
    label: "Speculative",
    description: "Includes weaker signals, writing style, vibes, and broader hypotheses.",
  },
];

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

function isAcceptedFile(file: File): boolean {
  const name = file.name.toLowerCase();
  return name.endsWith(".json") || name.endsWith(".zip");
}

export function UploadDialog({ onClose }: UploadDialogProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const folderInputRef = useRef<HTMLInputElement>(null);
  const pendingReportWindowRef = useRef<Window | null>(null);
  const [analysisMode, setAnalysisMode] = useState<AnalysisMode>("conservative");
  const [selectedParts, setSelectedParts] = useState<ExportFiles | null>(null);
  const [selectionLabel, setSelectionLabel] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [reportId, setReportId] = useState<string | null>(null);
  const [isRunning, setIsRunning] = useState(false);
  const [isDragging, setIsDragging] = useState(false);

  useEffect(() => {
    const folderInput = folderInputRef.current;
    if (!folderInput) return;
    folderInput.setAttribute("webkitdirectory", "");
    folderInput.setAttribute("directory", "");
  }, []);

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape" && !isRunning) onClose();
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [isRunning, onClose]);

  const selectFile = (file: File) => {
    if (!isAcceptedFile(file)) {
      setSelectedParts(null);
      setSelectionLabel(null);
      setReportId(null);
      setStatus(null);
      setError("Choose a .json or .zip export.");
      return;
    }
    setSelectedParts({ file });
    setSelectionLabel(file.name);
    setError(null);
    setStatus(null);
    setReportId(null);
  };

  const selectFolderFiles = (files: File[]) => {
    const conversationsFile = pickFolderFile(files, "conversations.json");
    if (!conversationsFile) {
      setSelectedParts(null);
      setSelectionLabel(null);
      setReportId(null);
      setStatus(null);
      setError("No conversations.json found in the selected folder.");
      return;
    }

    const firstPath = files[0]?.webkitRelativePath;
    const folderName = firstPath?.split("/")[0] || "Selected folder";
    setSelectedParts({
      file: conversationsFile,
      users: pickFolderFile(files, "users.json"),
      memories: pickFolderFile(files, "memories.json"),
    });
    setSelectionLabel(`${folderName} (${files.length} files)`);
    setError(null);
    setStatus(null);
    setReportId(null);
  };

  const selectMode = (mode: AnalysisMode) => {
    if (mode === analysisMode) return;
    setAnalysisMode(mode);
    setReportId(null);
    setStatus(null);
    setError(null);
  };

  const handleFileSelection = (event: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = event.target.files?.[0];
    if (selectedFile) selectFile(selectedFile);
    event.target.value = "";
  };

  const handleFolderSelection = (event: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFiles = Array.from(event.target.files ?? []);
    if (selectedFiles.length > 0) selectFolderFiles(selectedFiles);
    event.target.value = "";
  };

  const handleDrop = (event: React.DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setIsDragging(false);
    const droppedFiles = Array.from(event.dataTransfer.files ?? []);
    if (droppedFiles.length === 0) return;

    const conversationsFile = pickFolderFile(droppedFiles, "conversations.json");
    if (conversationsFile) {
      selectFolderFiles(droppedFiles);
      return;
    }
    selectFile(droppedFiles[0]);
  };

  const runPipeline = async () => {
    if (!selectedParts) {
      setError("Choose an export first.");
      return;
    }

    setError(null);
    setReportId(null);
    setIsRunning(true);
    localStorage.removeItem(PENDING_REPORT_KEY);
    pendingReportWindowRef.current = window.open("/generating-report", "_blank");
    try {
      setStatus("Uploading and parsing...");
      const parsed = await parseExport(selectedParts);
      console.log("[Glasshouse] /parse response:", parsed);

      const allMessages = parsed.conversations.flatMap((c) => c.messages);
      if (allMessages.length === 0) {
        setStatus(null);
        setError("No messages were found to analyze.");
        return;
      }

      setStatus(
        `Analyzing ${parsed.conversations.length} conversations (${allMessages.length} messages) in ${analysisMode} mode...`,
      );

      const inferences = await analyze(
        allMessages,
        {
          onMeta: (meta) =>
            console.log("[Glasshouse] meta:", meta, "tier_counts:", meta.tier_counts),
          onInference: (inf) =>
            console.log(
              `[Glasshouse] finding [${inf.tier}] ${inf.category_id} (${inf.subject ?? "self"}):`,
              inf,
            ),
          onError: (message) => console.error("[Glasshouse] analyze error:", message),
          onDone: (data) => console.log("[Glasshouse] done:", data),
        },
        { mode: analysisMode },
      );

      const id = newReportId();
      const saved = saveReport({
        id,
        createdAt: Date.now(),
        source: parsed.format,
        mode: analysisMode,
        parsed,
        findings: inferences,
      });

      setReportId(id);
      setStatus(
        saved
          ? `Done - ${inferences.length} findings.`
          : `Done - ${inferences.length} findings (couldn't save locally; use the link below now).`,
      );
      const reportUrl = `/${id}`;
      localStorage.setItem(PENDING_REPORT_KEY, id);
      if (pendingReportWindowRef.current && !pendingReportWindowRef.current.closed) {
        pendingReportWindowRef.current.location.href = reportUrl;
      } else {
        window.open(reportUrl, "_blank");
      }
      pendingReportWindowRef.current = null;
    } catch (err) {
      console.error("[Glasshouse] pipeline error:", err);
      if (pendingReportWindowRef.current && !pendingReportWindowRef.current.closed) {
        pendingReportWindowRef.current.close();
      }
      pendingReportWindowRef.current = null;
      setStatus(null);
      setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setIsRunning(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-ink/20 px-4 py-8 backdrop-blur-[2px]"
      role="dialog"
      aria-modal="true"
      aria-labelledby="upload-dialog-title"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget && !isRunning) onClose();
      }}
    >
      <div className="max-h-[calc(100vh-32px)] w-full max-w-[680px] overflow-y-auto rounded-[8px] bg-background p-5 shadow-[0_34px_100px_rgba(36,31,26,0.26)] sm:p-7">
        <div className="mb-5 flex items-start justify-between gap-5">
          <div>
            <h2
              id="upload-dialog-title"
              className="font-serif text-[28px] font-semibold leading-tight text-ink sm:text-[32px]"
            >
              Upload a conversation
            </h2>
            <p className="mt-1.5 text-[14px] leading-[1.4] text-muted sm:text-[15px]">
              Runs in your browser first. Selected messages go to your backend only to generate this report.
            </p>
          </div>
          <button
            type="button"
            disabled={isRunning}
            onClick={onClose}
            className="grid h-10 w-10 flex-none place-items-center rounded-full border border-hairline text-[26px] leading-none text-muted transition-colors hover:border-accent hover:text-accent disabled:cursor-not-allowed disabled:opacity-50 cursor-pointer"
            aria-label="Close upload dialog"
          >
            ×
          </button>
        </div>

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

        <div
          role="button"
          tabIndex={isRunning ? -1 : 0}
          onClick={() => fileInputRef.current?.click()}
          onKeyDown={(event) => {
            if (event.key === "Enter" || event.key === " ") {
              event.preventDefault();
              fileInputRef.current?.click();
            }
          }}
          onDragEnter={(event) => {
            event.preventDefault();
            setIsDragging(true);
          }}
          onDragOver={(event) => event.preventDefault()}
          onDragLeave={() => setIsDragging(false)}
          onDrop={handleDrop}
          className={`mb-5 flex min-h-[150px] w-full flex-col items-center justify-center rounded-[18px] border-2 border-dashed bg-surface px-5 text-center transition-colors ${
            isDragging ? "border-accent bg-[#fff8f0]" : "border-[#d8c8b4]"
          } ${isRunning ? "cursor-not-allowed opacity-70" : "cursor-pointer hover:border-accent"}`}
        >
          <span className="mb-3 grid h-11 w-11 place-items-center rounded-[12px] bg-[#f1e5d8] text-accent">
            <span className="block h-3.5 w-3.5 rotate-45 border-l-[3px] border-t-[3px] border-current" />
          </span>
          <span className="text-[18px] font-bold text-ink">
            {selectionLabel ?? "No file selected"}
          </span>
          <span className="mt-2 text-[14px] leading-[1.4] text-muted sm:text-[15px]">
            .json or .zip export, or click to browse
          </span>
        </div>
        <button
          type="button"
          disabled={isRunning}
          onClick={() => folderInputRef.current?.click()}
          className="mb-5 -mt-2 text-[12px] font-semibold text-accent underline underline-offset-2 disabled:cursor-not-allowed disabled:opacity-60 cursor-pointer"
        >
          Choose an export folder instead
        </button>

        <div className="mb-3 font-sans text-[12px] font-bold uppercase tracking-[0.1em] text-accent">
          Mode
        </div>
        <div className="space-y-3">
          {MODE_OPTIONS.map((option) => {
            const active = analysisMode === option.value;
            return (
              <button
                key={option.value}
                type="button"
                disabled={isRunning}
                onClick={() => selectMode(option.value)}
                className={`flex w-full items-center gap-4 rounded-[14px] border-2 bg-surface px-5 py-4 text-left transition-colors ${
                  active ? "border-accent bg-[#fff3eb]" : "border-hairline hover:border-[#d8c8b4]"
                } ${isRunning ? "cursor-not-allowed opacity-70" : "cursor-pointer"}`}
              >
                <span
                  className={`h-7 w-7 flex-none rounded-full border-2 ${
                    active ? "border-accent bg-accent" : "border-accent bg-transparent"
                  }`}
                  aria-hidden="true"
                />
                <span>
                  <span className="block text-[17px] font-bold leading-tight text-ink">
                    {option.label}
                  </span>
                  <span className="mt-0.5 block text-[14px] leading-[1.3] text-secondary">
                    {option.description}
                  </span>
                </span>
              </button>
            );
          })}
        </div>

        {(status || error) && (
          <p className={`mt-4 text-[13px] leading-[1.4] ${error ? "text-accent" : "text-muted"}`}>
            {error ?? status}
          </p>
        )}

        {reportId && !error ? (
          <a
            href={`/${reportId}`}
            className="mt-5 block w-full rounded-full bg-accent px-8 py-4 text-center text-[16px] font-bold text-accent-foreground transition-opacity hover:opacity-90 cursor-pointer"
          >
            Show report
          </a>
        ) : (
          <button
            type="button"
            disabled={isRunning}
            onClick={() => void runPipeline()}
            className="mt-5 w-full rounded-full bg-accent px-8 py-4 text-[16px] font-bold text-accent-foreground transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60 cursor-pointer"
          >
            {isRunning ? "Generating report..." : "Generate report"}
          </button>
        )}
      </div>
    </div>
  );
}
