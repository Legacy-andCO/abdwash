"use client";

import Link from "next/link";
import { useI18n } from "./i18n-provider";

export function ServiceAreaNotice({ compact = false }: { compact?: boolean }) {
  const { t } = useI18n();
  return <aside className={compact ? "service-area-notice compact" : "service-area-notice"} role="note">
    <div className="service-area-notice-icon" aria-hidden="true">!</div>
    <div>
      <strong>{t("serviceArea.title")}</strong>
      <p>{t("serviceArea.copy")}</p>
      <span>{t("serviceArea.availableIntro")}</span>
      <ul>
        <li>{t("serviceArea.villas")}</li>
        <li>{t("serviceArea.compounds")}</li>
        <li>{t("serviceArea.privateParking")}</li>
        <li>{t("serviceArea.businessParking")}</li>
        <li>{t("serviceArea.fmAccess")}</li>
      </ul>
      <p>{t("serviceArea.contact")} <Link href="/contact">{t("nav.contact")}</Link></p>
    </div>
  </aside>;
}
