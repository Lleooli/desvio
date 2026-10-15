import { Barlow_400Regular, Barlow_600SemiBold, useFonts } from "@expo-google-fonts/barlow";
import { BarlowCondensed_600SemiBold, BarlowCondensed_700Bold } from "@expo-google-fonts/barlow-condensed";
import { BricolageGrotesque_700Bold } from "@expo-google-fonts/bricolage-grotesque";
import { Stack } from "expo-router";
import { StatusBar } from "expo-status-bar";
import { GestureHandlerRootView } from "react-native-gesture-handler";
import { useCores } from "@/tema";

export default function RaizLayout() {
  const { tema, c } = useCores();
  const [carregou] = useFonts({
    Barlow_400Regular,
    Barlow_600SemiBold,
    BarlowCondensed_600SemiBold,
    BarlowCondensed_700Bold,
    BricolageGrotesque_700Bold,
  });
  if (!carregou) return null;

  return (
    <GestureHandlerRootView style={{ flex: 1 }}>
      <StatusBar style={tema === "dark" ? "light" : "dark"} />
      <Stack screenOptions={{ headerShown: false, contentStyle: { backgroundColor: c["surface-100"] } }}>
        <Stack.Screen name="(abas)" />
        <Stack.Screen name="lugares/[lugarId]" options={{ presentation: "modal" }} />
      </Stack>
    </GestureHandlerRootView>
  );
}
