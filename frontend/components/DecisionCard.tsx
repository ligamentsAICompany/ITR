import type { ExplanationResponse, ITRDecisionResponse } from "@/types/itr";

type DecisionCardProps = {
  decision: ITRDecisionResponse | null;
  explanation: ExplanationResponse | null;
  missingFields: string[];
};

export function DecisionCard({ decision, explanation, missingFields }: DecisionCardProps) {
  if (!decision) {
    return (
      <section className="rounded-2xl border border-[#e5e7eb] bg-white p-6 shadow-sm">
        <p className="text-sm font-semibold uppercase tracking-[0.18em] text-[#22c55e]">
          Decision result
        </p>
        <p className="mt-3 text-sm leading-6 text-gray-600">
          Run the workflow to see candidate ITR, confidence, missing fields, and explanation.
        </p>
      </section>
    );
  }

  return (
    <section className="fade-in rounded-2xl border border-[#e5e7eb] border-l-4 border-l-[#22c55e] bg-white p-6 shadow-sm">
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-start">
        <div>
          <p className="text-sm font-semibold uppercase tracking-[0.18em] text-[#22c55e]">
            Candidate ITR
          </p>
          <h2 className="mt-2 text-5xl font-semibold tracking-tight text-[#22c55e]">
            {decision.candidate_itr || "Pending"}
          </h2>
        </div>
        <span className="w-fit rounded-full border border-[#e5e7eb] bg-[#f9fafb] px-3 py-1 text-sm font-semibold capitalize text-gray-700">
          {decision.confidence} confidence
        </span>
      </div>

      <div className="mt-6 space-y-4">
        <div>
          <h3 className="text-sm font-semibold text-[#111827]">Explanation</h3>
          <p className="mt-2 text-sm leading-6 text-gray-600">
            {explanation?.explanation ?? "Explanation will appear after missing fields are resolved."}
          </p>
        </div>

        <div>
          <h3 className="text-sm font-semibold text-[#111827]">Missing fields</h3>
          {missingFields.length > 0 ? (
            <div className="mt-2 flex flex-wrap gap-2">
              {missingFields.map((field) => (
                <span
                  key={field}
                  className="rounded-full border border-[#e5e7eb] bg-[#f9fafb] px-3 py-1 text-xs font-medium text-gray-700"
                >
                  {field}
                </span>
              ))}
            </div>
          ) : (
            <p className="mt-2 text-sm text-[#22c55e]">No missing fields reported.</p>
          )}
        </div>
      </div>
    </section>
  );
}
