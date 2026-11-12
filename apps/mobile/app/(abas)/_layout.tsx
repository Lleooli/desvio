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
        // Igual à barra padrão do React Navigation: avisa o tabPress (rolar para o topo,
        // recarregar) e só navega se ninguém cancelou e a aba ainda não está aberta.
        const tocar = (area: Area) => {
          const rota = state.routes.find((r) => r.name === area);
          if (!rota) return;
          const evento = navigation.emit({ type: "tabPress", target: rota.key, canPreventDefault: true });
          if (area !== nome && !evento.defaultPrevented) navigation.navigate(area);
        };
        return <BottomNav ativo={ehArea(nome) ? nome : "viagens"} onChange={tocar} />;
      }}
    >
      <Tabs.Screen name="viagens" options={{ title: "Viagens" }} />
      <Tabs.Screen name="descobrir" options={{ title: "Descobrir" }} />
      <Tabs.Screen name="roteiro" options={{ title: "Roteiro" }} />
      <Tabs.Screen name="perfil" options={{ title: "Perfil" }} />
    </Tabs>
  );
}
