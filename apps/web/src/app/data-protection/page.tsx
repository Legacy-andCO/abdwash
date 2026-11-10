import { PolicyPage } from "@/components/policy-page";
import { policyMetadata } from "@/lib/policies";

export const metadata = policyMetadata("data-protection");

export default function Page() {
  return <PolicyPage slug="data-protection" />;
}
