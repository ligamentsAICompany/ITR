import { useState } from "react";
import { extractDocument, uploadDocument } from "@/lib/api";
import type { DocumentRecord, DocumentType, ExtractionResult } from "@/types/itr";

type DocumentUploadCenterProps = {
  disabled: boolean;
  onExtracted: (document: DocumentRecord, extraction: ExtractionResult) => void;
  onLog: (message: string) => void;
  onError: (message: string) => void;
};

export function DocumentUploadCenter({ disabled, onExtracted, onLog, onError }: DocumentUploadCenterProps) {
  const [file, setFile] = useState<File | null>(null);
  const [documentType, setDocumentType] = useState<DocumentType>("form16");
  const [busy, setBusy] = useState(false);

  async function uploadAndExtract() {
    if (!file) {
      onError("Choose a CSV, Excel, text PDF, or TXT document first.");
      return;
    }

    setBusy(true);
    onError("");
    try {
      onLog("upload: POST /v1/uploads");
      const document = await uploadDocument(file, documentType);
      onLog("extract: POST /v1/uploads/{document_id}/extract");
      const extraction = await extractDocument(document.document_id);
      onExtracted(document, extraction);
    } catch (caughtError) {
      onError(caughtError instanceof Error ? caughtError.message : "Document extraction failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="rounded-2xl border border-[#d1fae5] bg-white p-6 shadow-sm">
      <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
        <div>
          <p className="text-sm font-semibold uppercase tracking-[0.18em] text-[#059669]">
            Document upload
          </p>
          <h2 className="mt-1 text-2xl font-semibold text-[#111827]">Upload center</h2>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-gray-600">
            Upload Form 16, AIS, bank CSV/Excel, or text-based PDFs. Extracted values stay in review until you accept them.
          </p>
        </div>
      </div>

      <div className="mt-5 grid gap-4 md:grid-cols-[1fr_220px_auto] md:items-end">
        <label className="block">
          <span className="text-sm font-medium text-gray-700">Document file</span>
          <input
            className="mt-2 w-full rounded-lg border border-gray-300 bg-white px-3 py-2.5 text-sm text-[#111827]"
            type="file"
            accept=".csv,.xls,.xlsx,.pdf,.txt"
            disabled={disabled || busy}
            onChange={(event) => setFile(event.target.files?.[0] ?? null)}
          />
        </label>
        <label className="block">
          <span className="text-sm font-medium text-gray-700">Document type</span>
          <select
            className="mt-2 w-full rounded-lg border border-gray-300 bg-white px-3 py-2.5 text-sm text-[#111827]"
            value={documentType}
            disabled={disabled || busy}
            onChange={(event) => setDocumentType(event.target.value as DocumentType)}
          >
            <option value="form16">Form 16</option>
            <option value="ais">AIS</option>
            <option value="bank_statement">Bank statement</option>
            <option value="pdf_text">Text PDF</option>
            <option value="other">Other</option>
          </select>
        </label>
        <button
          type="button"
          disabled={disabled || busy}
          onClick={() => void uploadAndExtract()}
          className="rounded-lg bg-[#111827] px-5 py-3 text-sm font-semibold text-white transition hover:bg-black disabled:cursor-not-allowed disabled:opacity-60"
        >
          {busy ? "Extracting..." : "Upload & extract"}
        </button>
      </div>
    </section>
  );
}
