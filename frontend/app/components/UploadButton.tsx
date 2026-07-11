"use client";

import { useEffect, useRef, useState } from "react";

type UploadMode = "json" | "zip" | "folder";

const ACCEPTED_FILE_TYPES = ".json,application/json,.zip,application/zip,application/x-zip-compressed";

export function UploadButton() {
  const containerRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const folderInputRef = useRef<HTMLInputElement>(null);
  const [isOpen, setIsOpen] = useState(false);
  const [selectionLabel, setSelectionLabel] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

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
  };

  const handleFolderSelection = (event: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFiles = Array.from(event.target.files ?? []);

    if (selectedFiles.length === 0) return;

    const firstPath = selectedFiles[0].webkitRelativePath;
    const folderName = firstPath.split("/")[0] || "Selected folder";

    setSelectionLabel(`${folderName} (${selectedFiles.length} files)`);
    setError(null);
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

      {(selectionLabel || error) && (
        <p
          className={`mt-3 max-w-[260px] text-[13px] ${
            error ? "text-accent" : "text-muted"
          }`}
        >
          {error ?? `Selected: ${selectionLabel}`}
        </p>
      )}
    </div>
  );
}
