import { Platform } from "react-native";

export const colors = {
  background: "#F3F6F3",
  surface: "#FFFFFF",
  surfaceElevated: "#F9FBF9",
  primary: "#09695E",
  primaryPressed: "#07564E",
  secondary: "#E3EFEA",
  text: "#153C36",
  textSecondary: "#667A74",
  success: "#1F7A5B",
  warning: "#A66B14",
  danger: "#B3473D",
  border: "#DCE6E1",
  white: "#FFFFFF",
};

export const spacing = { xs: 4, sm: 8, md: 12, lg: 16, xl: 24, xxl: 32 };
export const radii = { sm: 10, md: 14, lg: 20, pill: 999 };
export const elevation = Platform.select({
  ios: {
    shadowColor: "#173C36",
    shadowOpacity: 0.08,
    shadowRadius: 14,
    shadowOffset: { width: 0, height: 6 },
  },
  android: { elevation: 2 },
  default: {},
});
