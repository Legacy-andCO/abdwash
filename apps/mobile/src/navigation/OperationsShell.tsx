import { StatusBar } from "expo-status-bar";
import { useState } from "react";
import { useEffect, useRef } from "react";
import { AppState, Pressable, StyleSheet, Text, View } from "react-native";
import NetInfo from "@react-native-community/netinfo";
import { SafeAreaView } from "react-native-safe-area-context";
import { queryClient } from "../cache/queryClient";
import { synchronizeOperations } from "../cache/sync";
import type { StaffContext } from "../lib";
import { navigationTabs, type MainTab } from "../operations";
import { JobsScreen, type JobsNavigationState } from "../screens/JobsScreen";
import { ProfileScreen } from "../screens/ProfileScreen";
import {
  ReportsScreen,
  type ReportsNavigationState,
} from "../screens/ReportsScreen";
import { TeamScreen, type TeamSection } from "../screens/TeamScreen";
import { TodayScreen } from "../screens/TodayScreen";
import { CustomersScreen } from "../screens/CustomersScreen";
import { InventoryScreen } from "../screens/InventoryScreen";
import { ServicesPricingScreen } from "../screens/ServicesPricingScreen";
import { colors, spacing } from "../theme";

export function OperationsShell({ context }: { context: StaffContext }) {
  const tabs = navigationTabs(context.role);
  const [tab, setTab] = useState<MainTab>("today");
  const [customersOpen, setCustomersOpen] = useState(false);
  const [inventoryOpen, setInventoryOpen] = useState(false);
  const [servicesOpen, setServicesOpen] = useState(false);
  const [jobDrillId, setJobDrillId] = useState<string | null>(null);
  const [jobsNavigation, setJobsNavigation] = useState<JobsNavigationState>({
    view: "today",
    offset: 0,
  });
  const [teamSection, setTeamSection] = useState<TeamSection>("teams");
  const [reportsNavigation, setReportsNavigation] =
    useState<ReportsNavigationState>(() => {
      const today = new Date().toISOString().slice(0, 10);
      return { period: "week", customStart: today, customEnd: today };
    });
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
    <SafeAreaView
      edges={["top", "bottom", "left", "right"]}
      style={styles.screen}
    >
      <StatusBar style="dark" />
      <View style={styles.header}>
        <View>
          <Text style={styles.eyebrow}>TRIFECTA OPERATIONS</Text>
          <Text style={styles.name}>
            {context.display_name || context.business_name}
          </Text>
        </View>
        <Text style={styles.role}>{context.role.toUpperCase()}</Text>
      </View>
      <View style={styles.body}>
        {servicesOpen ? (
          <ServicesPricingScreen
            context={context}
            onBack={() => setServicesOpen(false)}
          />
        ) : inventoryOpen ? (
          <InventoryScreen
            context={context}
            onBack={() => setInventoryOpen(false)}
          />
        ) : customersOpen ? (
          <CustomersScreen
            context={context}
            onBack={() => setCustomersOpen(false)}
            onOpenJob={(jobId) => {
              setCustomersOpen(false);
              setTab("jobs");
              setJobDrillId(jobId);
            }}
          />
        ) : tab === "today" ? (
          <TodayScreen
            context={context}
            onOpenCustomers={() => setCustomersOpen(true)}
            onOpenInventory={() => setInventoryOpen(true)}
            onOpenServices={() => setServicesOpen(true)}
          />
        ) : tab === "jobs" ? (
          <JobsScreen
            context={context}
            navigationState={jobsNavigation}
            onNavigationStateChange={setJobsNavigation}
            initialJobId={jobDrillId}
            onInitialJobClosed={() => setJobDrillId(null)}
          />
        ) : tab === "team" ? (
          <TeamScreen
            context={context}
            initialSection={teamSection}
            onSectionChange={setTeamSection}
          />
        ) : tab === "reports" ? (
          <ReportsScreen
            context={context}
            navigationState={reportsNavigation}
            onNavigationStateChange={setReportsNavigation}
            onOpenInventory={() => setInventoryOpen(true)}
          />
        ) : (
          <ProfileScreen context={context} />
        )}
      </View>
      {!customersOpen && !inventoryOpen && !servicesOpen ? (
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
      ) : null}
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
