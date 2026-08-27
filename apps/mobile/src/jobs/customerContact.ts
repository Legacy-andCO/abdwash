export function customerEmailUrl(email: string): string {
  return `mailto:${email.trim()}`;
}
