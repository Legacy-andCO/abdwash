import * as Haptics from "expo-haptics";

export async function successHaptic(): Promise<void> {
  await Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
}

export async function selectionHaptic(): Promise<void> {
  await Haptics.selectionAsync();
}
