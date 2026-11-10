import { PolicyPage } from "@/components/policy-page";
import { policyMetadata } from "@/lib/policies";

export const metadata = policyMetadata("privacy-policy");

export default function Page() {
  return <PolicyPage slug="privacy-policy" />;
}
