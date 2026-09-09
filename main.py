import os
import time
import threading
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
import requests
from bs4 import BeautifulSoup
from curl_cffi import requests as cffi_requests

DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")

SEARCH_QUERIES = [
    "Harry Kane Topps",
    "Kane Chrome UCC",
    "Igamane",
    "abde ezzalzouli auto",
    "Saibari RC",
    "Iphone"
]

seen_ebay = set()
seen_vinted = set()
is_first_run = True

def log(msg):
    print(msg, flush=True)

class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        self.wfile.write(b"Bot is running 24/7!")

    def log_message(self, format, *args):
        return

def start_web_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    server.serve_forever()

def send_to_discord(platform, query, title, price, link):
    if not DISCORD_WEBHOOK_URL:
        return
    payload = {
        "embeds": [
            {
                "title": f"🛒 [{platform}] {title[:200]}",
                "url": link,
                "color": 15082531 if "eBay" in platform else 3066993,
                "fields": [
                    {"name": "Suchbegriff", "value": query, "inline": True},
                    {"name": "Preis", "value": price, "inline": True}
                ]
            }
        ]
    }
    try:
        requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=5)
    except Exception as e:
        log(f"Discord Fehler: {e}")

def check_ebay_rss(query):
    global is_first_run
    try:
        encoded_query = urllib.parse.quote_plus(query)
        # Offizieller eBay-Neueste-Artikel RSS Feed
        url = f"https://www.ebay.de/sch/i.html?_nkw={encoded_query}&_sop=10&_rss=1"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code != 200:
            log(f"[eBay RSS] '{query}' HTTP Status: {res.status_code}")
            return

        soup = BeautifulSoup(res.text, "xml")
        items = soup.find_all("item")
        log(f"[eBay RSS] '{query}' Treffer: {len(items)}")

        sent_count = 0
        for item in items:
            title = item.find("title").text.strip() if item.find("title") else "Kein Titel"
            link = item.find("link").text.strip() if item.find("link") else ""
            link = link.split("?")[0]
            if not link:
                continue

            # Beim 1. Durchlauf sofort die 3 neuesten schicken
            if is_first_run and sent_count < 3:
                send_to_discord("eBay (Aktuell)", query, title, "Siehe Angebot", link)
                sent_count += 1
                time.sleep(1)

            if link not in seen_ebay:
                if not is_first_run:
                    send_to_discord("eBay", query, title, "Siehe Angebot", link)
                seen_ebay.add(link)
    except Exception as e:
        log(f"eBay Fehler bei '{query}': {e}")

def init_vinted_session():
    session = cffi_requests.Session()
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
    }
    try:
        session.get("https://www.vinted.de", headers=headers, impersonate="chrome120", timeout=10)
        log("Vinted Cookie Session initialisiert.")
    except Exception as e:
        log(f"Vinted Session Init Fehler: {e}")
    return session

def check_vinted(session, query):
    global is_first_run
    try:
        encoded_query = urllib.parse.quote_plus(query)
        url = f"https://www.vinted.de/api/v2/catalog/items?search_text={encoded_query}&order=newest_first"
        res = session.get(url, impersonate="chrome120", timeout=10)
        
        if res.status_code != 200:
            log(f"[Vinted] '{query}' HTTP Status: {res.status_code}")
            return

        data = res.json()
        items = data.get("items", [])
        log(f"[Vinted] '{query}' Treffer: {len(items)}")

        sent_count = 0
        for item in items:
            item_id = str(item.get("id"))
            title = item.get("title", "Kein Titel")
            price = f"{item.get('price', {}).get('amount', 'k. A.')} {item.get('price', {}).get('currency_code', 'EUR')}"
            link = f"https://www.vinted.de/items/{item_id}"

            if is_first_run and sent_count < 3:
                send_to_discord("Vinted (Aktuell)", query, title, price, link)
                sent_count += 1
                time.sleep(1)

            if item_id not in seen_vinted:
                if not is_first_run:
                    send_to_discord("Vinted", query, title, price, link)
                seen_vinted.add(item_id)
    except Exception as e:
        log(f"Vinted Fehler bei '{query}': {e}")

def bot_loop():
    global is_first_run
    log("Bot-Suchschleife gestartet...")
    send_to_discord("System", "Start", "Bot scannt eBay RSS & Vinted!", "0 €", "https://discord.com")
    
    vinted_session = init_vinted_session()
    last_vinted_init = time.time()

    while True:
        # Alle 15 Minuten frische Vinted-Cookies holen
        if time.time() - last_vinted_init > 900:
            vinted_session = init_vinted_session()
            last_vinted_init = time.time()

        for q in SEARCH_QUERIES:
            log(f"--- Prüfe: {q} ---")
            check_ebay_rss(q)
            time.sleep(2)
            check_vinted(vinted_session, q)
            time.sleep(2)

        is_first_run = False
        log("Durchlauf fertig. Pause 20 Sek...")
        time.sleep(20)

if __name__ == "__main__":
    server_thread = threading.Thread(target=start_web_server, daemon=True)
    server_thread.start()
    bot_loop()
