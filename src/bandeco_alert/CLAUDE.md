# CLAUDE.md

Este arquivo dá contexto ao Claude Code sobre o projeto `bandeco_alert`.

## O que é o projeto

Bot em Python que faz scraping diário do cardápio dos RUs da UFMG
(`fump.ufmg.br/cardapio-do-dia`) via Selenium e envia os dados formatados
para o Telegram. Ambiente de desenvolvimento: WSL (Ubuntu). Gerenciamento
de dependências: `uv`.

## Stack

- **Linguagem**: Python 3.13
- **Gerenciador de pacotes**: `uv` (nunca usar `pip install` direto — sempre `uv add`)
- **Web scraping**: Selenium (modo headless) + BeautifulSoup4 para parsing
- **Mensageria**: API do Telegram (via `requests`, sem SDK)
- **Automação de execução**: GitHub Actions (cron job) — ainda não implementado
- **Ambiente**: WSL (Linux)

## Estrutura do projeto

```
bandeco_alert/
├── src/bandeco_alert/
│   ├── scraper.py       # Selenium: abre o site, preenche formulário, devolve HTML bruto
│   ├── parser.py         # BeautifulSoup: extrai categorias/itens do HTML
│   ├── formatter.py      # Monta o texto final da mensagem (Markdown do Telegram)
│   ├── notifier/
│   │   ├── telegram.py   # Envia mensagens via API do Telegram
│   │   └── whatsapp.py   # NÃO IMPLEMENTADO — planejado, nunca escrito
│   └── main.py            # Orquestra o fluxo completo (scraper → parser → formatter → notifier)
├── tests/                 # Arquivos existem mas estão VAZIOS — nunca foram escritos
│   ├── test_scraper.py
│   ├── test_parser.py
│   └── test_formatter.py
├── .env                   # Não versionado — credenciais locais
├── .env.example           # Versionado — mostra quais variáveis existem, sem valores
├── pyproject.toml
└── uv.lock
```

## Comandos

```bash
# Instalar dependências
uv add <pacote>

# Rodar um módulo específico (scraper, parser, formatter isolados)
uv run python src/bandeco_alert/scraper.py

# Rodar o fluxo completo (main.py usa imports absolutos, precisa de -m)
uv run python -m bandeco_alert.main

# Rodar testes (quando existirem)
uv run pytest
```

## Variáveis de ambiente (`.env`)

```
TELEGRAM_BOT_TOKEN=<token do bot, criado via @BotFather>
TELEGRAM_CHAT_ID=<chat_id do grupo principal>
TELEGRAM_CHAT_ID_SAUDE_DIREITO=<chat_id de uma conversa individual separada>
```

## Fluxo de dados

```
scraper.buscar_cardapio_completo(restaurante_value)
  → dict[str, str]                          # HTML por refeição: "Almoço" / "Jantar"

parser.parse_cardapio_completo(htmls)
  → dict[str, dict[str, list[str]]]         # refeição → categoria → itens

formatter.formatar_mensagem(nome_restaurante, cardapio)
  → str                                      # texto pronto, Markdown do Telegram

notifier.telegram.enviar_mensagem_multiplos_destinos(texto, chat_ids)
  → envia para cada destino; erros parciais são coletados, não interrompem os demais
```

## Regras de negócio (em `main.py`)

`RESTAURANTES` (definido em `scraper.py`) tem 4 opções: RU Setorial I, RU
Setorial II, RU ICA, RU Saúde e Direito. As regras de destino ficam em
`DESTINOS_POR_RESTAURANTE` dentro de `main.py`:

- **RU ICA**: excluído do processamento inteiro (`RESTAURANTES_EXCLUIDOS`) —
  não busca, não parseia, não envia.
- **RU Saúde e Direito**: vai **só** para `TELEGRAM_CHAT_ID_SAUDE_DIREITO`
  (uma conversa individual), **não** vai para o grupo.
- **RU Setorial I e II**: vão só para o grupo (`TELEGRAM_CHAT_ID`, destino padrão).

Se mexer nessas regras, mantenha o padrão: se um restaurante não está em
`DESTINOS_POR_RESTAURANTE`, ele cai no destino padrão (só grupo). Se está,
a lista ali **substitui** o padrão, não soma.

## Decisões técnicas — não mudar sem motivo forte

Essas soluções vieram de bugs reais já debugados. Documentando o "porquê"
para evitar reintroduzir os mesmos problemas:

1. **Botão "Consultar Cardápio" via XPath por texto**, nunca por seletor
   genérico `button[type='submit']`. A página tem outro botão de submit
   no cabeçalho (busca do site) que aparece antes no DOM e é encontrado
   por engano por seletores genéricos, causando envio de busca vazia em
   vez de consulta ao cardápio.

2. **`<select id="restaurante">` carrega as `<option>` via JS depois do
   `<select>` já existir no DOM.** Sempre esperar uma `<option>`
   específica aparecer (`#restaurante option[value='...']`), nunca só o
   `<select>` em si — senão o Selenium tenta selecionar antes das opções
   existirem.

3. **Banner de cookies (CookieYes) é dispensado no início de cada busca**
   (`_dispensar_banner_cookies` em `scraper.py`), de forma silenciosa
   (não é erro se ele não aparecer).

4. **Clique no botão de submit usa `execute_script("arguments[0].click()")`**
   (clique via JS), não `.click()` nativo do Selenium — evita
   inconsistência causada por overlays/animações na página.

5. **Datas sempre no fuso `America/Sao_Paulo`** (`zoneinfo`), nunca UTC
   puro — importante porque o GitHub Actions roda em UTC e Brasília é
   UTC-3.

6. **Mensagens do Telegram usam `parse_mode="Markdown"`.** Cuidado com
   underscore (`_`) solto no texto (não em par) — quebra o parser de
   entidades do Telegram com erro 400. Nomes de pratos vindos do site
   podem eventualmente ter caracteres especiais; se isso virar problema,
   considerar escapar ou migrar para `parse_mode="HTML"`.

7. **"Sem cardápio disponível" é tratado como resultado válido**, não
   como erro — alguns RUs não servem todas as refeições em todos os
   dias. Ver `_formatar_refeicao` em `formatter.py`.

## O que falta implementar

1. **Testes** (`tests/*.py`) — arquivos existem mas estão vazios. Usar
   `pytest`. Prioridade: `parser.py` e `formatter.py` são os mais fáceis
   de testar isoladamente (sem precisar de navegador). `scraper.py`
   precisaria de mocks do Selenium ou HTML fixo salvo em disco.

2. **GitHub Actions** (`.github/workflows/daily_scrape.yml`) — automação
   com cron job diário. Precisa:
   - Instalar Chrome/Chromedriver no runner (ex: `browser-actions/setup-chrome`)
   - Configurar os 3 Secrets no GitHub (`Settings > Secrets and variables
     > Actions`): `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`,
     `TELEGRAM_CHAT_ID_SAUDE_DIREITO`
   - Cron ajustado pro fuso de Brasília (GitHub Actions usa UTC — calcular
     o deslocamento de -3h)

3. **`notifier/whatsapp.py`** — mencionado no requisito original (Twilio/
   WhatsApp Sandbox) mas nunca implementado. Hoje só existe Telegram.

4. **Possível otimização de performance**: `buscar_cardapio_completo`
   abre/fecha uma instância de Chrome por restaurante processado em
   `main.py`. Dá para reaproveitar um único navegador entre todos os
   restaurantes do loop, se o tempo de execução no CI for um problema.