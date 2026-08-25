"""
notifier/telegram.py

Responsável por enviar a mensagem final (já formatada pelo formatter.py)
para o Telegram, via API HTTP oficial do bot.

Este módulo NÃO sabe nada sobre scraping, parsing ou formatação — só
recebe uma string de texto pronta e a envia. Isso facilita testar
isoladamente (basta chamar enviar_mensagem("teste 123")).

Local esperado deste arquivo no projeto:
    src/bandeco_alert/notifier/telegram.py

Depende de:
    uv add python-dotenv requests

Variáveis de ambiente esperadas (ver .env.example):
    TELEGRAM_BOT_TOKEN
    TELEGRAM_CHAT_ID
"""

import os

import requests
from dotenv import load_dotenv

# Carrega as variáveis do .env para o ambiente. Só tem efeito localmente —
# no GitHub Actions, as variáveis já vêm do ambiente via Secrets, então
# essa chamada simplesmente não encontra nada pra carregar e não faz mal.
load_dotenv()

TELEGRAM_API_URL = "https://api.telegram.org/bot{token}/sendMessage"


class TelegramConfigError(Exception):
    """Erro levantado quando as variáveis de ambiente do Telegram
    não estão configuradas corretamente."""


def _obter_credenciais(chat_id: str | None) -> tuple[str, str]:
    """Lê o token do ambiente e resolve o chat_id a usar.

    Se `chat_id` for None, cai no TELEGRAM_CHAT_ID padrão do .env (o
    grupo principal) — é assim que main.py manda para o grupo sem
    precisar saber o chat_id dele. Levanta um erro claro (em vez de um
    KeyError genérico) se alguma credencial estiver faltando.
    """
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = chat_id or os.getenv("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        raise TelegramConfigError(
            "TELEGRAM_BOT_TOKEN e/ou TELEGRAM_CHAT_ID não encontrados. "
            "Verifique se o arquivo .env existe na raiz do projeto "
            "(ou se os Secrets estão configurados no GitHub Actions)."
        )

    return token, chat_id


def enviar_mensagem(texto: str, chat_id: str | None = None) -> None:
    """Envia uma mensagem de texto para um chat do Telegram.

    `chat_id=None` (padrão) envia para o TELEGRAM_CHAT_ID do .env (o
    grupo principal). Passar um chat_id explícito permite enviar para
    outro destino, como a conversa individual do RU Saúde e Direito.

    Usa parse_mode="Markdown" para que *negrito* e _itálico_ (produzidos
    pelo formatter.py) sejam renderizados corretamente.

    Levanta requests.HTTPError se a API do Telegram retornar um erro
    (ex: token inválido, chat_id incorreto, mensagem malformada).
    """
    token, chat_id = _obter_credenciais(chat_id)
    url = TELEGRAM_API_URL.format(token=token)

    payload = {
        "chat_id": chat_id,
        "text": texto,
        "parse_mode": "Markdown",
    }

    resposta = requests.post(url, json=payload, timeout=10)

    # Levanta uma exceção clara se o Telegram recusar a requisição
    # (ex: 400 Bad Request por Markdown malformado, 401 por token errado).
    # A API do Telegram manda uma descrição legível do erro no corpo da
    # resposta (ex: "can't find end of the entity starting at byte offset
    # 20") — incluímos isso na mensagem de erro, já que o texto genérico
    # do requests ("400 Client Error") sozinho não ajuda a debugar.
    if not resposta.ok:
        detalhe = resposta.json().get("description", resposta.text)
        raise RuntimeError(
            f"Telegram recusou a mensagem (HTTP {resposta.status_code}): {detalhe}"
        )

    corpo = resposta.json()
    if not corpo.get("ok"):
        raise RuntimeError(f"Telegram retornou ok=false: {corpo}")


def enviar_mensagem_multiplos_destinos(
    texto: str, chat_ids: list[str | None]
) -> list[str]:
    """Envia a mesma mensagem para vários destinos (ex: o grupo principal
    e uma conversa individual). Cada destino é enviado de forma
    independente: se um falhar (ex: chat_id inválido), os demais ainda
    são tentados, em vez de interromper o envio inteiro.

    Um item `None` na lista significa "grupo principal" (TELEGRAM_CHAT_ID
    do .env) — ver `enviar_mensagem`.

    Retorna a lista de destinos que falharam (vazia se todos tiverem
    sucesso), para quem chamar decidir o que fazer com isso (ex: logar,
    contar como erro parcial do restaurante em main.py).
    """
    falhas: list[str] = []
    for chat_id in chat_ids:
        destino = chat_id or "TELEGRAM_CHAT_ID (grupo padrão)"
        try:
            enviar_mensagem(texto, chat_id=chat_id)
        except Exception as erro:
            print(f"[ERRO] Falha ao enviar para {destino}: {erro}")
            falhas.append(destino)

    return falhas


if __name__ == "__main__":
    # Teste manual rápido: roda "uv run python src/bandeco_alert/notifier/telegram.py"
    # e confira se a mensagem chega no seu Telegram.
    # OBS: evite underscore "_" solto no texto de teste — no modo Markdown do
    # Telegram, "_" delimita itálico, e um underscore sozinho (sem par) faz
    # a API recusar a mensagem inteira com erro 400 Bad Request.
    enviar_mensagem("🤖 Teste do bandeco alert")
    print("Mensagem enviada com sucesso!")