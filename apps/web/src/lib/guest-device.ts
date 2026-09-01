const DEVICE_KEY = "trifecta-guest-device-id";

export function getGuestDeviceId(): string {
  const existing = window.localStorage.getItem(DEVICE_KEY);
  if (existing) return existing;
  const created = crypto.randomUUID();
  window.localStorage.setItem(DEVICE_KEY, created);
  return created;
}

export function clearCustomerBrowserState(userId?: string): void {
  if (userId) {
    window.localStorage.removeItem(
      `trifecta-profile-onboarding-dismissed:${userId}`,
    );
    window.sessionStorage.removeItem(`trifecta-review-open:${userId}`);
  }
}
