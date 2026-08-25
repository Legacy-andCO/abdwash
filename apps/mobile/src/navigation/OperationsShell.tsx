import { StatusBar } from "expo-status-bar";
import { useState } from "react";
import { useEffect, useRef } from "react";
import {
  AppState,
  Pressable,
  SafeAreaView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import NetInfo from "@react-native-community/netinfo";
import { queryClient } from "../cache/queryClient";
import { synchronizeOperations } from "../cache/sync";
import type { StaffContext } from "../lib";
import { navigationTabs, type MainTab } from "../operations";
import { JobsScreen } from "../screens/JobsScreen";
import { ProfileScreen } from "../screens/ProfileScreen";
import { ReportsScreen } from "../screens/ReportsScreen";
import { TeamScreen } from "../screens/TeamScreen";
import { TodayScreen } from "../screens/TodayScreen";
import { colors, spacing } from "../theme";

export function OperationsShell({ context }: { context: StaffContext }) {
  const tabs = navigationTabs(context.role);
  const [tab, setTab] = useState<MainTab>("today");
  const inFlight = useRef<Promise<unknown> | null>(null);
  useEffect(() => {
    const synchronize = () => {
      if (inFlight.current) return inFlight.current;
      const operation = synchronizeOperations(queryClient, context)
        .catch(() => undefined)
        .finally(() => {
          inFlight.current = null;
        });
      inFlight.current = operation;
      return operation;
    };
    void synchronize();
    const appState = AppState.addEventListener("change", (state) => {
      if (state === "active") void synchronize();
    });
    const network = NetInfo.addEventListener((state) => {
      if (state.isConnected) void synchronize();
    });
    const timer = setInterval(() => {
      if (AppState.currentState === "active") void synchronize();
    }, 60_000);
    return () => {
      appState.remove();
      network();
      clearInterval(timer);
    };
  }, [context]);
  return (
    <SafeAreaView style={styles.screen}>
      <StatusBar style="dark" />
      <View style={styles.header}>
        <View>
          <Text style={styles.eyebrow}>ABDWASH OPERATIONS</Text>
          <Text style={styles.name}>
            {context.display_name || context.business_name}
          </Text>
        </View>
        <Text style={styles.role}>{context.role.toUpperCase()}</Text>
      </View>
      <View style={styles.body}>
        {tab === "today" ? (
          <TodayScreen context={context} />
        ) : tab === "jobs" ? (
          <JobsScreen context={context} />
        ) : tab === "team" ? (
          <TeamScreen context={context} />
        ) : tab === "reports" ? (
          <ReportsScreen context={context} />
        ) : (
          <ProfileScreen context={context} />
        )}
      </View>
      <View style={styles.tabs}>
        {tabs.map((value) => (
          <Pressable
            accessibilityRole="tab"
            accessibilityState={{ selected: tab === value }}
            key={value}
            onPress={() => setTab(value)}
            style={[styles.tab, tab === value ? styles.tabActive : undefined]}
          >
            <Text
              style={[
                styles.tabText,
                tab === value ? styles.tabTextActive : undefined,
              ]}
            >
              {value[0].toUpperCase() + value.slice(1)}
            </Text>
          </Pressable>
        ))}
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.background },
  header: {
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.md,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    backgroundColor: colors.surface,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  body: { flex: 1 },
  eyebrow: {
    color: colors.primary,
    fontWeight: "900",
    fontSize: 10,
    letterSpacing: 1.3,
  },
  name: { color: colors.text, fontWeight: "900", fontSize: 20 },
  role: { color: colors.primary, fontWeight: "900", fontSize: 11 },
  tabs: {
    flexDirection: "row",
    minHeight: 64,
    backgroundColor: colors.surface,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  tab: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    borderTopWidth: 3,
    borderTopColor: "transparent",
  },
  tabActive: { borderTopColor: colors.primary },
  tabText: { color: colors.textSecondary, fontSize: 11, fontWeight: "700" },
  tabTextActive: { color: colors.primary, fontWeight: "900" },
});
