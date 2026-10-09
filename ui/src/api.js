import { translate } from "./locales.js";
export async function api(path, { method = "GET", body, signal } = {}) {
  const multipart = body instanceof FormData;
  const response = await fetch(`/api/v1/${path}`, {
    method,
    signal,
    credentials: "same-origin",
    headers:
      body === undefined || multipart
        ? {}
        : { "Content-Type": "application/json" },
    body: multipart
      ? body
      : body === undefined
        ? undefined
        : JSON.stringify(body),
  });
  const payload = response.status === 204 ? null : await response.json();
  if (!response.ok)
    throw new Error(
      payload.error?.message ||
        (typeof payload.error === "string" ? payload.error : "") ||
        payload.detail ||
        translate("requestFailed", { status: response.status }),
    );
  return payload;
}
