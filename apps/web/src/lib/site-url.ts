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
