# bandeco-alert

Bot que faz scraping diário do cardápio dos Restaurantes Universitários (RUs)
da UFMG (`fump.ufmg.br/cardapio-do-dia`) e envia o resultado formatado para o
Telegram. Roda automaticamente todo dia via GitHub Actions.

## Como funciona

```
scraper (Selenium)  →  parser (BeautifulSoup)  →  formatter (texto)  →  notifier (Telegram)
```

1. **scraper.py** — abre o site com Selenium (headless), preenche o
   formulário e devolve o HTML bruto do cardápio de cada refeição.
2. **parser.py** — extrai categorias e itens do HTML com BeautifulSoup.
3. **formatter.py** — monta o texto final da mensagem (Markdown do
   Telegram).
4. **notifier/telegram.py** — envia a mensagem via API do Telegram.

`main.py` orquestra esse fluxo para cada restaurante e decide para onde
enviar cada mensagem.

### Regras de destino

- **RU ICA**: não é processado (fica de fora do fluxo inteiro).
- **RU Saúde e Direito**: enviado só para uma conversa separada
  (`TELEGRAM_CHAT_ID_SAUDE_DIREITO`), não vai para o grupo.
- **RU Setorial I e II**: enviados só para o grupo (`TELEGRAM_CHAT_ID`,
  destino padrão).

## Requisitos

- Python 3.13+
- [uv](https://docs.astral.sh/uv/) para gerenciar dependências
- Google Chrome (usado pelo Selenium)

## Instalação

```bash
uv sync
cp .env.example .env
# preencha .env com suas credenciais (ver abaixo)
```

## Variáveis de ambiente (`.env`)

```
TELEGRAM_BOT_TOKEN=<token do bot, criado via @BotFather>
TELEGRAM_CHAT_ID=<chat_id do grupo principal>
TELEGRAM_CHAT_ID_SAUDE_DIREITO=<chat_id de uma conversa individual separada>
```

## Uso

```bash
# Rodar o fluxo completo
uv run python -m bandeco_alert.main

# Rodar um módulo isolado (ex: scraper)
uv run python src/bandeco_alert/scraper.py

# Rodar os testes
uv run pytest
```

## Automação (GitHub Actions)

O workflow em `.github/workflows/daily_scrape.yml` roda todo dia às 10h
(horário de Brasília) e envia o cardápio automaticamente. Requer os
seguintes Secrets configurados em `Settings > Secrets and variables >
Actions`:

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`
- `TELEGRAM_CHAT_ID_SAUDE_DIREITO`

## Estrutura do projeto

```
bandeco_alert/
├── src/bandeco_alert/
│   ├── scraper.py         # Selenium: abre o site, preenche formulário, devolve HTML bruto
│   ├── parser.py          # BeautifulSoup: extrai categorias/itens do HTML
│   ├── formatter.py       # Monta o texto final da mensagem (Markdown do Telegram)
│   ├── notifier/
│   │   ├── telegram.py    # Envia mensagens via API do Telegram
│   │   └── whatsapp.py    # Não implementado
│   └── main.py            # Orquestra o fluxo completo
├── tests/
├── .env.example            # Modelo das variáveis de ambiente (sem valores)
└── .github/workflows/      # Automação via GitHub Actions
```
