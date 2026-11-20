import { Alert } from "./alert";
import { prepareOperationalLogout } from "./cache/queryClient";
import { t } from "./i18n";
import { supabase } from "./lib";

export async function signOutFromStaffApp() {
  try {
    await prepareOperationalLogout();
    const { error } = await supabase.auth.signOut({ scope: "local" });
    if (error) throw error;
  } catch {
    Alert.alert(
      t("Unable to sign out"),
      t("Check your connection and try again."),
    );
  }
}
