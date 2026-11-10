import { PolicyPage } from "@/components/policy-page";
import { policyMetadata } from "@/lib/policies";

export const metadata = policyMetadata("terms-and-conditions");

export default function Page() {
  return <PolicyPage slug="terms-and-conditions" />;
}
