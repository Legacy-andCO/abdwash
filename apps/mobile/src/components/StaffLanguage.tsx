import AsyncStorage from "@react-native-async-storage/async-storage";
import { useEffect, useSyncExternalStore } from "react";
import { Platform, Pressable, StyleSheet, Text } from "react-native";
import { LANGUAGE_STORAGE_KEY, preferredLanguage } from "../../../web/src/lib/i18n";
import { getStaffLanguage, setStaffLanguage, subscribeStaffLanguage } from "../i18n";
import { colors } from "../theme";

export function useStaffLanguage() {
  return useSyncExternalStore(subscribeStaffLanguage, getStaffLanguage, () => "en" as const);
}
export function StaffLanguage() {
  const language = useStaffLanguage();
  useEffect(() => {
    void AsyncStorage.getItem(LANGUAGE_STORAGE_KEY).then(value => { if (value) setStaffLanguage(preferredLanguage(value)); }).catch(() => undefined);
  }, []);
  useEffect(() => {
    if (Platform.OS === "web") { document.documentElement.lang = language; document.documentElement.dir = language === "ar" ? "rtl" : "ltr"; }
  }, [language]);
  return <Pressable accessibilityRole="button" accessibilityLabel={language === "en" ? "Application language: English" : "لغة التطبيق: العربية"}
    onPress={() => { const next = language === "en" ? "ar" : "en"; setStaffLanguage(next); void AsyncStorage.setItem(LANGUAGE_STORAGE_KEY, next).catch(() => undefined); }} style={styles.button}>
    <Text style={styles.text}>{language === "en" ? "Language · English" : "اللغة · العربية"}</Text>
  </Pressable>;
}
const styles = StyleSheet.create({ button: { minHeight: 44, justifyContent: "center", paddingHorizontal: 16, backgroundColor: colors.surface }, text: { color: colors.text, fontSize: 14, fontWeight: "600", textAlign: "right" } });
