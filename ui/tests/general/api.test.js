import test from "node:test";
import assert from "node:assert/strict";
import { api } from "../../src/api.js";
import { translate } from "../../src/locales.js";

for (const [label, status, body, message] of [
  ["structured error", 409, '{"error":{"message":"Build failed"}}', "Build failed"],
  ["string error", 503, '{"error":"Browser unavailable"}', "Browser unavailable"],
  ["validation details", 422, '{"detail":[{"msg":"invalid"}]}', translate("requestFailed", { status: 422 })],
  ["null error", 500, 'null', translate("requestFailed", { status: 500 })],
  ["HTML proxy error", 502, '<html>Bad gateway</html>', translate("requestFailed", { status: 502 })],
  ["malformed successful response", 200, '{', translate("invalidResponse")],
]) {
  test(label, async (t) => {
    t.mock.method(globalThis, "fetch", async () => new Response(body, { status }));
    await assert.rejects(api("test"), { message });
  });
}

test("empty responses and request contracts", async (t) => {
  let request;
  t.mock.method(globalThis, "fetch", async (url, options) => {
    request = { url, ...options };
    return new Response(null, { status: 204 });
  });
  const controller = new AbortController();
  assert.equal(await api("test", { method: "PUT", body: { enabled: false }, signal: controller.signal }), null);
  assert.equal(request.url, "/api/v1/test");
  assert.equal(request.credentials, "same-origin");
  assert.equal(request.signal, controller.signal);
  assert.equal(request.body, '{"enabled":false}');
});

test("multipart does not replace browser content type", async (t) => {
  const body = new FormData();
  body.append("prompt", "hello");
  t.mock.method(globalThis, "fetch", async (_url, options) => {
    assert.equal(options.body, body);
    assert.deepEqual(options.headers, {});
    return new Response('{"ok":true}');
  });
  assert.deepEqual(await api("test", { method: "POST", body }), { ok: true });
});


test("HTTP errors retain status and machine-readable code", async (t) => {
  t.mock.method(globalThis, "fetch", async () => new Response('{"error":{"code":"local_only","message":"Local only"}}', { status: 403 }));
  await assert.rejects(api("local-files/settings"), { message: "Local only", status: 403, code: "local_only" });
});
