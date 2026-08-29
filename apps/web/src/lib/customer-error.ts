import { ApiError, friendlyError } from "./api";
import type { Language, TranslationKey } from "./i18n";

type Translator = (key: TranslationKey) => string;

export function localizedCustomerError(
  error: unknown,
  language: Language,
  t: Translator,
): string {
  if (error instanceof ApiError && error.code === "MOBILE_MINIMUM_NOT_MET")
    return t("errors.mobileMinimum");
  if (
    error instanceof ApiError &&
    [
      "INVALID_SERVICE",
      "INVALID_SERVICE_ADDON",
      "INVALID_VEHICLE_TYPE",
      "SERVICE_ADDON_MISMATCH",
      "SERVICE_CHANNEL_UNAVAILABLE",
      "SERVICE_PRICE_UNAVAILABLE",
    ].includes(error.code)
  )
    return t("errors.catalogueChanged");
  if (error instanceof ApiError && error.isSchedulingConflict)
    return t("errors.timeUnavailable");
  if (language === "en") return friendlyError(error);
  if (error instanceof ApiError && error.code === "NETWORK_ERROR") return t("errors.network");
  return t("errors.generic");
}
