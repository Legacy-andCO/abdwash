import { AccountBookings } from "@/components/account-bookings";
import { SiteHeader } from "@/components/site-header";
import Link from "next/link";

export default function AccountPage() { return <><SiteHeader /><div className="account-profile-link"><Link className="button button-ghost" href="/account/profile">Profile & saved details</Link></div><AccountBookings /></>; }
