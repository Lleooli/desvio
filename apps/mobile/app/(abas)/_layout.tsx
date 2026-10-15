import { Tabs } from "expo-router";
import { fontes, useCores } from "@/tema";

// As quatro abas da barra inferior. Descobrir e Roteiro sempre mostram a viagem ativa.
export default function AbasLayout() {
  const { c } = useCores();
  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        tabBarActiveTintColor: c.placa,
        tabBarInactiveTintColor: c["ink-muted"],
        tabBarStyle: { backgroundColor: c["surface-200"], borderTopColor: c.line },
        tabBarLabelStyle: { fontFamily: fontes.sansForte, fontSize: 12 },
      }}
    >
      <Tabs.Screen name="viagens" options={{ title: "Viagens" }} />
      <Tabs.Screen name="descobrir" options={{ title: "Descobrir" }} />
      <Tabs.Screen name="roteiro" options={{ title: "Roteiro" }} />
      <Tabs.Screen name="perfil" options={{ title: "Perfil" }} />
    </Tabs>
  );
}
