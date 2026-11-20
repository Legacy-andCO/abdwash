let invalidation: (() => void) | undefined;
export function subscribeSessionRejected(callback: () => void) {
  invalidation = callback;
  return () => { invalidation = undefined; };
}
export function notifySessionRejected() { invalidation?.(); }

let listener: (() => void) | undefined;
export function subscribeMfaRequired(callback: () => void) { listener = callback; return () => { listener = undefined; }; }
export function requestMfa(code: string) {
  if (code === "MFA_REQUIRED" || code === "MFA_REAUTHENTICATION_REQUIRED") listener?.();
}
