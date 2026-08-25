export function buttonInteractionState(disabled = false, loading = false) {
  return {
    disabled: disabled || loading,
    busy: loading,
    showSpinner: loading,
  };
}
