// Desvio — tipos dos componentes (documentação; window.Desvio.*)

export type Categoria = "turismo" | "restaurante" | "posto" | "natureza" | "hospedagem";
export type IconName =
  | "x" | "check" | "star" | "pin" | "camera" | "food" | "fuel" | "leaf" | "bed"
  | "route" | "compass" | "user" | "suitcase" | "clock" | "at" | "car";

export interface IconProps {
  name: IconName;
  /** px, padrão 20 */
  size?: number;
  filled?: boolean;
  strokeWidth?: number;
  /** Texto para leitor de tela; sem ele o ícone é decorativo. */
  label?: string;
  className?: string;
}

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  /** primary = placa; secondary = contorno ink; ghost = só texto placa; favorito = faixa com brilho */
  variant?: "primary" | "secondary" | "ghost" | "favorito";
  size?: "md" | "sm";
  icon?: IconName;
  /** Ocupa a largura toda (CTAs no rodapé da tela). */
  block?: boolean;
  children?: React.ReactNode;
}

export interface ChipProps {
  /** Preenche rótulo e ícone a partir da categoria. */
  categoria?: Categoria;
  label?: string;
  icon?: IconName;
  /** Com onClick vira filtro (button + aria-pressed). */
  selected?: boolean;
  onClick?: () => void;
  /** Fundo sólido para ficar legível sobre a foto do card. */
  onPhoto?: boolean;
  children?: React.ReactNode;
}

export interface RatingProps {
  /** 0 a 5; formatado em pt-BR ("4,7"). Sem nota, não renderiza. */
  nota?: number | null;
  avaliacoes?: number | null;
  onPhoto?: boolean;
}

export interface SwipeCardProps {
  nome: string;
  categoria?: Categoria;
  foto?: string | null;
  cidade?: string;
  uf?: string;
  nota?: number | null;
  avaliacoes?: number | null;
  /** km na rota. */
  km?: number;
  /** horas desde a saída. */
  horas?: number;
  descricao?: string;
  /** URL ou @handle. */
  instagram?: string | null;
  /** true quando o @ veio de busca web (instagram_origem = "busca"). */
  instagramProvavel?: boolean;
  /** Carimbo exibido enquanto o card é arrastado. */
  stamp?: "bora" | "passo" | "favorito" | null;
  style?: React.CSSProperties;
  className?: string;
}

export interface SwipeActionsProps {
  onPasso?: () => void;
  onFavorito?: () => void;
  onBora?: () => void;
  disabled?: boolean;
}

export interface StopItemProps {
  cidade: string;
  uf?: string;
  km?: number;
  /** 0 = saída */
  horas?: number;
  tipo?: "origem" | "parada" | "destino";
  /** parada sendo escolhida agora */
  ativo?: boolean;
  aceitos?: number;
  total?: number;
}

export interface TextFieldProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  icon?: IconName;
  hint?: string;
  /** Mensagem de erro; troca a dica e pinta a borda de perigo. */
  erro?: string;
}

export interface BottomNavProps {
  ativo?: "viagens" | "descobrir" | "roteiro" | "perfil";
  onChange?: (id: "viagens" | "descobrir" | "roteiro" | "perfil") => void;
}

export interface DestaqueProps {
  /** Uma palavra (ou duas) do título. */
  children: React.ReactNode;
}

export interface CeuProps {
  /** "faixa" (amarelo no canto superior esquerdo, padrão) ou "placa" (verde no canto superior). */
  variante?: "faixa" | "placa";
  /** Recorta a base com o perfil de serra, na cor de fundoSerra. */
  serra?: boolean;
  /** Cor da serra, padrão var(--surface-100): a cor do que vem logo abaixo. */
  fundoSerra?: string;
  /** Cantos radius-lg, para usar como bloco dentro da tela. */
  arredondado?: boolean;
  style?: React.CSSProperties;
  children?: React.ReactNode;
}

export interface EstradaProps {
  /** Cidades da rota, na ordem. */
  cidades: string[];
  variante?: "curva" | "subida";
  /** px por segundo, padrão 36. */
  velocidade?: number;
  /** Congela o texto (também congela sozinho com prefers-reduced-motion). */
  parado?: boolean;
  /** Largura da pista em unidades do viewBox 400x200, padrão 46. */
  largura?: number;
  /** Texto para leitor de tela; padrão "Rota: cidade, cidade…". */
  rotulo?: string;
}

export interface SegmentedProps {
  opcoes: { valor: string; label: string; icon?: IconName }[];
  /** Controlado. Sem ele, o componente guarda o estado e começa em `padrao`. */
  valor?: string;
  padrao?: string;
  onChange?: (valor: string) => void;
  block?: boolean;
  /** Nome do grupo para leitor de tela. */
  rotulo?: string;
}

export interface ToastProps {
  children: React.ReactNode;
  icon?: IconName;
  /** Texto do botão, ex. "Desfazer". */
  acao?: string;
  onAcao?: () => void;
}
