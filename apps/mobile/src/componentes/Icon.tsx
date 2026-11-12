import Svg, { Path } from "react-native-svg";
import { tamanhoIcone, useCores } from "@/tema";

// Traços copiados de docs/design/design-system/components/bundle.js: grade de 24px, traço 1.8.
const caminhos = {
  x: "M6 6l12 12M18 6L6 18",
  check: "M5 12.5l4.5 4.5L19 7",
  star: "M12 3.5l2.6 5.3 5.9.9-4.25 4.15 1 5.85L12 16.9l-5.25 2.8 1-5.85L3.5 9.7l5.9-.9z",
  pin: "M12 21s-6.5-5.6-6.5-11a6.5 6.5 0 0113 0c0 5.4-6.5 11-6.5 11zM12 12.5a2.5 2.5 0 100-5 2.5 2.5 0 000 5z",
  camera: "M4 8h3l2-2.5h6L17 8h3v11H4zM12 16.5a3.5 3.5 0 100-7 3.5 3.5 0 000 7z",
  food: "M7 3v8M5 3v5a2 2 0 004 0V3M7 11v10M16 21V3c-2 1.5-3 4-3 7v3h3",
  fuel: "M4 20V5a1 1 0 011-1h8a1 1 0 011 1v15M3 20h12M6 8h6M14 9h2.5a1.5 1.5 0 011.5 1.5V16a1.5 1.5 0 003 0V8l-3-3",
  leaf: "M5 19c0-8 5-14 14-14 0 9-6 14-14 14zM5 19l7-7",
  bed: "M3 18V7M3 13h18v5M21 13a3 3 0 00-3-3h-7v3M7 11.5a1.5 1.5 0 100-3 1.5 1.5 0 000 3z",
  route: "M6 19a2 2 0 100-4 2 2 0 000 4zM18 9a2 2 0 100-4 2 2 0 000 4zM6 15V9.5A3.5 3.5 0 019.5 6H12M18 9v5.5a3.5 3.5 0 01-3.5 3.5H12",
  compass: "M12 21a9 9 0 100-18 9 9 0 000 18zM15.5 8.5l-2 5-5 2 2-5z",
  user: "M12 12a4 4 0 100-8 4 4 0 000 8zM4 20a8 8 0 0116 0",
  suitcase: "M4 8h16v11H4zM9 8V5.5A1.5 1.5 0 0110.5 4h3A1.5 1.5 0 0115 5.5V8M4 13h16",
  clock: "M12 21a9 9 0 100-18 9 9 0 000 18zM12 7v5l3 2",
  at: "M16 12a4 4 0 10-1.2 2.85M16 8v5a2.5 2.5 0 005 0v-1a9 9 0 10-3.5 7.1",
  car: "M5 16v3M19 16v3M3 16h18v-4l-2-5H5l-2 5zM3 12h18M7 14h1M16 14h1",
  // moto e bike: traço provisório na mesma grade, até entrarem no bundle do design system
  moto: "M5 19a3 3 0 100-6 3 3 0 000 6zM19 19a3 3 0 100-6 3 3 0 000 6zM5 16h5.5l3-5H17l2 5M9 11h4.5M15 7h2.5l1.5 4",
  bike: "M5.5 19.5a3.5 3.5 0 100-7 3.5 3.5 0 000 7zM18.5 19.5a3.5 3.5 0 100-7 3.5 3.5 0 000 7zM5.5 16L9 9h6.5l3 7M9 9l3.5 7h-7M7.5 6.5h3M15.5 9l-1-3H17",
} as const;

export type IconName = keyof typeof caminhos;

type Props = {
  name: IconName;
  size?: number;
  /** Sem `color`, usa `ink` do tema (no web o DS herda do texto; aqui o pai passa a cor). */
  color?: string;
  /** Só a estrela usa preenchido. */
  filled?: boolean;
  /** Texto para o leitor de tela; sem ele o ícone é decorativo. */
  label?: string;
};

export function Icon({ name, size = tamanhoIcone.padrao, color, filled = false, label }: Props) {
  const { c } = useCores();
  const cor = color ?? c.ink;
  return (
    <Svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill={filled ? cor : "none"}
      stroke={cor}
      strokeWidth={1.8}
      strokeLinecap="round"
      strokeLinejoin="round"
      // Só com label: no web essas props vão direto para o <svg> e o React reclama.
      {...(label
        ? { accessible: true, accessibilityRole: "image" as const, accessibilityLabel: label }
        : { "aria-hidden": true })}
    >
      <Path d={caminhos[name]} />
    </Svg>
  );
}
