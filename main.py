import os
import time
import threading
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
import requests
from bs4 import BeautifulSoup
from curl_cffi import requests as cffi_requests

DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")

# --- HIER BELIEBIG VIELE SUCHBEGRIFFE EINTRAGEN ---
SEARCH_QUERIES = [
    "Harry Kane Topps",
    "Kane Chrome UCC",
    "Igamane",
    "abde ezzalzouli auto"
    "Saibari RC"
    "Iphone"
    
    "
]

HEADERS_EBAY = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
    "Accept-Language": "de-DE,de;q=0.9",
    "Referer": "https://www.ebay.de/",
}

seen_ebay = set()
seen_vinted = set()

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
                "color": 15082531 if platform == "eBay" else 3066993,
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
        print(f"Discord Fehler: {e}")

def check_ebay(session, query):
    try:
        encoded_query = urllib.parse.quote_plus(query)
        url = f"https://www.ebay.de/sch/i.html?_nkw={encoded_query}&_sop=10"
        res = session.get(url, headers=HEADERS_EBAY, timeout=10)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, "html.parser")
            items = soup.find_all("li", class_="s-item")
            for item in items:
                title_elem = item.find("div", class_="s-item__title")
                price_elem = item.find("span", class_="s-item__price")
                link_elem = item.find("a", class_="s-item__link")
                if not title_elem or not link_elem:
                    continue
                title = title_elem.text.strip()
                price = price_elem.text.strip() if price_elem else "n/a"
                link = link_elem.get("href", "").split("?")[0]
                if "Shop on eBay" in title or not link:
                    continue
                if link not in seen_ebay:
                    if len(seen_ebay) > 0:
                        send_to_discord("eBay", query, title, price, link)
                    seen_ebay.add(link)
    except Exception as e:
        print(f"eBay Fehler bei '{query}': {e}")

def check_vinted(session, query):
    try:
        encoded_query = urllib.parse.quote_plus(query)
        url = f"https://www.vinted.de/api/v2/catalog/items?search_text={encoded_query}&order=newest_first"
        res = session.get(url, impersonate="chrome120", timeout=10)
        if res.status_code == 200:
            data = res.json()
            items = data.get("items", [])
            for item in items:
                item_id = str(item.get("id"))
                title = item.get("title", "Kein Titel")
                price = f"{item.get('price', {}).get('amount', 'n/a')} {item.get('price', {}).get('currency_code', 'EUR')}"
                link = f"https://www.vinted.de/items/{item_id}"
                if item_id not in seen_vinted:
                    if len(seen_vinted) > 0:
                        send_to_discord("Vinted", query, title, price, link)
                    seen_vinted.add(item_id)
    except Exception as e:
        print(f"Vinted Fehler bei '{query}': {e}")

def bot_loop():
    print("Bot-Suchschleife gestartet...")
    send_to_discord("System", "Alle Suchen", f"Bot scannt {len(SEARCH_QUERIES)} Suchbegriffe auf eBay & Vinted!", "0 €", "https://discord.com")
    
    ebay_session = requests.Session()
    vinted_session = cffi_requests.Session()
    try:
        vinted_session.get("https://www.vinted.de", impersonate="chrome120")
    except Exception:
        pass
    
    last_cookie_refresh = time.time()

    while True:
        if time.time() - last_cookie_refresh > 1200:
            vinted_session = cffi_requests.Session()
            try:
                vinted_session.get("https://www.vinted.de", impersonate="chrome120")
            except Exception:
                pass
            last_cookie_refresh = time.time()

        for q in SEARCH_QUERIES:
            check_ebay(ebay_session, q)
            time.sleep(2)
            check_vinted(vinted_session, q)
            time.sleep(2)

        time.sleep(15)

if __name__ == "__main__":
    server_thread = threading.Thread(target=start_web_server, daemon=True)
    server_thread.start()
    bot_loop()
