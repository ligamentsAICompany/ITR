import { useMemo, useState } from "react";
import type { DocumentRecord, ExtractionResult } from "@/types/itr";

type ExtractionReviewPanelProps = {
  document: DocumentRecord | null;
  extraction: ExtractionResult | null;
  disabled: boolean;
  onAccept: (fieldIds: string[], reviewedExtraction: ExtractionResult) => void;
};

type ExtractionReviewPanelContentProps = {
  document: DocumentRecord;
  extraction: ExtractionResult;
  disabled: boolean;
  onAccept: (fieldIds: string[], reviewedExtraction: ExtractionResult) => void;
};

export function ExtractionReviewPanel({ document, extraction, disabled, onAccept }: ExtractionReviewPanelProps) {
  if (!document || !extraction) {
    return null;
  }

  return (
    <ExtractionReviewPanelContent
      key={extraction.document_id}
      document={document}
      extraction={extraction}
      disabled={disabled}
      onAccept={onAccept}
    />
  );
}

function ExtractionReviewPanelContent({ document, extraction, disabled, onAccept }: ExtractionReviewPanelContentProps) {
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [fieldValues, setFieldValues] = useState<Record<string, string>>(() =>
    Object.fromEntries(extraction.fields.map((field) => [field.field_id, String(field.value)])),
  );
  const selected = useMemo(() => new Set(selectedIds), [selectedIds]);

  const reviewedExtraction: ExtractionResult = {
    ...extraction,
    fields: extraction.fields.map((field) => ({
      ...field,
      value: fieldValues[field.field_id] ?? field.value,
    })),
  };

  function toggle(fieldId: string) {
    setSelectedIds((current) =>
      current.includes(fieldId) ? current.filter((id) => id !== fieldId) : [...current, fieldId],
    );
  }

  return (
    <section className="rounded-2xl border border-[#bfdbfe] bg-white p-6 shadow-sm">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="text-sm font-semibold uppercase tracking-[0.18em] text-[#2563eb]">
            Extraction review
          </p>
          <h2 className="mt-1 text-2xl font-semibold text-[#111827]">{document.original_filename}</h2>
          <p className="mt-2 text-sm leading-6 text-gray-600">
            Review each extracted value. Only checked fields are merged into the intake form.
          </p>
        </div>
        <span className="rounded-full bg-[#eff6ff] px-3 py-1 text-xs font-semibold uppercase tracking-wide text-[#1d4ed8]">
          {extraction.status}
        </span>
      </div>

      {extraction.warnings?.length ? (
        <div className="mt-4 rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
          {extraction.warnings.join(" ")}
        </div>
      ) : null}

      <div className="mt-5 space-y-3">
        {extraction.fields.length === 0 ? (
          <p className="rounded-xl border border-gray-200 bg-gray-50 p-4 text-sm text-gray-600">
            No conservative v1 mappings were found in this document.
          </p>
        ) : (
          extraction.fields.map((field) => (
            <label
              key={field.field_id}
              className="flex cursor-pointer gap-3 rounded-xl border border-gray-200 p-4 transition hover:border-[#93c5fd]"
            >
              <input
                type="checkbox"
                className="mt-1 h-4 w-4"
                checked={selected.has(field.field_id)}
                disabled={disabled}
                onChange={() => toggle(field.field_id)}
              />
              <span className="flex-1">
                <span className="block text-sm font-semibold text-[#111827]">{field.label}</span>
                <input
                  aria-label={`Edit ${field.label}`}
                  className="mt-2 w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-700"
                  disabled={disabled}
                  value={fieldValues[field.field_id] ?? String(field.value)}
                  onChange={(event) =>
                    setFieldValues((current) => ({ ...current, [field.field_id]: event.target.value }))
                  }
                />
                <span className="mt-1 block text-xs text-gray-500">
                  {field.raw_path} {"->"} {field.canonical_path} | confidence {Math.round(field.confidence * 100)}%
                </span>
              </span>
            </label>
          ))
        )}
      </div>

      <button
        type="button"
        disabled={disabled || selectedIds.length === 0}
        onClick={() => onAccept(selectedIds, reviewedExtraction)}
        className="mt-5 rounded-lg bg-[#2563eb] px-5 py-3 text-sm font-semibold text-white transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-60"
      >
        Accept selected values
      </button>
    </section>
  );
}
