import os
import time
import requests
from bs4 import BeautifulSoup
from curl_cffi import requests as cffi_requests

DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")

EBAY_URL = "https://www.ebay.de/sch/i.html?_nkw=harry+kane+topps&_sop=10"
VINTED_URL = "https://www.vinted.de/api/v2/catalog/items?search_text=Harry%20Kane%20Topps&order=newest_first"

HEADERS_EBAY = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
    "Accept-Language": "de-DE,de;q=0.9",
    "Referer": "https://www.ebay.de/",
}

seen_ebay = set()
seen_vinted = set()

def send_to_discord(platform, title, price, link):
    if not DISCORD_WEBHOOK_URL:
        return
    payload = {
        "embeds": [
            {
                "title": f"🛒 [{platform}] {title[:200]}",
                "url": link,
                "color": 15082531 if platform == "eBay" else 3066993,
                "fields": [{"name": "Preis", "value": price, "inline": True}]
            }
        ]
    }
    try:
        requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=5)
    except Exception as e:
        print(f"Discord Fehler: {e}")

def check_ebay(session):
    try:
        res = session.get(EBAY_URL, headers=HEADERS_EBAY, timeout=10)
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
                        send_to_discord("eBay", title, price, link)
                    seen_ebay.add(link)
    except Exception as e:
        print(f"eBay Fehler: {e}")

def check_vinted(session):
    try:
        res = session.get(VINTED_URL, impersonate="chrome120", timeout=10)
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
                        send_to_discord("Vinted", title, price, link)
                    seen_vinted.add(item_id)
    except Exception as e:
        print(f"Vinted Fehler: {e}")

def main():
    print("Bot gestartet...")
    send_to_discord("System", "Bot ist 24/7 aktiv und scannt eBay & Vinted!", "0 €", "https://discord.com")
    
    ebay_session = requests.Session()
    vinted_session = cffi_requests.Session()
    vinted_session.get("https://www.vinted.de", impersonate="chrome120")
    
    last_cookie_refresh = time.time()

    while True:
        # Vinted Session alle 20 Minuten erneuern
        if time.time() - last_cookie_refresh > 1200:
            vinted_session = cffi_requests.Session()
            vinted_session.get("https://www.vinted.de", impersonate="chrome120")
            last_cookie_refresh = time.time()

        check_ebay(ebay_session)
        check_vinted(vinted_session)
        time.sleep(15)

if __name__ == "__main__":
    main()
