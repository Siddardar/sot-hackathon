// app/page.tsx
"use client";

import { useState } from "react";

export default function Home() {
  // Holds the JSON file the user picked
  const [file, setFile] = useState<File | null>(null);

  // Must be true before the user can upload or generate anything
  const [agreed, setAgreed] = useState(false);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (f) setFile(f);
  };

  const handleGenerate = () => {
    alert(file ? `Generating report for ${file.name}` : "Please upload a file first");
  };

  return (
    <main className="min-h-screen bg-slate-50 flex flex-col items-center px-4 py-12">
      <div className="w-full max-w-md">
        {/* Header */}
        <div className="text-center mb-8">
          <h1 className="text-2xl font-semibold text-slate-900">
            Sensitive Information Check
          </h1>
          <p className="mt-2 text-sm text-slate-500">
            Upload a JSON file to scan for sensitive information
          </p>
        </div>

        {/* Main card */}
        <div className="bg-white border border-slate-200 rounded-xl shadow-sm p-6 sm:p-8">
          {/* Disclaimer */}
          <div className="mb-6">
            <h2 className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-3">
              Before you continue
            </h2>
            <ul className="mx-auto max-w-2xl space-y-2 text-sm text-slate-600 list-disc text-left mb-4 pl-6">
              <li>Only upload conversation files that you want analyzed.</li>
              <li>Please be aware that the file you upload may contain personal or sensitive information.</li>
              <li>We analyze only the file you choose to upload and do not access any other data on your device.</li>
              <li>Results are automated and may not be fully accurate.</li>
            </ul>

            <label className="flex items-start gap-3 text-sm text-slate-700 cursor-pointer select-none">
              <input
                type="checkbox"
                checked={agreed}
                onChange={(e) => setAgreed(e.target.checked)}
                className="mt-0.5 h-4 w-4 rounded border-slate-300 text-blue-600 focus:ring-blue-500"
              />
              <span>
                I understand and agree to the conditions above.
              </span>
            </label>
          </div>

          {/* Upload + generate */}
          <div className="flex flex-col gap-3 pt-2 border-t border-slate-100">
            <div className="pt-4">
              <label
                htmlFor="fileInput"
                className={`inline-block w-full text-center px-4 py-2 rounded-lg font-medium transition ${
                  agreed
                    ? "bg-blue-600 text-white cursor-pointer hover:bg-blue-700"
                    : "bg-slate-100 text-slate-400 cursor-not-allowed"
                }`}
              >
                Upload JSON
              </label>
              <input
                id="fileInput"
                type="file"
                accept=".json"
                onChange={handleFileChange}
                disabled={!agreed}
                className="hidden"
              />
              {file && (
                <p className="mt-2 text-sm text-slate-500">📄 {file.name}</p>
              )}
            </div>

            <button
              onClick={handleGenerate}
              disabled={!agreed}
              className={`w-full px-4 py-2 rounded-lg font-medium transition ${
                agreed
                  ? "bg-green-600 text-white hover:bg-green-700"
                  : "bg-slate-100 text-slate-400 cursor-not-allowed"
              }`}
            >
              Generate Report
            </button>
          </div>
        </div>

        {/* Steps */}
        <h3 className="mt-10 text-center text-xs font-semibold text-slate-500 uppercase tracking-wide">
          Follow these steps
        </h3>
        <div className="mt-4 grid grid-cols-3 gap-4 text-center">
          <div>
            <div className="text-sm font-semibold text-blue-600">1</div>
            <p className="mt-1 text-xs text-slate-500">Agree to the conditions</p>
          </div>
          <div>
            <div className="text-sm font-semibold text-blue-600">2</div>
            <p className="mt-1 text-xs text-slate-500">Upload your JSON file</p>
          </div>
          <div>
            <div className="text-sm font-semibold text-blue-600">3</div>
            <p className="mt-1 text-xs text-slate-500">Generate your report</p>
          </div>
        </div>
      </div>
    </main>
  );
}
