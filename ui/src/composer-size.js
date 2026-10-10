// Keep the CSS theme in charge of limits, including browser zoom and host themes.
export function resizeComposerTextarea(element, styles = (node) => getComputedStyle(node)) {
  if (!element) return;
  element.style.height = "auto";
  const maximum = Number.parseFloat(styles(element).maxHeight);
  const height = Number.isFinite(maximum) ? Math.min(element.scrollHeight, maximum) : element.scrollHeight;
  element.style.height = `${height}px`;
  element.style.overflowY = element.scrollHeight > height ? "auto" : "hidden";
}
