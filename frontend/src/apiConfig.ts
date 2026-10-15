/** Dev API endpoints. Override via VITE_* env (see .env.development). */

function trimTrailingSlash(value: string) {
  return value.replace(/\/+$/, "");
}

function withPort(path: string, port: string) {
  const url = new URL(path, window.location.origin);
  url.port = port;
  return url.toString();
}

function withBase(path: string, base: string) {
  return new URL(path, `${trimTrailingSlash(base)}/`).toString();
}

/** Backend Django API (auth, app-data, documents, …). */
export function backendApiUrl(path: string) {
  const base = import.meta.env.VITE_BACKEND_BASE_URL?.trim();
  if (base) return withBase(path, base);

  const url = new URL(path, window.location.origin);
  if (import.meta.env.DEV) {
    url.port = String(import.meta.env.VITE_BACKEND_PORT || "18080");
  }
  return url.toString();
}

/** OCR FastAPI service. */
export function ocrServiceUrl(path: string) {
  const base = import.meta.env.VITE_OCR_BASE_URL?.trim();
  if (base) return withBase(path, base);

  if (!import.meta.env.DEV) {
    return new URL(path, window.location.origin).toString();
  }

  const port = String(import.meta.env.VITE_OCR_PORT || "18081");
  return withPort(path, port);
}
