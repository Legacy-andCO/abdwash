export function getPublicSiteUrl(): string {
  const configured = process.env.NEXT_PUBLIC_SITE_URL?.trim();
  if (configured) {
    try {
      const url = new URL(configured);
      const localHttp = url.protocol === "http:" && ["localhost", "127.0.0.1"].includes(url.hostname);
      if (url.protocol === "https:" || localHttp) return url.origin;
    } catch {
      // Fall through to the browser origin so sign-up remains usable in development.
    }
  }
  if (typeof window !== "undefined") return window.location.origin;
  return "http://localhost:3000";
}

export function safeReturnPath(value: string | null, fallback = "/account"): string {
  if (!value?.startsWith("/") || value.startsWith("//") || /[\\\u0000-\u0020\u007f]/.test(value) || /%5c|%0[ad]/i.test(value)) return fallback;
  const trustedBase = "https://return.invalid";
  return new URL(value, trustedBase).origin === trustedBase ? value : fallback;
}

export function getAuthConfirmUrl(returnTo: string | null): string {
  const url = new URL("/auth/confirm", getPublicSiteUrl());
  url.searchParams.set("returnTo", safeReturnPath(returnTo));
  return url.toString();
}
