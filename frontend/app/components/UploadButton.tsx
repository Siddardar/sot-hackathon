"use client";

import { useState } from "react";

import { UploadDialog } from "./UploadDialog";

export function UploadButton() {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <>
      <button
        type="button"
        onClick={() => setIsOpen(true)}
        className="rounded-full bg-accent px-[30px] py-4 text-[15px] font-semibold text-accent-foreground transition-opacity hover:opacity-90 cursor-pointer"
      >
        Find out now!
      </button>

      {isOpen && <UploadDialog onClose={() => setIsOpen(false)} />}
    </>
  );
}
