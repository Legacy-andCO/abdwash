"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useAuth } from "./auth-provider";
import { useI18n } from "./i18n-provider";
import {
  cachedCustomerProfile,
  loadCustomerProfile,
} from "@/lib/customer-profile-resource";
import type { CustomerProfileBootstrap } from "@/lib/types";
import { localizeServiceName } from "@/lib/i18n";

export function HomeLoyaltyStatus() {
  const { user, loading: authLoading } = useAuth();
  const userId = user?.id;
  const { language, t } = useI18n();
  const [snapshot, setSnapshot] = useState<{
    userId: string;
    data: CustomerProfileBootstrap;
  } | null>(null);

  useEffect(() => {
    if (authLoading || !userId) return;
    let active = true;
    const cached = cachedCustomerProfile(userId);
    const load = (refresh = false) => {
      void loadCustomerProfile(userId, { refresh })
        .then((data) => {
          if (active) setSnapshot({ userId, data });
        })
        .catch(() => undefined);
    };
    load();
    if (cached) {
      load(true);
    }
    const refreshLoyalty = () => load(true);
    window.addEventListener("trifecta-loyalty-updated", refreshLoyalty);
    return () => {
      active = false;
      window.removeEventListener("trifecta-loyalty-updated", refreshLoyalty);
    };
  }, [authLoading, userId]);

  const loyalty =
    user && snapshot?.userId === user.id ? snapshot.data.loyalty : null;
  if (!loyalty?.enabled || !loyalty.configured) return null;

  const rewardAvailable = loyalty.available_rewards > 0;
  const rewardService = loyalty.reward_service;
  const rewardServiceName = rewardService
    ? localizeServiceName(language, rewardService.name)
    : t("home.loyaltyWash");
  return (
    <section className="shell home-loyalty" aria-labelledby="home-loyalty-title">
      <div>
        <p className="eyebrow">
          <span /> {t("home.loyaltyEyebrow")}
        </p>
        <h2 id="home-loyalty-title">
          {rewardAvailable
            ? t("home.loyaltyAvailable", {
                service: rewardServiceName,
              })
            : t("home.loyaltyProgress", {
                current: loyalty.progress_washes,
                required: loyalty.required_washes,
              })}
        </h2>
        <p>
          {rewardAvailable
            ? t("home.loyaltyAvailableCopy")
            : t("home.loyaltyRemaining", {
                count: loyalty.washes_remaining,
                service: rewardServiceName,
              })}
        </p>
      </div>
      <div className="home-loyalty-actions">
        {rewardAvailable ? (
          <Link
            className="button"
            href={rewardService ? `/book?service=${rewardService.id}` : "/book"}
          >
            {t("home.bookReward")}
          </Link>
        ) : null}
        <Link className="button button-ghost" href="/account/profile#rewards">
          {t("home.viewRewards")}
        </Link>
      </div>
    </section>
  );
}
