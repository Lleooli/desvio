import { useEffect, useState } from "react";
import { KeyboardAvoidingView, Modal, Platform, Pressable, StyleSheet, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { espaco, estiloTexto, raio, useCores } from "@/tema";
import { Button } from "./Button";
import { TextField } from "./TextField";

/** A palavra que a pessoa digita para confirmar; é a mesma que o coletor exige em `DELETE /eu`. */
const PALAVRA = "APAGAR";

type Props = {
  visivel: boolean;
  /** Enquanto a conta está sendo apagada: os botões ficam parados. */
  apagando: boolean;
  /** Mensagem do erro ao apagar, se houve. */
  erro?: string;
  onApagar: () => void;
  onFechar: () => void;
};

/**
 * Folha de confirmação de Apagar conta (HU19). Apagar não tem volta, então a pessoa digita
 * APAGAR antes; sem isso o botão fica desligado.
 */
export function FolhaApagarConta({ visivel, apagando, erro, onApagar, onFechar }: Props) {
  const { c } = useCores();
  const margens = useSafeAreaInsets();
  const [texto, setTexto] = useState("");
  const confirmou = texto.trim().toUpperCase() === PALAVRA;

  useEffect(() => {
    if (!visivel) setTexto(""); // cada abertura começa do zero
  }, [visivel]);

  const fechar = () => {
    if (!apagando) onFechar();
  };

  return (
    <Modal visible={visivel} transparent animationType="slide" onRequestClose={fechar}>
      <KeyboardAvoidingView style={s.tela} behavior={Platform.OS === "ios" ? "padding" : undefined}>
        <Pressable accessibilityLabel="Fechar" style={[s.veu, { backgroundColor: c.scrim }]} onPress={fechar} />
        <View
          style={[
            s.painel,
            { backgroundColor: c["surface-100"], paddingBottom: margens.bottom + espaco["space-6"] },
          ]}
        >
          <Text accessibilityRole="header" style={[estiloTexto("title"), { color: c.ink }]}>
            Apagar sua conta?
          </Text>
          <Text style={[estiloTexto("body"), { color: c["ink-muted"] }]}>
            Suas viagens, decisões, roteiros e o perfil de gosto somem na hora, e a conta de login em até 15 dias.
            Não dá para desfazer. Se quiser uma cópia, exporte seus dados antes.
          </Text>
          <TextField
            label={`Digite ${PALAVRA} para confirmar`}
            value={texto}
            onChangeText={setTexto}
            autoCapitalize="characters"
            autoCorrect={false}
            editable={!apagando}
            erro={erro}
          />
          <Button block disabled={!confirmou || apagando} onPress={onApagar}>
            {apagando ? "Apagando..." : "Apagar conta"}
          </Button>
          <Button block variant="ghost" disabled={apagando} onPress={fechar}>
            Voltar
          </Button>
        </View>
      </KeyboardAvoidingView>
    </Modal>
  );
}

const s = StyleSheet.create({
  tela: { flex: 1 },
  veu: { flex: 1 },
  painel: {
    gap: espaco["space-3"],
    padding: espaco["space-4"],
    borderTopLeftRadius: raio["radius-lg"],
    borderTopRightRadius: raio["radius-lg"],
  },
});
