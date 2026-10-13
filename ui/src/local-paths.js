// Transform Markdown nodes, never source text: leave code blocks, math, images,
// web links and their labels intact. Relative paths have no unambiguous base.
const prefix = "#local-path=";

export function localPath(value) {
  if (typeof value !== "string" || /[\u0000-\u001f\u007f]/u.test(value)) return null;
  if (value.startsWith(prefix)) {
    try { return localPath(decodeURIComponent(value.slice(prefix.length))); }
    catch { return null; }
  }
  if (value.startsWith("file:")) {
    try {
      const url = new URL(value);
      if (url.hostname && url.hostname !== "localhost") return null;
      if (url.search || url.hash) return null;
      return localPath(decodeURIComponent(url.pathname));
    } catch { return null; }
  }
  return (value.startsWith("/") && !value.startsWith("//")) || value.startsWith("~/") ? value : null;
}

function link(path, children) {
  return { type: "link", url: prefix + encodeURIComponent(path), children };
}

export function remarkLocalPaths() {
  return function transform(tree) {
    function walk(node) {
      if (node.type === "link") {
        const path = localPath(node.url);
        if (path) node.url = prefix + encodeURIComponent(path);
        return;
      }
      if (["code", "math", "inlineMath", "image", "linkReference", "definition"].includes(node.type)) return;
      if (!node.children) return;
      node.children = node.children.flatMap((child) => {
        if (child.type === "inlineCode") {
          const path = localPath(child.value);
          return path ? [link(path, [child])] : [child];
        }
        if (child.type !== "text") { walk(child); return [child]; }
        const result = [];
        let end = 0;
        for (const match of child.value.matchAll(/(?:^|(?<=[\s([{]))(?:~\/|\/)[^\s<>"'`]+/gu)) {
          const path = match[0].replace(/[.,;:!?\])}]+$/u, "");
          if (!localPath(path)) continue;
          if (match.index > end) result.push({ type: "text", value: child.value.slice(end, match.index) });
          result.push(link(path, [{ type: "text", value: path }]));
          end = match.index + path.length;
        }
        if (end < child.value.length) result.push({ type: "text", value: child.value.slice(end) });
        return result.length ? result : [child];
      });
    }
    walk(tree);
  };
}
