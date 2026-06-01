export const DEFAULT_DEMO_BACKEND_INTERNAL_URL = "http://127.0.0.1:8000";

export function resolveBackendInternalUrl(value: string | undefined): string {
  const trimmed = value?.trim();
  return trimmed || DEFAULT_DEMO_BACKEND_INTERNAL_URL;
}
