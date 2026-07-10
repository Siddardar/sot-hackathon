// app/page.tsx
"use client";

import { useState } from "react";

export default function Home() {
  const [file, setFile] = useState<File | null>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (f) setFile(f);
  };

  const handleGenerate = () => {
    alert(file ? `Generating report for ${file.name}` : "Please upload a file first");
  };

  return (
    <main className="min-h-screen flex items-center justify-center p-4">
      <div className="bg-white p-8 rounded-2xl shadow-lg max-w-md w-full">
        <h1 className="text-3xl font-bold text-gray-800 mb-6 text-center">Sensitive Information Check</h1>

        <div className="flex flex-col gap-4">
          {/* Upload button */}
          <div>
            <label
              htmlFor="fileInput"
              className="inline-block w-full text-center px-4 py-2 bg-blue-600 text-white rounded-lg cursor-pointer hover:bg-blue-700 transition"
            >
              Upload JSON
            </label>
            <input
              id="fileInput"
              type="file"
              accept=".json"
              onChange={handleFileChange}
              className="hidden"
            />
            {file && (
              <p className="mt-1 text-sm text-gray-600">📄 {file.name}</p>
            )}
          </div>

          {/* Generate button */}
          <button
            onClick={handleGenerate}
            className="w-full px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition"
          >
            Generate Report
          </button>
        </div>
      </div>
    </main>
  );
}