// Formatos das respostas do coletor (services/coletor/README.md, seção Endpoints).
// Os nomes dos campos seguem a API, em snake_case, para não traduzir no meio do caminho.

export type Veiculo = "carro" | "moto" | "bicicleta";
export type CategoriaLugar = "turismo" | "restaurante" | "posto" | "natureza" | "hospedagem";
export type StatusViagem = "buscando" | "pronta" | "falhou";
export type StatusJob = "pendente" | "rodando" | "pronto" | "falhou";
export type TipoParada = "parada" | "destino" | "estadia";
export type TipoDecisao = "bora" | "passo" | "favorito";

/** Card de um lugar como o coletor devolve. Só o id é garantido; o resto depende da fonte. */
export type Card = {
  id: string;
  fonte?: string;
  nome?: string;
  categoria?: CategoriaLugar;
  tipo?: string | null;
  descricao?: string | null;
  cidade?: string;
  uf?: string | null;
  lat?: number | null;
  lon?: number | null;
  foto?: string | null;
  fotos?: string[];
  nota?: number | null;
  avaliacoes?: number | null;
  faixa_preco?: string | null;
  instagram?: string | null;
  /** `site` é confiável; `busca` foi achado na web e aparece como "provável". */
  instagram_origem?: "site" | "busca" | null;
  km_na_rota?: number | null;
  horas_desde_saida?: number | null;
  link_maps?: string | null;
};

export type Parada = {
  ordem: number;
  nome: string;
  uf: string | null;
  tipo: TipoParada;
  km_na_rota: number | null;
  horas_desde_saida?: number | null;
  cards: Card[];
};

/** Parada de `GET /viagens/{id}`: os cards já avaliados não vêm, mas o progresso conta todos. */
export type ParadaDaViagem = Parada & {
  /** Bora ou Favorito sobre todos os cards da parada: o "3 de 12". */
  progresso: { aceitos: number; total: number };
};

export type NovaViagem = {
  origem: string;
  destino: string;
  veiculo?: Veiculo;
  intervalo_km: number;
  categorias?: CategoriaLugar[];
  por_categoria?: number;
  usar_google_maps?: boolean;
  buscar_instagram?: boolean;
};

export type ViagemCriada = { job_id: string; viagem_id: string; status: StatusJob };

export type ResumoViagem = {
  id: string;
  origem: string;
  destino: string;
  veiculo: Veiculo;
  intervalo_km: number;
  categorias: CategoriaLugar[];
  status: StatusViagem;
  job_id: string | null;
  criado_em: string;
  atualizado_em: string;
  /** Cards da viagem já avaliados pela pessoa. */
  progresso: { decididos: number; total: number };
};

export type Viagem = ResumoViagem & {
  /** Pares [lat, lon] da rota. */
  polilinha: [number, number][] | null;
  paradas: ParadaDaViagem[];
};

export type Cidade = { nome: string; uf: string; rotulo: string; lat: number; lon: number; codigo_ibge: string };

export type EtapaBusca = "rota" | "cidades" | "lugares" | "instagram";

export type ResultadoBusca = { paradas: Parada[] };

export type Job = {
  id: string;
  tipo: string;
  status: StatusJob;
  resultado: ResultadoBusca | null;
  erro: string | null;
  criado_em: string;
  atualizado_em: string;
  progresso: { etapa: EtapaBusca; titulo: string; detalhe: string; percentual: number } | null;
  /** Paradas só com cards do OpenStreetMap, antes do Google chegar. */
  parcial: ResultadoBusca | null;
};

type TaxaAceite = Record<string, { aceitos: number; vistos: number; taxa: number }>;

export type PerfilGosto = {
  total_swipes: number;
  aceitos: number;
  nota_media_aceitos: number | null;
  categoria: TaxaAceite;
  tipo: TaxaAceite;
  faixa_preco: TaxaAceite;
  /** O que a IA entendeu da triagem, ou o que a pessoa corrigiu; null sem triagem concluída. */
  resumo: string | null;
  respostas: RespostaTriagem[];
  pulou: boolean;
  tema: EscolhaTema;
  /** Distância padrão entre paradas; null enquanto a pessoa não escolheu. */
  intervalo_km: number | null;
};

/** O tema que a pessoa escolhe no perfil; "sistema" segue o aparelho. */
export type EscolhaTema = "claro" | "escuro" | "sistema";

/** O que o PATCH /perfil grava; só as chaves enviadas mudam. Resumo vazio apaga. */
export type AjustePerfil = Partial<{ tema: EscolhaTema; intervalo_km: number; resumo: string }>;

export type RespostaTriagem = { pergunta: string; resposta: string };

export type PassoTriagem = {
  pergunta: string | null;
  opcoes: string[];
  /** A pessoa pode marcar mais de uma opção; sem ele, um toque responde. */
  multi: boolean;
  /** A última pergunta: a pessoa escreve a resposta, e as opções são sugestões. */
  livre: boolean;
  fim: boolean;
  resumo: string | null;
  fonte: "ia" | "fixa";
};

export type PedidoRoteiro = {
  cards: Card[];
  usar_ia?: boolean;
  contexto?: Record<string, unknown>;
};

/** O que a IA usa para ajustar o roteiro da viagem ao horário. */
export type ContextoRoteiro = {
  /** Hora de saída, "HH:MM". */
  saida?: string;
  /** Dias de viagem, de 1 em diante. */
  dias?: number;
};

export type PedidoRoteiroDaViagem = {
  usar_ia?: boolean;
  contexto?: ContextoRoteiro;
};

export type Roteiro = {
  itens: Card[];
  /** Por id do card, quando a IA ajustou o roteiro. */
  explicacoes: Record<string, string>;
  /** "pessoa" depois que ela reordena ou tira lugares: a ordem dela, sem IA. */
  fonte: "ia" | "geometria" | "pessoa";
};

export type ContaApagada = { dados: "apagados"; conta: "apagada" | "pendente" };
