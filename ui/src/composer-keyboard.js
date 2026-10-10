// Submit through the form so keyboard and button use the same send path.
export function handleComposerKeyDown(event, canSubmit) {
  if (event.key !== "Enter" || event.shiftKey || event.ctrlKey || event.altKey || event.metaKey
      || event.isComposing || event.nativeEvent?.isComposing || event.keyCode === 229) return;
  event.preventDefault();
  if (canSubmit && !event.repeat) event.currentTarget.form?.requestSubmit();
}
