export type DemoUserRole = "taxpayer" | "reviewer" | "admin" | "service";

export type DemoAuthContext = {
  userId: string;
  role: DemoUserRole;
  organizationId: string;
  label: string;
};

export const DEMO_USERS: DemoAuthContext[] = [
  {
    userId: "00000000-0000-4000-8000-000000000001",
    role: "taxpayer",
    organizationId: "00000000-0000-4000-8000-000000000101",
    label: "Demo Taxpayer",
  },
  {
    userId: "00000000-0000-4000-8000-000000000002",
    role: "reviewer",
    organizationId: "00000000-0000-4000-8000-000000000101",
    label: "Demo Reviewer",
  },
  {
    userId: "00000000-0000-4000-8000-000000000003",
    role: "admin",
    organizationId: "00000000-0000-4000-8000-000000000101",
    label: "Demo Admin",
  },
  {
    userId: "00000000-0000-4000-8000-000000000004",
    role: "reviewer",
    organizationId: "00000000-0000-4000-8000-000000000202",
    label: "Other Org Reviewer",
  },
];

const STORAGE_KEY = "itr-demo-auth-context";

export function isDemoAuthEnabled(): boolean {
  return process.env.NODE_ENV !== "production" || process.env.NEXT_PUBLIC_DEMO_AUTH_ENABLED === "true";
}

export function getDemoAuthContext(): DemoAuthContext {
  if (typeof window === "undefined") {
    return DEMO_USERS[0];
  }
  const stored = window.localStorage.getItem(STORAGE_KEY);
  const match = DEMO_USERS.find((user) => user.userId === stored);
  return match ?? DEMO_USERS[0];
}

export function setDemoAuthContext(userId: string): DemoAuthContext {
  const selected = DEMO_USERS.find((user) => user.userId === userId) ?? DEMO_USERS[0];
  if (typeof window !== "undefined") {
    window.localStorage.setItem(STORAGE_KEY, selected.userId);
  }
  return selected;
}

export function demoAuthHeaders(): Record<string, string> {
  if (!isDemoAuthEnabled()) {
    return {};
  }
  const context = getDemoAuthContext();
  return {
    "X-Demo-User-Id": context.userId,
    "X-Demo-User-Role": context.role,
    "X-Demo-Organization-Id": context.organizationId,
  };
}
