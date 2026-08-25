"""
main.py

Ponto de entrada do bot. Orquestra o fluxo completo:

    scraper (Selenium)  →  parser (BeautifulSoup)  →  formatter (texto)  →  notifier (Telegram)

Este módulo NÃO tem lógica própria de scraping/parsing/formatação/envio —
só chama, na ordem certa, as funções que já foram validadas isoladamente
nos outros módulos.

Regras de destino atuais:
    - RU ICA: NÃO é processado (fica de fora do fluxo inteiro).
    - RU Saúde e Direito: enviado SÓ para uma conversa separada
      (TELEGRAM_CHAT_ID_SAUDE_DIREITO), não vai para o grupo.
    - Demais restaurantes (Setorial I e II): enviados só para o grupo
      (TELEGRAM_CHAT_ID, destino padrão).

Local esperado deste arquivo no projeto:
    src/bandeco_alert/main.py
"""

import os
import time

from dotenv import load_dotenv

from bandeco_alert.formatter import formatar_mensagem
from bandeco_alert.notifier.telegram import enviar_mensagem_multiplos_destinos
from bandeco_alert.parser import parse_cardapio_completo
from bandeco_alert.scraper import RESTAURANTES, buscar_cardapio_completo

load_dotenv()

# Número de tentativas por restaurante antes de desistir. Falhas do tipo
# "Chrome travou/não respondeu" costumam ser passageiras (instabilidade
# do runner do GitHub Actions), então vale tentar de novo antes de
# marcar como erro definitivo.
MAX_TENTATIVAS = 3
SEGUNDOS_ENTRE_TENTATIVAS = 10

# Restaurantes que NÃO devem ser processados.
RESTAURANTES_EXCLUIDOS = {"RU ICA"}

# Chat_id da conversa separada onde o Saúde e Direito deve ser enviado.
TELEGRAM_CHAT_ID_SAUDE_DIREITO = os.getenv("TELEGRAM_CHAT_ID_SAUDE_DIREITO")

# Mapeamento explícito de destinos por restaurante. Se um restaurante NÃO
# aparecer aqui, ele cai no comportamento padrão: só o grupo principal
# (TELEGRAM_CHAT_ID do .env).
#
# "RU Saúde e Direito" é um caso especial: vai SÓ para a conversa
# separada, sem passar pelo grupo — por isso o grupo (None) não entra
# nessa lista.
DESTINOS_POR_RESTAURANTE: dict[str, list[str]] = {}
if TELEGRAM_CHAT_ID_SAUDE_DIREITO:
    DESTINOS_POR_RESTAURANTE["RU Saúde e Direito"] = [TELEGRAM_CHAT_ID_SAUDE_DIREITO]


def _destinos_para(nome_restaurante: str) -> list[str | None]:
    """Monta a lista de chat_ids para onde a mensagem desse restaurante
    deve ir.

    - Se o restaurante tiver uma entrada em DESTINOS_POR_RESTAURANTE,
      usa EXATAMENTE essa lista (substitui o padrão, não soma).
    - Caso contrário, usa o destino padrão: só o grupo principal
      (chat_id=None faz enviar_mensagem() usar o TELEGRAM_CHAT_ID do .env).
    """
    if nome_restaurante in DESTINOS_POR_RESTAURANTE:
        return DESTINOS_POR_RESTAURANTE[nome_restaurante]
    return [None]  # None = usa TELEGRAM_CHAT_ID padrão (grupo)


def processar_restaurante(nome_restaurante: str, restaurante_value: str) -> None:
    """Executa o fluxo completo (buscar → parsear → formatar → enviar)
    para UM restaurante, mandando a mensagem para todos os destinos
    configurados para ele.
    """
    print(f"\n=== {nome_restaurante} ===")

    print("[1/4] Buscando cardápio...")
    htmls_por_refeicao = buscar_cardapio_completo(restaurante_value)

    print("[2/4] Extraindo dados do HTML...")
    cardapio = parse_cardapio_completo(htmls_por_refeicao)

    print("[3/4] Formatando mensagem...")
    mensagem = formatar_mensagem(nome_restaurante, cardapio)
    print(mensagem)  # útil para conferir no log do GitHub Actions depois

    destinos = _destinos_para(nome_restaurante)
    print(f"[4/4] Enviando para {len(destinos)} destino(s)...")
    enviar_mensagem_multiplos_destinos(mensagem, destinos)

    print(f"{nome_restaurante}: concluído com sucesso!")


def processar_restaurante_com_retry(nome_restaurante: str, restaurante_value: str) -> None:
    """Chama processar_restaurante() com retry automático.

    Tenta até MAX_TENTATIVAS vezes, com uma pequena pausa entre elas.
    Se todas as tentativas falharem, a última exceção é relançada —
    quem chama essa função (main()) decide o que fazer a partir daí.
    """
    for tentativa in range(1, MAX_TENTATIVAS + 1):
        try:
            processar_restaurante(nome_restaurante, restaurante_value)
            return  # sucesso, não precisa tentar de novo
        except Exception as erro:
            if tentativa == MAX_TENTATIVAS:
                raise  # última tentativa falhou, propaga o erro pra cima

            print(
                f"[AVISO] Tentativa {tentativa}/{MAX_TENTATIVAS} falhou para "
                f"{nome_restaurante}: {erro}. Tentando de novo em "
                f"{SEGUNDOS_ENTRE_TENTATIVAS}s..."
            )
            time.sleep(SEGUNDOS_ENTRE_TENTATIVAS)


def main() -> None:
    erros: list[str] = []

    restaurantes_a_processar = {
        nome: value
        for nome, value in RESTAURANTES.items()
        if nome not in RESTAURANTES_EXCLUIDOS
    }

    for nome_restaurante, restaurante_value in restaurantes_a_processar.items():
        try:
            processar_restaurante_com_retry(nome_restaurante, restaurante_value)
        except Exception as erro:
            # Não deixamos um restaurante com problema (ex: site fora do
            # ar naquele momento) derrubar o envio dos outros restaurantes.
            print(f"[ERRO] Falha ao processar {nome_restaurante} após {MAX_TENTATIVAS} tentativas: {erro}")
            erros.append(nome_restaurante)

    if erros:
        print(f"\nConcluído com falhas em: {', '.join(erros)}")
    else:
        print("\nConcluído com sucesso para todos os restaurantes!")


if __name__ == "__main__":
    main()