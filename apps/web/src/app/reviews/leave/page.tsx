import { Suspense } from "react";
import { LeaveReviewPage } from "@/components/leave-review-page";

export default function Page() {
  return <Suspense fallback={null}><LeaveReviewPage /></Suspense>;
}
