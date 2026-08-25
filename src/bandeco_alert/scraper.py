"""
scraper.py

Responsável por interagir com o site da Fump (fump.ufmg.br/cardapio-do-dia)
via Selenium e devolver o HTML bruto da área de resultado do cardápio.

Este módulo NÃO faz parsing do conteúdo (isso é responsabilidade do parser.py) —
aqui a única preocupação é: abrir o site, preencher o formulário, submeter,
e devolver o HTML da seção de resultado.

Local esperado deste arquivo no projeto:
    src/bandeco_alert/scraper.py
"""

from datetime import datetime
from zoneinfo import ZoneInfo

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select, WebDriverWait

URL_CARDAPIO = "https://fump.ufmg.br/cardapio-do-dia/"

# Valores dos <option> do select#restaurante (ver HTML do site)
RESTAURANTES = {
    "RU Setorial II": "1",
    "RU Saúde e Direito": "2",
    "RU ICA": "5",
    "RU Setorial I": "6",
}

REFEICOES = ["Almoço", "Jantar"]

TIMEOUT_PADRAO = 15  # segundos de espera para WebDriverWait

# XPath do botão de submit do FORMULÁRIO DO CARDÁPIO.
# IMPORTANTE: não usar CSS_SELECTOR "button[type='submit']" sozinho —
# a página tem outro botão de submit no cabeçalho (busca do site), que
# vem antes no DOM e seria encontrado primeiro por engano.
XPATH_BOTAO_CONSULTAR = "//button[contains(text(), 'Consultar Cardápio')]"

# XPath do botão "Aceitar tudo" do banner de cookies (CookieYes).
# Esse banner reaparece a cada driver.get(), e mesmo quando não bloqueia
# fisicamente o clique, pode causar comportamento inconsistente entre
# execuções — então dispensamos ele logo no início, sempre.
XPATH_BOTAO_ACEITAR_COOKIES = "//button[@data-cky-tag='accept-button']"


def criar_driver() -> webdriver.Chrome:
    """Cria e configura uma instância headless do Chrome.

    Inclui flags extras (--disable-gpu, --disable-extensions,
    --disable-background-networking) para reduzir instabilidade em
    ambientes com recursos limitados, como runners do GitHub Actions,
    onde o Chrome headless às vezes trava/some sem erro claro.

    Também define um timeout explícito de carregamento de página
    (30s) — sem isso, se o Chrome travar de verdade, o Selenium só
    percebe depois de ~120s (timeout padrão da conexão HTTP local
    entre Selenium e ChromeDriver), o que deixa o diagnóstico bem
    mais lento e confuso.
    """
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-background-networking")

    driver = webdriver.Chrome(options=options)
    driver.set_page_load_timeout(30)
    return driver


def _data_hoje_iso() -> str:
    """Retorna a data de hoje (fuso de Brasília) no formato exigido
    pelo input HTML5 type="date": AAAA-MM-DD.
    """
    hoje = datetime.now(ZoneInfo("America/Sao_Paulo"))
    return hoje.strftime("%Y-%m-%d")


def _salvar_debug(driver: webdriver.Chrome, motivo: str) -> None:
    """Salva um screenshot e o HTML da página no momento da falha,
    pra facilitar investigar o que travou. Gera:
        debug_<motivo>.png
        debug_<motivo>.html
    na raiz de onde o script foi executado.
    """
    driver.save_screenshot(f"debug_{motivo}.png")
    with open(f"debug_{motivo}.html", "w", encoding="utf-8") as f:
        f.write(driver.page_source)
    print(f"[DEBUG] Screenshot e HTML salvos: debug_{motivo}.png / debug_{motivo}.html")


def _dispensar_banner_cookies(driver: webdriver.Chrome) -> None:
    """Clica em "Aceitar tudo" no banner de cookies, se ele estiver presente.
    Não é um erro se o banner não aparecer (ex: já foi dispensado antes
    nessa sessão) — por isso o try/except silencioso.
    """
    try:
        botao_cookies = WebDriverWait(driver, 3).until(
            EC.element_to_be_clickable((By.XPATH, XPATH_BOTAO_ACEITAR_COOKIES))
        )
        driver.execute_script("arguments[0].click();", botao_cookies)
    except Exception:
        pass  # banner não apareceu a tempo — segue o fluxo normalmente


