"use client";

import { AccountBookings } from "@/components/account-bookings";
import { SiteHeader } from "@/components/site-header";
import Link from "next/link";
import { useI18n } from "@/components/i18n-provider";

export default function AccountPage() { const { t } = useI18n(); return <><SiteHeader /><div className="account-profile-link"><Link className="button button-ghost" href="/account/profile">{t("account.profileLink")}</Link></div><AccountBookings /></>; }
