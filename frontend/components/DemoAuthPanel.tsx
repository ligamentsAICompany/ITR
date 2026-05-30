"use client";

import { useState } from "react";
import { DEMO_USERS, getDemoAuthContext, isDemoAuthEnabled, setDemoAuthContext } from "../lib/auth";
import type { DemoAuthContext } from "../lib/auth";

export function DemoAuthPanel() {
  const [context, setContext] = useState<DemoAuthContext>(() => getDemoAuthContext());

  if (!isDemoAuthEnabled()) {
    return (
      <section className="rounded-2xl border border-[#e5e7eb] bg-white p-4 text-sm text-gray-700 shadow-sm">
        Production authentication is required. Demo identity controls are disabled.
      </section>
    );
  }

  return (
    <section className="rounded-2xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-950 shadow-sm">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="font-semibold">Demo auth context</p>
          <p className="mt-1">
            Role: <span className="font-semibold">{context.role}</span> · Org:{" "}
            <span className="font-semibold">{context.organizationId.slice(-12)}</span>
          </p>
        </div>
        <label className="flex flex-col gap-1 text-xs font-semibold uppercase tracking-[0.14em] text-emerald-900">
          Demo user
          <select
            className="rounded-xl border border-emerald-300 bg-white px-3 py-2 text-sm font-medium normal-case tracking-normal text-emerald-950"
            value={context.userId}
            onChange={(event) => setContext(setDemoAuthContext(event.target.value))}
          >
            {DEMO_USERS.map((user) => (
              <option key={user.userId} value={user.userId}>
                {user.label} ({user.role})
              </option>
            ))}
          </select>
        </label>
      </div>
    </section>
  );
}
