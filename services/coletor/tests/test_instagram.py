from app import instagram


def r(handle, title, body=""):
    return {"href": f"https://www.instagram.com/{handle}/", "title": title, "body": body}


def test_cidade_no_texto_ganha_da_ordem():
    res = [r("cantina_nono", "Cantina do Nono (@cantina_nono)", "Canela, RS. Massas"),
           r("cantinadonono", "Cantina do Nono (@cantinadonono)", "Curitiba, PR. Massa caseira")]
    assert instagram.escolher_handle("Cantina do Nono", "Curitiba", res) == "cantinadonono"


def test_sem_cidade_vence_o_handle_mais_parecido():
    res = [r("cantinadononofilho", "Cantina do Nono Filho"),
           r("cantinadonono", "Cantina do Nono")]
    assert instagram.escolher_handle("Cantina do Nono", "Lages", res) == "cantinadonono"


def test_cidade_nao_salva_nome_diferente():
    # caso real do ddgs: "Cantina da Nona" é de Curitiba, mas não é a "Cantina do Nono"
    res = [r("cantinadonono", "Cantina do Nono (@cantinadonono)"),
           r("cantinadanona", "Cantina da Nona (@cantinadanona)", "Curitiba, PR")]
    assert instagram.escolher_handle("Cantina do Nono", "Curitiba", res) == "cantinadonono"


def test_nome_que_nao_bate_devolve_none():
    res = [r("nonnogastronomia", "Nonno Gastronomia"), r("p", "post qualquer")]
    assert instagram.escolher_handle("Churrascaria Gaúcha", "Lages", res) is None


def test_lista_vazia():
    assert instagram.escolher_handle("X", "Y", []) is None
