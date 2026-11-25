"""Issue #95: roteiro com dias, limite de horas ao volante, pernoite e conferência da resposta da IA."""
import asyncio

from app import horarios, ia, roteiro


def _lugar(i, horas, categoria="turismo", km=None, **extra):
    return {"id": f"l{i}", "nome": f"Lugar {i}", "categoria": categoria, "horas_desde_saida": horas,
            "km_na_rota": km if km is not None else horas * 80, **extra}


def _agenda(itens, **kw):
    return [(c["id"], c["dia"], c.get("chegada"), c["pernoite"]) for c in roteiro.agendar(itens, **kw)]


# ---------- horário de funcionamento ----------

def test_aberto_pelo_horario_do_google_e_do_osm():
    google = {"Segunda-feira": ["10:00–14:00"], "Sábado": ["Fechado"], "Domingo": ["18:00–02:00"]}
    assert horarios.aberto(google, 12 * 60, dia=0) is True
    assert horarios.aberto(google, 17 * 60 + 24, dia=0) is False  # o "jantar" das 17h24 do caso medido
    assert horarios.aberto(google, 12 * 60, dia=5) is False
    assert horarios.aberto(google, 23 * 60, dia=6) is True and horarios.aberto(google, 60, dia=6) is True
    assert horarios.aberto(google, 12 * 60, dia=2) is None  # quarta não veio
    assert horarios.aberto("Mo-Su 10:00-14:00", 17 * 60) is False  # sem data: fechado todo dia nessa hora
    assert horarios.aberto("Mo-Fr 10:00-14:00; Sa 18:00-23:00", 19 * 60) is True  # sem data: algum dia abre
    assert horarios.aberto("24/7", 3 * 60) is True
    assert horarios.aberto(None, 600) is None and horarios.aberto({"Segunda": ["com reserva"]}, 600, dia=0) is None


# ---------- agenda sem IA ----------

def test_dias_com_limite_de_horas_ao_volante_e_pernoite():
    """Caso medido: 38 h seguidas de estrada. Agora cada dia tem até 9 h ao volante, de carro."""
    itens = [_lugar(1, 2), _lugar(2, 7, "restaurante"), _lugar(3, 12), _lugar(4, 20), _lugar(5, 38)]
    agenda = roteiro.agendar(itens, "07:00", "carro")
    assert [(c["id"], c["dia"], c["chegada"], c["pernoite"]) for c in agenda] == [
        ("l1", 1, "09:00", False), ("l2", 1, "15:00", True),  # 9:00 + 1 h no l1 + 5 h; dorme no l2
        ("l3", 2, "12:00", True),  # as 8 h até o l4 não cabem nas 4 h que sobram
        ("l4", 3, "15:00", True),
        ("l5", 5, "16:00", False),  # 18 h: um dia só de estrada (9 h) e mais 9 h no dia 5
    ]
    for dia in {c["dia"] for c in agenda}:
        assert all(roteiro.minutos(c["chegada"]) <= roteiro.FIM_DO_DIA for c in agenda if c["dia"] == dia)


def test_bicicleta_roda_menos_horas_por_dia():
    itens = [_lugar(1, 5), _lugar(2, 9)]
    assert _agenda(itens, saida="07:00", veiculo="bicicleta") == [("l1", 1, "12:00", True), ("l2", 2, "11:00", False)]
    assert _agenda(itens, saida="07:00", veiculo="carro") == [("l1", 1, "12:00", False), ("l2", 1, "17:00", False)]


def test_ninguem_chega_depois_das_22h():
    itens = [_lugar(1, 1), _lugar(2, 2)]
    assert _agenda(itens, saida="20:00") == [("l1", 1, "21:00", True), ("l2", 2, "09:00", False)]
    assert _agenda([_lugar(1, 1)], saida="23:00") == [("l1", 2, "09:00", False)]


def test_sem_saida_tem_dias_mas_nao_tem_chegada():
    assert _agenda([_lugar(1, 5), _lugar(2, 12)]) == [("l1", 1, None, True), ("l2", 2, None, False)]


def test_aberto_na_chegada_usa_o_dia_da_semana_da_data():
    fecha_domingo = {"Sábado": ["08:00–18:00"], "Domingo": ["Fechado"]}
    itens = [_lugar(1, 3, horarios=fecha_domingo), _lugar(2, 12, horarios=fecha_domingo)]
    # sai num sábado (2026-11-28): o l2 cai no domingo, fechado
    agenda = roteiro.agendar(itens, "07:00", data="2026-11-28")
    assert [(c["dia"], c["aberto_na_chegada"]) for c in agenda] == [(1, True), (2, False)]


# ---------- conferência da resposta da IA ----------

