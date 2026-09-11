import type { CSSProperties } from "react";
import { colors, radii, spacing } from "../theme";
import { toIsoDate } from "./picker-values";

export { fromIsoDate, toIsoDate } from "./picker-values";

type PickerFieldProps = {
  label: string;
  value: string;
  onChange: (value: string) => void;
  minimumDate?: Date;
  maximumDate?: Date;
};

function Picker({ label, value, onChange, minimumDate, maximumDate, type }: PickerFieldProps & { type: "date" | "time" }) {
  return (
    <label style={{ display: "flex", flexDirection: "column", gap: spacing.sm, minWidth: 0 }}>
      <span style={{ color: colors.textSecondary, fontSize: 11, fontWeight: 900, letterSpacing: 1 }}>{label.toUpperCase()}</span>
      <input
        aria-label={label}
        type={type}
        value={type === "time" ? value.slice(0, 5) : value}
        min={type === "date" && minimumDate ? toIsoDate(minimumDate) : undefined}
        max={type === "date" && maximumDate ? toIsoDate(maximumDate) : undefined}
        onChange={(event) => {
          if (event.target.value && event.target.validity.valid) onChange(event.target.value);
        }}
        style={fieldStyle}
      />
    </label>
  );
}

export function DatePickerField(props: PickerFieldProps) {
  return <Picker {...props} type="date" />;
}

export function TimePickerField(props: PickerFieldProps) {
  return <Picker {...props} type="time" />;
}

const fieldStyle: CSSProperties = {
  boxSizing: "border-box", width: "100%", minWidth: 0, minHeight: 52,
  border: `1px solid ${colors.border}`, borderRadius: radii.md,
  backgroundColor: colors.surface, padding: spacing.lg,
  color: colors.text, font: "inherit", fontSize: 16, fontWeight: 800,
};
