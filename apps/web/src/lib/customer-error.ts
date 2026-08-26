import { ApiError, friendlyError } from "./api";
import type { Language, TranslationKey } from "./i18n";

type Translator = (key: TranslationKey) => string;

export function localizedCustomerError(
  error: unknown,
  language: Language,
  t: Translator,
): string {
  if (language === "en") return friendlyError(error);
  if (error instanceof ApiError && error.code === "NETWORK_ERROR") return t("errors.network");
  return t("errors.generic");
}