def _preencher_e_submeter(driver: webdriver.Chrome, restaurante_value: str, refeicao: str) -> None:
    """Preenche o formulário do cardápio (restaurante, refeição e data de hoje)
    e clica em "Consultar Cardápio". Não retorna nada — quem chama essa função
    lê o driver.page_source depois, já com o resultado carregado.
    """
    driver.get(URL_CARDAPIO)
    _dispensar_banner_cookies(driver)

    # Restaurante
    # IMPORTANTE: o <select> já existe no DOM ao carregar a página, mas as
    # <option> dentro dele são preenchidas depois via JavaScript. Por isso
    # esperamos uma option específica aparecer, não só o select em si —
    # senão o Selenium tenta selecionar antes das opções existirem.
    WebDriverWait(driver, TIMEOUT_PADRAO).until(
        EC.presence_of_element_located(
            (By.CSS_SELECTOR, f"#restaurante option[value='{restaurante_value}']")
        )
    )
    select_restaurante = Select(driver.find_element(By.ID, "restaurante"))
    select_restaurante.select_by_value(restaurante_value)

    # Tipo de refeição
    select_refeicao = Select(driver.find_element(By.ID, "tipoRefeicao"))
    select_refeicao.select_by_value(refeicao)

    # Data (sempre hoje, fuso de Brasília)
    campo_data = driver.find_element(By.ID, "data")
    data_iso = _data_hoje_iso()
    driver.execute_script("arguments[0].value = arguments[1];", campo_data, data_iso)
    # setar .value via JS não aciona os listeners do formulário sozinho,
    # então disparamos os eventos manualmente (change E input, para cobrir
    # diferentes formas de validação/JS que o site possa usar)
    driver.execute_script("arguments[0].dispatchEvent(new Event('change'));", campo_data)
    driver.execute_script("arguments[0].dispatchEvent(new Event('input'));", campo_data)

    # Submeter — usa o texto do botão, NÃO type=submit genérico
    # (o cabeçalho do site tem outro botão de submit, o de busca).
    # Esperamos o botão ficar CLICÁVEL (não só presente), e clicamos via
    # JavaScript em vez de clique nativo — isso evita falhas causadas por
    # elementos sobrepostos (ex: banner de cookies, animações) que às
    # vezes causam comportamento inconsistente entre execuções.
    botao = WebDriverWait(driver, TIMEOUT_PADRAO).until(
        EC.element_to_be_clickable((By.XPATH, XPATH_BOTAO_CONSULTAR))
    )
    driver.execute_script("arguments[0].click();", botao)

    # Espera até o resultado ser preenchido de fato (não só existir vazio no DOM)
    try:
        WebDriverWait(driver, TIMEOUT_PADRAO).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "#resultado h3"))
        )
    except Exception:
        # DEBUG: se travou, salva screenshot + HTML antes de propagar o erro,
        # assim dá pra investigar exatamente o que a página estava mostrando.
        # Também checamos o título da página: se caiu na busca do site por
        # engano, isso aparece claro na mensagem de erro.
        _salvar_debug(driver, motivo=f"timeout_{refeicao}")
        titulo_atual = driver.title
        raise RuntimeError(
            f"Timeout esperando o resultado do cardápio ({refeicao}). "
            f"Título da página no momento da falha: '{titulo_atual}'. "
            f"Veja debug_timeout_{refeicao}.png / .html para mais detalhes."
        )


def buscar_html_cardapio(restaurante_value: str, refeicao: str) -> str:
    """Busca o HTML do resultado para UMA refeição (Almoço OU Jantar).
    Abre e fecha o navegador nessa única consulta.
    Útil para testes isolados ou quando você só precisa de uma refeição.
    """
    driver = criar_driver()
    try:
        _preencher_e_submeter(driver, restaurante_value, refeicao)
        resultado = driver.find_element(By.ID, "resultado")
        return resultado.get_attribute("outerHTML")
    finally:
        driver.quit()


def buscar_cardapio_completo(restaurante_value: str) -> dict[str, str]:
    """Busca o HTML do resultado para Almoço E Jantar, reaproveitando
    a mesma instância do navegador (evita abrir/fechar o Chrome duas vezes).

    Retorna um dicionário como:
        {
            "Almoço": "<div id='resultado'>...</div>",
            "Jantar": "<div id='resultado'>...</div>",
        }
    """
    driver = criar_driver()
    resultados: dict[str, str] = {}
    try:
        for refeicao in REFEICOES:
            _preencher_e_submeter(driver, restaurante_value, refeicao)
            resultado = driver.find_element(By.ID, "resultado")
            resultados[refeicao] = resultado.get_attribute("outerHTML")
    finally:
        driver.quit()

    return resultados


if __name__ == "__main__":
    # Teste manual rápido: roda pro RU Setorial II e imprime os dois HTMLs.
    # Se travar, vai gerar debug_timeout_<refeicao>.png e .html na raiz do projeto.
    restaurante_value = RESTAURANTES["RU Setorial II"]
    cardapios = buscar_cardapio_completo(restaurante_value)

    for refeicao, html in cardapios.items():
        print(f"\n===== {refeicao} =====")
        print(html[:1000])  # só o começo, pra não poluir o terminal