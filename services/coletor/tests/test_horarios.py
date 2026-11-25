"""Issue #28 (HU11): o horário de hoje de um lugar, no fuso do lugar."""
from datetime import datetime, timezone

from app import horarios

GOOGLE = {"segunda-feira": ["11:00–15:00", "18:00–23:00"], "terça-feira": ["Fechado"],
          "domingo": ["Atendimento 24 horas"]}


def utc(dia: int, hora: int, minuto: int = 0) -> datetime:
    """Um instante em UTC em novembro de 2026; o dia 23 é uma segunda-feira."""
    return datetime(2026, 11, dia, hora, minuto, tzinfo=timezone.utc)


def test_faixas_do_dia_do_google():
    assert horarios.de_hoje(GOOGLE, "SP", utc(23, 15)) == ["11:00–15:00", "18:00–23:00"]


def test_o_dia_vira_no_fuso_do_lugar():
    # 03:30 UTC de terça: já é terça em São Paulo (00:30), ainda é segunda em Manaus (23:30).
    assert horarios.de_hoje(GOOGLE, "SP", utc(24, 3, 30)) == []
    assert horarios.de_hoje(GOOGLE, "AM", utc(24, 3, 30)) == ["11:00–15:00", "18:00–23:00"]
    # No Acre (UTC-5), 04:30 UTC de terça ainda é segunda.
    assert horarios.de_hoje(GOOGLE, "AC", utc(24, 4, 30)) == ["11:00–15:00", "18:00–23:00"]


def test_faixas_saem_no_mesmo_formato_qualquer_que_seja_a_escrita():
    escritas = {"segunda-feira": ["8:00\u2009–\u200912:00", "13:30 - 18:00"], "domingo": ["Atendimento 24 horas"],
                "sábado": ["Open 24 hours"]}
    assert horarios.de_hoje(escritas, "PR", utc(23, 15)) == ["08:00–12:00", "13:30–18:00"]
    assert horarios.de_hoje(escritas, "PR", utc(29, 15)) == ["00:00–24:00"]
    assert horarios.de_hoje(escritas, "PR", utc(28, 15)) == ["00:00–24:00"]


def test_dias_em_ingles_do_gosom():
    assert horarios.de_hoje({"Monday": ["11:30–23:00"], "Tuesday": ["Closed"]}, "SC", utc(23, 15)) == ["11:30–23:00"]
    assert horarios.de_hoje({"Monday": ["11:30–23:00"], "Tuesday": ["Closed"]}, "SC", utc(24, 15)) == []


def test_sem_horario_do_dia_nao_se_sabe():
    assert horarios.de_hoje(None, "SP", utc(23, 15)) is None
    assert horarios.de_hoje({"terça-feira": ["9:00–18:00"]}, "SP", utc(23, 15)) is None
    assert horarios.de_hoje("um texto qualquer", "SP", utc(23, 15)) is None


def test_opening_hours_do_openstreetmap():
    osm = "Mo-Fr 08:00-18:00; Sa 08:00-12:00,14:00-17:00; Su off"
    assert horarios.de_hoje(osm, "RS", utc(25, 15)) == ["08:00–18:00"]
    assert horarios.de_hoje(osm, "RS", utc(28, 15)) == ["08:00–12:00", "14:00–17:00"]
    assert horarios.de_hoje(osm, "RS", utc(29, 15)) == []
    assert horarios.de_hoje("24/7", "RS", utc(29, 15)) == ["00:00–24:00"]
    assert horarios.de_hoje("Fr-Mo 18:00-02:00", "RS", utc(23, 15)) == ["18:00–02:00"]
    # Regra que o leitor simples não entende (feriado, mês) não vira horário inventado.
    assert horarios.de_hoje("Mo-Fr 08:00-18:00; PH off", "RS", utc(23, 15)) is None
    assert horarios.de_hoje("Tu 10:00-12:00", "RS", utc(23, 15)) is None


def test_dia_com_texto_em_vez_de_lista():
    assert horarios.de_hoje({"segunda-feira": "8:00–18:00"}, "SP", utc(23, 15)) == ["08:00–18:00"]
    assert horarios.de_hoje({"segunda-feira": None}, "SP", utc(23, 15)) == []
