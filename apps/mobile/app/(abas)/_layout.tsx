import { Tabs } from "expo-router";
import { areas, BottomNav, type Area } from "@/componentes/BottomNav";

const ehArea = (nome: string): nome is Area => areas.some((a) => a.id === nome);

// As quatro abas da barra inferior. Descobrir e Roteiro sempre mostram a viagem ativa.
export default function AbasLayout() {
  return (
    <Tabs
      screenOptions={{ headerShown: false }}
      tabBar={({ state, navigation }) => {
        const nome = state.routes[state.index].name;
        return (
          <BottomNav ativo={ehArea(nome) ? nome : "viagens"} onChange={(area) => navigation.navigate(area)} />
        );
      }}
    >
      <Tabs.Screen name="viagens" options={{ title: "Viagens" }} />
      <Tabs.Screen name="descobrir" options={{ title: "Descobrir" }} />
      <Tabs.Screen name="roteiro" options={{ title: "Roteiro" }} />
      <Tabs.Screen name="perfil" options={{ title: "Perfil" }} />
    </Tabs>
  );
}