def _rodar(itens, contexto, resposta):
    pedidos = []

    async def falso(client, **kw):
        pedidos.append(kw)
        return resposta
    original = ia.chamar_json
    ia.chamar_json = falso
    try:
        return asyncio.run(ia.ajustar_roteiro(None, itens, contexto)), pedidos
    finally:
        ia.chamar_json = original


def test_jantar_em_lugar_fechado_e_madrugada_sao_trocados_pela_agenda():
    """Caso medido: "jantar" às 17h24 num restaurante que abre das 10h às 14h, e piscina "na madrugada"."""
    almoco = {"Segunda-feira": ["10:00–14:00"], "Terça-feira": ["10:00–14:00"]}
    itens = [_lugar(1, 4.4, "restaurante", horarios=almoco), _lugar(2, 6.4, "restaurante", horarios=almoco),
             _lugar(3, 8, "natureza")]
    resposta = {"ordem": [{"id": "l1", "porque": "Almoço no caminho, perto do meio-dia."},
                          {"id": "l2", "porque": "Jantar caprichado antes do pernoite."},
                          {"id": "l3", "porque": "Piscina natural para um mergulho na madrugada."}]}
    r, pedidos = _rodar(itens, {"saida": "07:00", "data": "2026-11-23"}, resposta)  # segunda
    assert r["fonte"] == "ia"
    chegadas = {c["id"]: c["chegada"] for c in r["itens"]}
    assert chegadas == {"l1": "11:24", "l2": "14:24", "l3": "17:00"}
    assert r["explicacoes"]["l1"] == "Almoço no caminho, perto do meio-dia."  # 11h24, aberto
    assert "fechado" in r["explicacoes"]["l2"] and "14:24" in r["explicacoes"]["l2"]
    assert "madrugada" not in r["explicacoes"].get("l3", "")
    lugares = pedidos[0]["dados"]["lugares"]
    assert lugares[1]["aberto_na_chegada"] is False and pedidos[0]["dados"]["horas_volante_por_dia"] == 9
    assert "pernoite" in pedidos[0]["sistema"] and "horas_volante_por_dia" in pedidos[0]["sistema"]


def test_explicacao_que_diz_fechado_continua():
    itens = [_lugar(1, 10.5, "restaurante", horarios="Mo-Su 10:00-14:00")]
    r, _ = _rodar(itens, {"saida": "07:00"}, {"ordem": [{"id": "l1", "porque": "Vai estar fechado; passe direto."}]})
    assert r["explicacoes"] == {"l1": "Vai estar fechado; passe direto."}


def test_ordem_da_ia_que_volta_na_estrada_vira_a_ordem_do_km():
    itens = [_lugar(1, 1, km=50), _lugar(2, 2, km=150), _lugar(3, 3, km=250)]
    resposta = {"ordem": [{"id": "l3", "porque": "Mirante"}, {"id": "l1", "porque": "Praça"},
                          {"id": "l2", "porque": "Museu"}]}
    r, _ = _rodar(itens, {"saida": "07:00"}, resposta)
    assert [c["id"] for c in r["itens"]] == ["l1", "l2", "l3"]
    assert r["explicacoes"] == {"l3": "Mirante", "l1": "Praça", "l2": "Museu"}


def test_troca_pequena_da_ia_vale_e_a_agenda_e_refeita():
    itens = [_lugar(1, 4, "turismo", km=300), _lugar(2, 4.2, "restaurante", km=315)]
    resposta = {"ordem": [{"id": "l2", "porque": "Almoço antes do passeio."}, {"id": "l1", "porque": "Passeio."}]}
    r, _ = _rodar(itens, {"saida": "07:00"}, resposta)
    assert [(c["id"], c["chegada"]) for c in r["itens"]] == [("l2", "11:12"), ("l1", "12:24")]
    assert r["explicacoes"]["l2"] == "Almoço antes do passeio."


def test_plano_b_tem_a_agenda_e_avisa_fechado_e_pernoite():
    itens = [_lugar(1, 8, "restaurante", horarios="Mo-Su 10:00-14:00"), _lugar(2, 15)]

    async def falha(client, **kw):
        raise ia.IAIndisponivel("fora do ar")
    original = ia.chamar_json
    ia.chamar_json = falha
    try:
        r = asyncio.run(ia.ajustar_roteiro(None, itens, {"saida": "07:00"}, "moto"))
    finally:
        ia.chamar_json = original
    assert r["fonte"] == "geometria"
    assert [(c["id"], c["dia"], c["chegada"], c["pernoite"]) for c in r["itens"]] == [
        ("l1", 1, "15:00", True), ("l2", 2, "14:00", False)]
    assert "fechado" in r["explicacoes"]["l1"] and "Pernoite" in r["explicacoes"]["l1"]
    assert "l2" not in r["explicacoes"]
