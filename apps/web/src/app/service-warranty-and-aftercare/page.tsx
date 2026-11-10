import { PolicyPage } from "@/components/policy-page";
import { policyMetadata } from "@/lib/policies";

export const metadata = policyMetadata("service-warranty-and-aftercare");

export default function Page() {
  return <PolicyPage slug="service-warranty-and-aftercare" />;
}
