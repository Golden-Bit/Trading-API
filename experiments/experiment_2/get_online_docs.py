import requests
from bs4 import BeautifulSoup
import re
import os
import sys
from urllib.parse import urljoin, urlparse

# Lista globale per le righe di debug (max 10)
debug_lines = []


def debug_print(msg):
    """
    Aggiunge un messaggio alla lista di debug e aggiorna l'output in console
    mostrando al massimo le ultime 10 righe (senza numerazione).
    """
    global debug_lines
    debug_lines.append(msg)
    if len(debug_lines) > 10:
        debug_lines.pop(0)
    for _ in range(len(debug_lines)):
        sys.stdout.write("\033[F")  # Sposta il cursore su di una riga
        sys.stdout.write("\033[K")  # Pulisce la riga corrente
    for line in debug_lines:
        print(line)
    sys.stdout.flush()


def extract_text_from_html(html, url=None):
    """
    Parsa l'HTML e restituisce il testo principale, preservando la formattazione
    dei blocchi di codice: i tag <pre> vengono racchiusi in triple backticks.
    """
    soup = BeautifulSoup(html, 'html.parser')

    # Gestione dei blocchi di codice: racchiude i contenuti dei tag <pre> in triple backticks.
    for pre in soup.find_all('pre'):
        content = pre.get_text()
        new_text = "\n```\n" + content + "\n```\n"
        pre.replace_with(new_text)

    # Rimuove tag non rilevanti
    for tag in soup(['script', 'style', 'header', 'footer', 'nav', 'aside']):
        tag.decompose()

    if url and any(keyword in url.lower() for keyword in ['experiments', 'documentation', 'readthedocs']):
        doc_container = soup.find('div', class_='document')
        if doc_container:
            text = doc_container.get_text(separator='\n')
        else:
            main_tag = soup.find('main_1.py')
            text = main_tag.get_text(separator='\n') if main_tag else (
                soup.body.get_text(separator='\n') if soup.body else soup.get_text(separator='\n'))
    else:
        main_tag = soup.find('main_1.py')
        text = main_tag.get_text(separator='\n') if main_tag else (
            soup.body.get_text(separator='\n') if soup.body else soup.get_text(separator='\n'))

    # Pulisce il testo eliminando spazi e righe multiple
    text = re.sub(r'\n\s*\n', '\n\n', text)
    return text.strip()


def safe_filename(url):
    """
    Genera un nome file sicuro a partire dal path dell'URL,
    sostituendo le slash (/) con trattini (-). Se il path è vuoto, usa 'index'.
    """
    parsed = urlparse(url)
    path = parsed.path
    if not path or path == "/":
        filename = "index"
    else:
        filename = path.strip("/").replace("/", "-")
    return filename + ".txt"


def save_text(text, url, output_dir):
    """
    Salva il testo estratto in un file, utilizzando come nome file il path modificato dell'URL.
    """
    filename = safe_filename(url)
    filepath = os.path.join(output_dir, filename)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(text)
    debug_print(f"Saved: {filepath}")


def crawl(url, root_url, output_dir, max_depth, base_depth, visited):
    """
    Esegue una scansione ricorsiva a partire dall'URL fornito, fino alla profondità massima.
    Segue solo i link che iniziano con 'root_url' e che rispettano la profondità,
    dove la profondità è definita come il numero di elementi in più nel path rispetto alla radice.
    """
    # Verifica che l'URL corrente inizi con il root_url
    if not url.startswith(root_url):
        return

    # Calcola la profondità del path rispetto alla radice
    candidate_depth = len([seg for seg in urlparse(url).path.split("/") if seg])
    if candidate_depth > base_depth + max_depth:
        return

    if url in visited:
        return
    visited.add(url)

    debug_print(f"Processing (extra depth {candidate_depth - base_depth}): {url}")

    try:
        response = requests.get(url)
        if response.status_code != 200:
            debug_print(f"Failed ({response.status_code}): {url}")
            return
        html = response.text
        text = extract_text_from_html(html, url)
        save_text(text, url, output_dir)
        soup = BeautifulSoup(html, 'html.parser')
        for a in soup.find_all('a', href=True):
            href = a['href']
            next_url = urljoin(url, href)
            # Segue solo link che iniziano con il root_url
            if not next_url.startswith(root_url) or '/#' in next_url:
                continue
            crawl(next_url, root_url, output_dir, max_depth, base_depth, visited)
    except Exception as e:
        debug_print(f"Error: {url} - {e}")


def main():
    # Impostazioni iniziali
    start_url = "https://www.backtrader.com/docu/"  # URL di partenza
    if not start_url.endswith("/"):
        start_url += "/"
    max_depth = 2  # Profondità massima: un elemento in più rispetto alla radice
    output_dir = "output_docs"  # Cartella di output per i file TXT
    os.makedirs(output_dir, exist_ok=True)

    # Calcola il numero di segmenti del path della radice
    base_depth = len([seg for seg in urlparse(start_url).path.split("/") if seg])
    visited = set()

    debug_print("Starting crawl...")
    crawl(start_url, start_url, output_dir, max_depth, base_depth, visited)
    debug_print("Crawl finished.")


if __name__ == '__main__':
    main()
