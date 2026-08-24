import { CustomerBookingDetail } from "@/components/customer-booking-detail";
import { SiteHeader } from "@/components/site-header";

type Props = { params: Promise<{ bookingId: string }> };

export default async function CustomerBookingPage({ params }: Props) {
  const { bookingId } = await params;
  return <><SiteHeader /><CustomerBookingDetail bookingId={bookingId} /></>;
}
