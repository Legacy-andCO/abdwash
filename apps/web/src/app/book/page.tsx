import type { Metadata } from "next";
import { BookingWizard } from "@/components/booking-wizard";

export const metadata: Metadata = { title: "Book a wash" };

export default async function BookPage({ searchParams }: { searchParams: Promise<{ service?: string }> }) {
  const params = await searchParams;
  return <BookingWizard initialServiceId={params.service ?? ""} />;
}
