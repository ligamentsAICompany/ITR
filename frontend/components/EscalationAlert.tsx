type EscalationAlertProps = {
  show: boolean;
};

export function EscalationAlert({ show }: EscalationAlertProps) {
  if (!show) {
    return null;
  }

  return (
    <section className="fade-in rounded-2xl border border-red-300 bg-red-50 p-5">
      <div className="flex gap-3">
        <svg
          aria-hidden="true"
          className="mt-0.5 h-5 w-5 flex-none text-red-600"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          viewBox="0 0 24 24"
        >
          <path d="M12 9v4m0 4h.01" />
          <path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0Z" />
        </svg>
        <div>
          <h2 className="text-sm font-semibold text-red-900">This case requires expert review</h2>
          <p className="mt-1 text-sm leading-6 text-red-800">
            The platform will preserve deterministic results and escalate the unresolved case to a
            reviewer instead of guessing.
          </p>
        </div>
      </div>
    </section>
  );
}
