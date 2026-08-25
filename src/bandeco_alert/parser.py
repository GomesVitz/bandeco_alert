"""
parser.py

Responsável por transformar o HTML bruto devolvido pelo scraper.py
(a div#resultado da página do cardápio) em dados estruturados em Python.

Este módulo NÃO sabe nada sobre Selenium, requisições HTTP, nem sobre
como o texto final vai ser exibido — só recebe HTML como string e devolve
dicionários/listas. Isso facilita testar sem precisar abrir navegador
(basta ter um HTML de exemplo salvo em disco).

Local esperado deste arquivo no projeto:
    src/bandeco_alert/parser.py

Depende de BeautifulSoup4:
    uv add beautifulsoup4
"""

from bs4 import BeautifulSoup
from bandeco_alert.scraper import buscar_cardapio_completo, RESTAURANTES

# Tipo de retorno do parse de UMA refeição: categoria -> lista de itens
# Ex: {"Entrada": ["Salada de Almeirão", "Salada de Berinjela"], ...}
CardapioRefeicao = dict[str, list[str]]


def parse_cardapio_html(html: str) -> CardapioRefeicao:
    """Recebe o HTML da div#resultado (ou de qualquer HTML que contenha
    essa estrutura) e devolve um dicionário categoria -> itens.

    Estrutura esperada no HTML (uma div por categoria):
        <div>
            <h3>Prato Principal</h3>
            <p><img ...> Arroz Branco</p>
            <p><img ...> Feijão Carioca</p>
        </div>

    Cada <p> pode conter um <img> de ícone antes do texto — o ícone é
    ignorado, só o texto do prato é extraído.
    """
    soup = BeautifulSoup(html, "html.parser")
    cardapio: CardapioRefeicao = {}

    # Cada categoria é uma <div> cujo PRIMEIRO filho direto é um <h3>.
    # Não usamos seletor CSS ":has()" para manter compatibilidade com
    # versões mais antigas do BeautifulSoup/soupsieve.
    for div in soup.find_all("div"):
        titulo = div.find("h3", recursive=False)
        if titulo is None:
            continue  # essa div não é uma categoria de cardápio, pula

        categoria = titulo.get_text(strip=True)

        # Pega só os <p> que são filhos diretos dessa div (evita pegar
        # <p> de categorias aninhadas, caso a estrutura do site mude)
        itens = [
            p.get_text(strip=True)
            for p in div.find_all("p", recursive=False)
            if p.get_text(strip=True)  # ignora <p> vazios
        ]

        if itens:
            cardapio[categoria] = itens

    return cardapio


def parse_cardapio_completo(
    htmls_por_refeicao: dict[str, str | None],
) -> dict[str, CardapioRefeicao]:
    """Recebe o dicionário {"Almoço": html, "Jantar": html} (formato
    devolvido por scraper.buscar_cardapio_completo) e aplica o parse
    em cada um, devolvendo:

        {
            "Almoço": {"Entrada": [...], "Prato Principal": [...], ...},
            "Jantar": {"Entrada": [...], "Prato Principal": [...], ...},
        }

    Quando não há cardápio cadastrado para uma refeição, o scraper
    devolve None para ela — isso não é um erro, então tratamos como
    um cardápio vazio ({}) em vez de tentar fazer parse de None.
    """
    return {
        refeicao: parse_cardapio_html(html) if html is not None else {}
        for refeicao, html in htmls_por_refeicao.items()
    }


if __name__ == "__main__":
    # Teste manual rápido: busca o cardápio de verdade via scraper.py
    # (abre o navegador) e aplica o parse em cima do HTML retornado.
    htmls = buscar_cardapio_completo(RESTAURANTES["RU Saúde e Direito"])
    cardapio = parse_cardapio_completo(htmls)

    for refeicao, categorias in cardapio.items():
        print(f"\n===== {refeicao} =====")
        for categoria, itens in categorias.items():
            print(f"\n{categoria}:")
            for item in itens:
                print(f"  - {item}")