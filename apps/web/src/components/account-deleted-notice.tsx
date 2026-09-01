"use client";

import { useEffect, useState } from "react";
import { useI18n } from "./i18n-provider";

export function AccountDeletedNotice() {
  const { t } = useI18n();
  const [visible, setVisible] = useState(false);
  useEffect(() => {
    const url = new URL(window.location.href);
    if (url.searchParams.get("accountDeleted") !== "1") return;
    const timer = window.setTimeout(() => setVisible(true), 0);
    url.searchParams.delete("accountDeleted");
    window.history.replaceState({}, "", `${url.pathname}${url.search}${url.hash}`);
    return () => window.clearTimeout(timer);
  }, []);
  return visible ? <div className="shell account-deleted-notice inline-notice" role="status"><strong>{t("profile.accountDeleted")}</strong></div> : null;
}
