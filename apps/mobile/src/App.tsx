import { StatusBar } from "expo-status-bar";
import { SafeAreaView, StyleSheet, Text, View } from "react-native";

export default function App() {
  return (
    <SafeAreaView style={styles.screen}>
      <StatusBar style="dark" />
      <View style={styles.card}>
        <Text style={styles.eyebrow}>STAFF OPERATIONS</Text>
        <Text style={styles.title}>AbdWash</Text>
        <Text style={styles.body}>The staff application foundation is ready.</Text>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, alignItems: "center", justifyContent: "center", backgroundColor: "#f4f7f8", padding: 24 },
  card: { alignItems: "center" },
  eyebrow: { color: "#287b8c", fontSize: 12, fontWeight: "700", letterSpacing: 2 },
  title: { color: "#10262b", fontSize: 56, fontWeight: "700", letterSpacing: -3, marginVertical: 8 },
  body: { color: "#4b646a", fontSize: 16, textAlign: "center" },
});

