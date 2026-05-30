export function Navbar() {
  const showPilotBanner = process.env.NEXT_PUBLIC_SHOW_PILOT_STATUS_BANNER !== "false";

  return (
    <header className="sticky top-0 z-20 border-b border-[#e5e7eb] bg-white/95 backdrop-blur">
      {showPilotBanner ? (
        <div className="border-b border-amber-200 bg-amber-50 px-4 py-2 text-center text-xs font-medium text-amber-900 sm:text-sm">
          Pilot mode: This platform prepares and validates tax filing data. Live government filing is disabled.
        </div>
      ) : null}
      <nav className="mx-auto flex max-w-[900px] items-center justify-between px-5 py-4">
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-[#22c55e]">
            <svg
              aria-hidden="true"
              className="h-5 w-5 text-white"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              viewBox="0 0 24 24"
            >
              <path d="M6 3h8l4 4v14H6z" />
              <path d="M14 3v5h5" />
              <path d="M9 13h6M9 17h4" />
            </svg>
          </div>
          <div>
            <p className="text-sm font-semibold uppercase tracking-[0.18em] text-[#22c55e]">
              Enterprise ITR
            </p>
            <h1 className="text-lg font-semibold text-[#111827]">ITR AI System</h1>
          </div>
        </div>
        <div className="hidden items-center gap-3 sm:flex">
          <span className="rounded-full border border-[#e5e7eb] bg-[#f9fafb] px-3 py-1 text-sm font-medium text-gray-700">
            Deterministic engine online
          </span>
          <span className="h-2.5 w-2.5 rounded-full bg-[#22c55e]" />
        </div>
      </nav>
    </header>
  );
}
