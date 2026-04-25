import { StatusBar } from "expo-status-bar";
import { StyleSheet, Text, View } from "react-native";

/**
 * Replace with navigation + API client using EXPO_PUBLIC_API_BASE.
 * See README.md for EAS Build / Submit to app stores.
 */
export default function App() {
  return (
    <View style={styles.container}>
      <Text style={styles.title}>Biomarker Identifier</Text>
      <Text style={styles.hint}>
        Set EXPO_PUBLIC_API_BASE and implement login against /api/v1/auth/login
      </Text>
      <StatusBar style="auto" />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: "#f8f9fa",
    alignItems: "center",
    justifyContent: "center",
    padding: 24,
  },
  title: {
    fontSize: 20,
    fontWeight: "600",
    color: "#2c3e50",
    marginBottom: 12,
  },
  hint: {
    fontSize: 14,
    color: "#64748b",
    textAlign: "center",
  },
});
