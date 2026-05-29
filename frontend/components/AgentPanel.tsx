type AgentPanelProps = {
  questions: string[];
  answer: string;
  disabled: boolean;
  onAnswerChange: (value: string) => void;
  onApplyAnswer: () => void;
};

export function AgentPanel({
  questions,
  answer,
  disabled,
  onAnswerChange,
  onApplyAnswer,
}: AgentPanelProps) {
  return (
    <section className="rounded-2xl border border-[#e5e7eb] bg-white p-6 shadow-sm">
      <div className="mb-4">
        <p className="text-sm font-semibold uppercase tracking-[0.18em] text-[#22c55e]">
          Agent clarification
        </p>
        <h2 className="mt-1 text-xl font-semibold text-[#111827]">One question at a time</h2>
        <p className="mt-2 text-sm leading-6 text-gray-600">
          The agent asks only for the next field needed to continue the deterministic check.
        </p>
      </div>

      <div className="space-y-3">
        {questions.length === 0 ? (
          <div className="rounded-xl border border-dashed border-[#e5e7eb] bg-[#f9fafb] p-4 text-sm text-gray-600">
            No question is needed yet. Run the workflow and the agent will ask only if a required
            detail is missing.
          </div>
        ) : (
          questions.map((question, index) => (
            <div key={`${question}-${index}`} className="fade-in rounded-2xl bg-green-50 p-4">
              <p className="text-sm font-medium text-green-900">{question}</p>
            </div>
          ))
        )}
      </div>

      <div className="mt-5">
        <label className="text-sm font-medium text-gray-700" htmlFor="agent-answer">
          Your answer
        </label>
        <div className="mt-2 flex flex-col gap-3 sm:flex-row">
          <input
            id="agent-answer"
            className="min-h-11 flex-1 rounded-lg border border-gray-300 bg-white px-3 py-2.5 text-sm text-[#111827] outline-none transition focus:border-[#22c55e] focus:ring-2 focus:ring-[#22c55e]/20 disabled:bg-gray-100"
            value={answer}
            disabled={disabled}
            placeholder="Example: yes, no, 2025-26"
            onChange={(event) => onAnswerChange(event.target.value)}
          />
          <button
            type="button"
            disabled={disabled || !answer.trim()}
            onClick={onApplyAnswer}
            className="cursor-pointer rounded-lg border border-gray-300 px-4 py-2.5 text-sm font-semibold text-gray-700 transition hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-gray-300 disabled:cursor-not-allowed disabled:opacity-70"
          >
            Apply and continue
          </button>
        </div>
      </div>
    </section>
  );
}
