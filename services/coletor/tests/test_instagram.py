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


def test_instagram_da_agencia_no_rodape_do_site_e_descartado():
    # caso real (Uruguaiana, 25/11): o site da churrascaria só cita o Instagram de quem fez o site
    assert not instagram.combina_com_o_lugar("visualhuman_studio", "Churrascaria e Restaurante Prodócimo",
                                             "http://www.churrascariaprodocimo.com.br/")


def test_instagram_do_site_que_combina_pelo_nome_ou_pelo_dominio():
    assert instagram.combina_com_o_lugar("prodocimo.uruguaiana", "Churrascaria e Restaurante Prodócimo")
    assert instagram.combina_com_o_lugar("churrascariaprodocimo", "Prodócimo", "http://churrascariaprodocimo.com.br")
    assert instagram.combina_com_o_lugar("cantinanono", "Cantina", "https://www.cantinanono.com.br/menu")


def test_do_site_escolhe_o_perfil_do_lugar_entre_varios():
    import asyncio

    import httpx

    html = ('<a href="https://instagram.com/visualhuman_studio">site por</a>'
            '<a href="https://www.instagram.com/prodocimo_churrascaria/">siga</a>')
    cliente = httpx.AsyncClient(transport=httpx.MockTransport(lambda req: httpx.Response(200, text=html)))
    url = "http://www.churrascariaprodocimo.com.br/"
    assert asyncio.run(instagram.do_site(cliente, url, "Churrascaria Prodócimo")) == "prodocimo_churrascaria"
    so_agencia = httpx.AsyncClient(transport=httpx.MockTransport(
        lambda req: httpx.Response(200, text='<a href="https://instagram.com/visualhuman_studio">x</a>')))
    assert asyncio.run(instagram.do_site(so_agencia, url, "Churrascaria Prodócimo")) is None
