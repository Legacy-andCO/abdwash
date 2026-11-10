import { PolicyPage } from "@/components/policy-page";
import { policyMetadata } from "@/lib/policies";

export const metadata = policyMetadata("cancellation-and-refund-policy");

export default function Page() {
  return <PolicyPage slug="cancellation-and-refund-policy" />;
}
