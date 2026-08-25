"""
formatter.py

Responsável por transformar os dados já estruturados do cardápio
(dict devolvido pelo parser.py) em uma string de texto pronta pra
enviar no Telegram/WhatsApp.

Este módulo NÃO sabe nada sobre Selenium, HTML, nem sobre como a
mensagem vai ser enviada — só recebe dados em Python e devolve texto.
Isso facilita testar sem precisar rodar o scraper toda vez (basta
montar um dicionário de exemplo na mão).

Local esperado deste arquivo no projeto:
    src/bandeco_alert/formatter.py
"""

from datetime import datetime
from zoneinfo import ZoneInfo

# Tipo de entrada: mesmo formato devolvido por parser.parse_cardapio_completo
# Ex: {"Almoço": {"Entrada": [...], "Prato Principal": [...]}, "Jantar": {...}}
CardapioCompleto = dict[str, dict[str, list[str]]]

DIAS_SEMANA_PT = {
    "Monday": "segunda-feira",
    "Tuesday": "terça-feira",
    "Wednesday": "quarta-feira",
    "Thursday": "quinta-feira",
    "Friday": "sexta-feira",
    "Saturday": "sábado",
    "Sunday": "domingo",
}

# Emoji por refeição, só pra deixar a mensagem mais fácil de escanear
EMOJI_REFEICAO = {
    "Almoço": "☀️",
    "Jantar": "🌙",
}


def _data_hoje_formatada() -> str:
    """Retorna algo como "terça-feira, 25/08/2026" no fuso de Brasília."""
    hoje = datetime.now(ZoneInfo("America/Sao_Paulo"))
    dia_semana_pt = DIAS_SEMANA_PT[hoje.strftime("%A")]
    return f"{dia_semana_pt}, {hoje.strftime('%d/%m/%Y')}"


def _formatar_refeicao(refeicao: str, categorias: dict[str, list[str]]) -> str:
    """Monta o bloco de texto de UMA refeição (Almoço OU Jantar), com
    todas as suas categorias e itens.

    Se a refeição não tiver nenhuma categoria (dict vazio — ex: o RU não
    serve essa refeição hoje), devolve uma linha avisando isso, em vez
    de simplesmente omitir a refeição sem explicação.
    """
    emoji = EMOJI_REFEICAO.get(refeicao, "🍽️")
    linhas = [f"{emoji} *{refeicao}*"]

    if not categorias:
        linhas.append("_Não há cardápio disponível para esta refeição hoje._")
        return "\n".join(linhas)

    for categoria, itens in categorias.items():
        linhas.append(f"\n_{categoria}_")
        for item in itens:
            linhas.append(f"• {item}")

    return "\n".join(linhas)


def formatar_mensagem(restaurante: str, cardapio: CardapioCompleto) -> str:
    """Recebe o nome do restaurante e o dicionário completo (Almoço +
    Jantar, já parseado) e devolve o texto final pronto para envio.

    O formato usa marcação estilo Markdown (*negrito*, _itálico_), que
    é compatível tanto com o Telegram (parse_mode="Markdown") quanto,
    de forma similar, com o WhatsApp.
    """
    cabecalho = f"🍴 *Cardápio do dia* — {restaurante}\n {_data_hoje_formatada()}"

    blocos_refeicoes = [
        _formatar_refeicao(refeicao, categorias)
        for refeicao, categorias in cardapio.items()
    ]

    corpo = "\n\n".join(blocos_refeicoes)

    return f"{cabecalho}\n\n{corpo}"


if __name__ == "__main__":
    # Teste manual rápido: roda a pipeline completa
    # scraper.py -> parser.py -> formatter.py e imprime o resultado final.
    from bandeco_alert.scraper import buscar_cardapio_completo, RESTAURANTES
    from bandeco_alert.parser import parse_cardapio_completo

    nome_restaurante = "RU Saúde e Direito"
    htmls = buscar_cardapio_completo(RESTAURANTES[nome_restaurante])
    cardapio = parse_cardapio_completo(htmls)
    mensagem = formatar_mensagem(nome_restaurante, cardapio)

    print(mensagem)