import { clientInstance } from "./client-output.js";
import { translate } from "./locales.js";
export async function api(path, { method = "GET", body, signal } = {}) {
  const multipart = body instanceof FormData;
  const response = await fetch(`/api/v1/${path}`, {
    method,
    signal,
    credentials: "same-origin",
    headers:
      body === undefined || multipart
        ? { "X-Client-Instance": clientInstance() }
        : { "Content-Type": "application/json", "X-Client-Instance": clientInstance() },
    body: multipart
      ? body
      : body === undefined
        ? undefined
        : JSON.stringify(body),
  });
  const text = response.status === 204 ? "" : await response.text();
  let payload;
  try { payload = text ? JSON.parse(text) : null; }
  catch {
    throw new Error(translate(response.ok ? "invalidResponse" : "requestFailed", { status: response.status }));
  }
  if (!response.ok) {
    const message = payload?.error?.message || payload?.error || payload?.detail;
    throw Object.assign(new Error(typeof message === "string" ? message : translate("requestFailed", { status: response.status })),
      { status: response.status, code: payload?.error?.code });
  }
  return payload;
}
