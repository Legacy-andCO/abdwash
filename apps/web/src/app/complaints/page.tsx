import { PolicyPage } from "@/components/policy-page";
import { policyMetadata } from "@/lib/policies";

export const metadata = policyMetadata("complaints");

export default function Page() {
  return <PolicyPage slug="complaints" />;
}
