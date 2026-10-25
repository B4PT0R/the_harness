import test from "node:test";
import assert from "node:assert/strict";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import { remarkLatexMath } from "../../src/latex-math.js";

const render = (source) => renderToStaticMarkup(React.createElement(ReactMarkdown, {
  remarkPlugins: [remarkGfm, remarkMath, remarkLatexMath],
  rehypePlugins: [[rehypeKatex, { strict: "ignore", trust: false }]],
  children: source,
}));
const count = (html, pattern) => (html.match(pattern) || []).length;

test("backslash and dollar delimiters coexist, inline and display", () => {
  const html = render(String.raw`En ligne \(x^2\), $y^2$ ; bloc \[z^2\].

$$
a^2
$$`);
  assert.equal(count(html, /class="katex"/g), 4);
  assert.equal(count(html, /class="katex-display"/g), 2);
  assert.doesNotMatch(html, /katex-error/);
});

test("multiline display preserves matrix row separators, blank lines and TeX punctuation", () => {
  const html = render(String.raw`Avant
\[
A=\begin{pmatrix}
1 & 2 \\

3 & 4
\end{pmatrix}
\]
Après`);
  assert.equal(count(html, /class="katex-display"/g), 1);
  assert.doesNotMatch(html, /katex-error/);
  assert.match(html, /\\begin\{pmatrix\}/);
  assert.match(html, /Avant/);
  assert.match(html, /Après/);
});

test("code spans, fenced and indented code keep their delimiters literally", () => {
  for (const source of [
    '`\\(x\\) \\[y\\]`',
    '``\\(x`y\\)``',
    '```latex\n\\[x\\]\n```',
    '~~~latex\n\\(x\\)\n~~~',
    '    \\[x\\]',
  ]) {
    const html = render(source);
    assert.doesNotMatch(html, /class="katex/);
    assert.match(html, /\\[([]/);
  }
});

test("escaped openers and incomplete or mismatched formulas stay ordinary Markdown", () => {
  for (const source of [String.raw`\\(x\\)`, String.raw`\\[x\\]`, String.raw`\(x`, String.raw`\[x\)`, String.raw`\(x\]`])
    assert.doesNotMatch(render(source), /class="katex/);
  assert.match(render(String.raw`\[x

**toujours du Markdown**`), /<strong>toujours du Markdown<\/strong>/);
});

test("math treats Markdown markers, dollars and backticks as raw TeX", () => {
  const html = render(String.raw`\(a_b * c + \text{\$5 et ` + '`' + String.raw`}\)`);
  assert.equal(count(html, /class="katex"/g), 1);
  assert.doesNotMatch(html, /katex-error|<em>|<code>/);
});

test("lists, blockquotes, tables, links and multiple formulas keep working", () => {
  for (const source of [
    String.raw`- \(x\) et \(y\)`,
    String.raw`> \[
> x^2
> \]`,
    '| valeur |\n| --- |\n| \\(x\\) |',
    String.raw`[\(x\)](https://example.org)`,
  ]) {
    const html = render(source);
    assert.match(html, /class="katex"/);
    assert.doesNotMatch(html, /katex-error/);
  }
});

test("invalid or unsafe TeX cannot break rendering or create trusted links", () => {
  assert.match(render(String.raw`\(\frac{\)`), /katex-error/);
  assert.doesNotMatch(render(String.raw`\(\href{javascript:alert(1)}{x}\)`), /href="javascript:/);
});


test("streamed prefixes never crash and complete formulas render, including CRLF", () => {
  const source = String.raw`Avant \[\begin{pmatrix}1 & 2 \\ 3 & 4\end{pmatrix}\] après \(x^2\).`;
  for (let end = 0; end <= source.length; end++) assert.doesNotThrow(() => render(source.slice(0, end)));
  const html = render("\\[\r\nx^2\r\n\\]  \r\n\r\nAprès");
  assert.equal(count(html, /class="katex-display"/g), 1);
  assert.match(html, /<p>Après<\/p>/);
});
