import { AuthConfirmation } from "@/components/auth-confirmation";
import { SiteHeader } from "@/components/site-header";

export default function ConfirmPage() {
  return <><SiteHeader /><main className="auth-page"><AuthConfirmation /></main></>;
}
