import { Platform } from "react-native";
import { brandColors } from "./brand-colors";

export const colors = {
  ...brandColors,
  surface: "#FFFFFF",
  surfaceElevated: "#FBF7F2",
  secondary: "#F6E2D2",
  text: "#241C1A",
  textSecondary: "#6E625D",
  success: "#26724E",
  warning: "#A45A0A",
  danger: "#A33A32",
  border: "#DED2C7",
  dangerSurface: "#FBE9E7",
  successSurface: "#E7F3EC",
  warningSurface: "#FFF0D6",
  neutralSurface: "#F0E9E3",
};

export const spacing = { xs: 4, sm: 8, md: 12, lg: 16, xl: 24, xxl: 32 };
export const radii = { sm: 10, md: 14, lg: 20, pill: 999 };
export const elevation = Platform.select({
  ios: {
    shadowColor: "#241C1A",
    shadowOpacity: 0.08,
    shadowRadius: 14,
    shadowOffset: { width: 0, height: 6 },
  },
  android: { elevation: 2 },
  default: {},
});
