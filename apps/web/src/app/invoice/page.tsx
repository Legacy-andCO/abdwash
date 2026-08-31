import type { Metadata } from "next";
import { InvoiceView } from "@/components/invoice-view";

export const metadata: Metadata = {
  title: "Payment invoice",
  robots: { index: false, follow: false },
};

export default async function InvoicePage({
  searchParams,
}: {
  searchParams: Promise<{ invoice?: string }>;
}) {
  const params = await searchParams;
  return <InvoiceView invoiceId={params.invoice ?? ""} />;
}
