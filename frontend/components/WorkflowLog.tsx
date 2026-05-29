type WorkflowLogProps = {
  logs: string[];
};

export function WorkflowLog({ logs }: WorkflowLogProps) {
  return (
    <section className="rounded-2xl border border-[#e5e7eb] bg-white p-6 shadow-sm">
      <p className="text-sm font-semibold uppercase tracking-[0.18em] text-[#22c55e]">
        Workflow log
      </p>
      <div className="mt-4 space-y-2">
        {logs.length === 0 ? (
          <p className="text-sm text-gray-600">No workflow steps yet.</p>
        ) : (
          logs.map((log, index) => (
            <div key={`${log}-${index}`} className="rounded-lg bg-[#f9fafb] px-3 py-2 text-xs text-gray-700">
              {log}
            </div>
          ))
        )}
      </div>
    </section>
  );
}
