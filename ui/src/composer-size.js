// Keep the CSS theme in charge of limits, including browser zoom and host themes.
export function resizeComposerTextarea(element, styles = (node) => getComputedStyle(node)) {
  if (!element) return;
  element.style.height = "auto";
  const maximum = Number.parseFloat(styles(element).maxHeight);
  const contentHeight = element.scrollHeight;
  const height = Number.isFinite(maximum) ? Math.min(contentHeight, maximum) : contentHeight;
  element.style.height = `${height}px`;
  element.style.overflowY = contentHeight > height ? "auto" : "hidden";
}
