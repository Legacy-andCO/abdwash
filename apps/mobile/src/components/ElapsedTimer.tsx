import { useEffect, useState } from "react";
import { Text } from "react-native";
import { colors } from "../theme";
import { elapsedLabel } from "../operations";

export function ElapsedTimer({ startedAt, prefix = "Elapsed" }: { startedAt: string; prefix?: string }) {
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 1_000);
    return () => clearInterval(timer);
  }, [startedAt]);
  return <Text style={{ color: colors.primary, fontSize: 18, fontWeight: "900" }}>{prefix} · {elapsedLabel(startedAt, now)}</Text>;
}
