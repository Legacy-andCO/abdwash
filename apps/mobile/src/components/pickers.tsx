import DateTimePicker, {
  DateTimePickerAndroid,
  type DateTimePickerEvent,
} from "@react-native-community/datetimepicker";
import { useState } from "react";
import { Platform, Pressable, StyleSheet, Text, View } from "react-native";
import { colors, radii, spacing } from "../theme";
import {
  formatHumanDate,
  formatHumanTime,
  fromApiTime,
  fromIsoDate,
  toApiTime,
  toIsoDate,
} from "./picker-values";

export { fromIsoDate, toIsoDate } from "./picker-values";

type PickerFieldProps = {
  label: string;
  value: string;
  onChange: (value: string) => void;
  minimumDate?: Date;
  maximumDate?: Date;
};

export function DatePickerField({
  label,
  value,
  onChange,
  minimumDate,
  maximumDate,
}: PickerFieldProps) {
  const [showIos, setShowIos] = useState(false);
  const selected = fromIsoDate(value);
  function accept(_event: DateTimePickerEvent, next?: Date) {
    if (next) onChange(toIsoDate(next));
    setShowIos(false);
  }
  function open() {
    if (Platform.OS === "android") {
      DateTimePickerAndroid.open({
        value: selected,
        mode: "date",
        minimumDate,
        maximumDate,
        onChange: accept,
      });
    } else {
      setShowIos(true);
    }
  }
  return (
    <View style={styles.group}>
      <Text style={styles.label}>{label.toUpperCase()}</Text>
      <Pressable
        accessibilityRole="button"
        accessibilityLabel={`${label}, ${formatHumanDate(value)}`}
        onPress={open}
        style={({ pressed }) => [
          styles.field,
          pressed ? styles.pressed : undefined,
        ]}
      >
        <Text style={styles.value}>{formatHumanDate(value)}</Text>
        <Text style={styles.chevron}>›</Text>
      </Pressable>
      {showIos ? (
        <DateTimePicker
          value={selected}
          mode="date"
          display="inline"
          minimumDate={minimumDate}
          maximumDate={maximumDate}
          onChange={accept}
        />
      ) : null}
    </View>
  );
}

export function TimePickerField({ label, value, onChange }: PickerFieldProps) {
  const [showIos, setShowIos] = useState(false);
  const selected = fromApiTime(value);
  function accept(_event: DateTimePickerEvent, next?: Date) {
    if (next) onChange(toApiTime(next));
    setShowIos(false);
  }
  function open() {
    if (Platform.OS === "android") {
      DateTimePickerAndroid.open({
        value: selected,
        mode: "time",
        is24Hour: false,
        onChange: accept,
      });
    } else {
      setShowIos(true);
    }
  }
  return (
    <View style={styles.group}>
      <Text style={styles.label}>{label.toUpperCase()}</Text>
      <Pressable
        accessibilityRole="button"
        accessibilityLabel={`${label}, ${formatHumanTime(value)}`}
        onPress={open}
        style={({ pressed }) => [
          styles.field,
          pressed ? styles.pressed : undefined,
        ]}
      >
        <Text style={styles.value}>{formatHumanTime(value)}</Text>
        <Text style={styles.chevron}>›</Text>
      </Pressable>
      {showIos ? (
        <DateTimePicker
          value={selected}
          mode="time"
          display="spinner"
          onChange={accept}
        />
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  group: { gap: spacing.sm },
  label: {
    color: colors.textSecondary,
    fontSize: 11,
    fontWeight: "900",
    letterSpacing: 1,
  },
  field: {
    minHeight: 52,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radii.md,
    backgroundColor: colors.surface,
    paddingHorizontal: spacing.lg,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
  },
  pressed: { backgroundColor: colors.secondary, borderColor: colors.primary },
  value: { color: colors.text, fontSize: 16, fontWeight: "800" },
  chevron: { color: colors.primary, fontSize: 28, lineHeight: 28 },
});
