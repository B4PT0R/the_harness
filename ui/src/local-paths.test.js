import test from "node:test";
import assert from "node:assert/strict";
import { localPath, remarkLocalPaths } from "./local-paths.js";

const transform = (children) => {
  const tree = { type: "root", children: [{ type: "paragraph", children }] };
  remarkLocalPaths()(tree);
  return tree.children[0].children;
};

test("local paths and file URLs are decoded, never remote shares or unsafe schemes", () => {
  for (const value of ["/home/a b/report.md", "~/Documents", "/tmp/image.png"])
    assert.equal(localPath(value), value);
  assert.equal(localPath("file:///tmp/a%20b.md"), "/tmp/a b.md");
  assert.equal(localPath("#local-path=%2Ftmp%2Freport.md"), "/tmp/report.md");
  for (const value of ["file://remote/a.txt", "file:///tmp/a?command=x", "//remote/a", "file:///%00.txt", "#local-path=%XX", "javascript:alert(1)", "https://example.org/a.txt", "docs/readme.md", "/tmp/a\n.txt"])
    assert.equal(localPath(value), null, value);
});

test("bare paths are clickable without swallowing surrounding text and punctuation", () => {
  const nodes = transform([{ type: "text", value: "Fichier /tmp/a.md, dossier ~/Documents et (/tmp/image.png)." }]);
  assert.deepEqual(nodes.filter((node) => node.type === "link").map((node) => localPath(node.url)), ["/tmp/a.md", "~/Documents", "/tmp/image.png"]);
  assert.equal(nodes.map((node) => node.value || node.children[0].value).join(""), "Fichier /tmp/a.md, dossier ~/Documents et (/tmp/image.png).");
});

test("inline paths with spaces are preserved and explicit local links are normalized", () => {
  const nodes = transform([
    { type: "inlineCode", value: "/tmp/a b.md" },
    { type: "link", url: "file:///tmp/c%20d.md", children: [{ type: "text", value: "rapport" }] },
  ]);
  assert.equal(localPath(nodes[0].url), "/tmp/a b.md");
  assert.equal(nodes[0].children[0].type, "inlineCode");
  assert.equal(localPath(nodes[1].url), "/tmp/c d.md");
});

test("code blocks, commands, math, web links and reference labels are untouched", () => {
  const nodes = [
    { type: "code", value: "/tmp/a.md" },
    { type: "inlineCode", value: "cat /tmp/a.md" },
    { type: "inlineMath", value: "/tmp/a.md" },
    { type: "link", url: "https://example.org", children: [{ type: "text", value: "/tmp/a.md" }] },
    { type: "linkReference", identifier: "site", children: [{ type: "text", value: "/tmp/a.md" }] },
  ];
  const original = structuredClone(nodes);
  assert.deepEqual(transform(nodes), original);
});
