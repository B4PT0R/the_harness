// Submit through the form so keyboard and button use the same send path.
export function handleComposerKeyDown(event, canSubmit) {
  if (event.key !== "Enter" || event.shiftKey || event.ctrlKey || event.altKey || event.metaKey
      || event.isComposing || event.nativeEvent?.isComposing || event.keyCode === 229) return;
  // Touch-first devices keep Return for multiline drafts; sending uses the button.
  if (event.currentTarget.ownerDocument?.defaultView?.matchMedia?.("(pointer: coarse)").matches) return;
  event.preventDefault();
  if (canSubmit && !event.repeat) event.currentTarget.form?.requestSubmit();
}
