import { Platform, type ViewStyle } from "react-native";

export const webSheetStyle: ViewStyle = Platform.OS === "web" ? {
  width: "100%",
  maxWidth: 680,
  maxHeight: "90%",
  alignSelf: "center",
  overflow: "scroll",
} : {};
