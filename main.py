import os
import sys
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

HEADERS_EBAY = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "de-DE,de;q=0.9,en-US;q=0.8",
}

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
        log("Kein Webhook gesetzt!")
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
        res = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=5)
        log(f"Discord gesendet ({platform} - {query}): Status {res.status_code}")
    except Exception as e:
        log(f"Discord Fehler: {e}")

def check_ebay(session, query):
    global is_first_run
    try:
        encoded_query = urllib.parse.quote_plus(query)
        url = f"https://www.ebay.de/sch/i.html?_nkw={encoded_query}&_sop=10"
        res = session.get(url, headers=HEADERS_EBAY, timeout=8)
        if res.status_code != 200:
            log(f"[eBay] '{query}' HTTP Status: {res.status_code}")
            return

        soup = BeautifulSoup(res.text, "html.parser")
        items = soup.find_all("li", class_="s-item")
        log(f"[eBay] '{query}' Roh-Treffer: {len(items)}")

        sent_count = 0
        for item in items:
            title_elem = item.find("div", class_="s-item__title")
            price_elem = item.find("span", class_="s-item__price")
            link_elem = item.find("a", class_="s-item__link")
            if not title_elem or not link_elem:
                continue

            title = title_elem.text.strip()
            price = price_elem.text.strip() if price_elem else "k. A."
            link = link_elem.get("href", "").split("?")[0]
            if "Shop on eBay" in title or not link:
                continue

            if is_first_run and sent_count < 3:
                send_to_discord("eBay (Aktuell)", query, title, price, link)
                sent_count += 1
                time.sleep(1)

            if link not in seen_ebay:
                if not is_first_run:
                    send_to_discord("eBay", query, title, price, link)
                seen_ebay.add(link)
    except Exception as e:
        log(f"eBay Fehler bei '{query}': {e}")

def check_vinted(session, query):
    global is_first_run
    try:
        encoded_query = urllib.parse.quote_plus(query)
        url = f"https://www.vinted.de/api/v2/catalog/items?search_text={encoded_query}&order=newest_first"
        res = session.get(url, impersonate="chrome120", timeout=8)
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
    send_to_discord("System", "Start", "Bot scannt eBay & Vinted und sendet aktuelle Treffer!", "0 €", "https://discord.com")
    
    ebay_session = requests.Session()
    vinted_session = cffi_requests.Session()

    while True:
        for q in SEARCH_QUERIES:
            log(f"--- Prüfe: {q} ---")
            check_ebay(ebay_session, q)
            time.sleep(2)
            check_vinted(vinted_session, q)
            time.sleep(2)

        is_first_run = False
        log("Durchlauf beendet. Warte 20 Sekunden...")
        time.sleep(20)

if __name__ == "__main__":
    server_thread = threading.Thread(target=start_web_server, daemon=True)
    server_thread.start()
    bot_loop()
