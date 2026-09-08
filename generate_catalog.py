import requests
from bs4 import BeautifulSoup
import json
import time
import re

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}

def extract_manga_from_card(card):
    title_elem = card.select_one('.s-card-title, .manga-title, .title, h3')
    if not title_elem:
        return None
    title = title_elem.text.strip()
    img_elem = card.select_one('img')
    cover = img_elem.get('src') if img_elem else None
    if cover and not cover.startswith('http'):
        cover = 'https://manhwashot.lat' + cover
    link_elem = card.select_one('a')
    link = link_elem.get('href') if link_elem else ''
    if link and not link.startswith('http'):
        link = 'https://manhwashot.lat' + link
    manga_id = ''
    if link:
        match = re.search(r'/manga/([^/]+)/?', link)
        if match:
            manga_id = match.group(1)
    if manga_id and title:
        return {
            'id': manga_id,
            'title': title,
            'cover': cover,
            'url': link
        }
    return None

def scrape_all_mangas():
    all_mangas = []
    seen_ids = set()
    
    # 1. Página principal
    print("Scrapeando página principal...")
    resp = requests.get('https://manhwashot.lat/', headers=HEADERS, timeout=15)
    soup = BeautifulSoup(resp.text, 'html.parser')
    cards = soup.select('.s-card, .manga-item, .manga-card')
    for card in cards:
        manga = extract_manga_from_card(card)
        if manga and manga['id'] not in seen_ids:
            all_mangas.append(manga)
            seen_ids.add(manga['id'])
    
    # 2. Explorar paginado
    page = 1
    while True:
        url = f"https://manhwashot.lat/explorar/page/{page}/" if page > 1 else "https://manhwashot.lat/explorar/"
        print(f"Scrapeando página {page}...")
        resp = requests.get(url, headers=HEADERS, timeout=15)
        if resp.status_code != 200:
            break
        soup = BeautifulSoup(resp.text, 'html.parser')
        cards = soup.select('.s-card, .manga-item, .manga-card')
        if not cards:
            break
        for card in cards:
            manga = extract_manga_from_card(card)
            if manga and manga['id'] not in seen_ids:
                all_mangas.append(manga)
                seen_ids.add(manga['id'])
        if len(cards) < 20:
            break
        page += 1
        time.sleep(0.5)
    
    return all_mangas

if __name__ == '__main__':
    mangas = scrape_all_mangas()
    with open('mangas.json', 'w', encoding='utf-8') as f:
        json.dump(mangas, f, ensure_ascii=False, indent=2)
    print(f"Total: {len(mangas)} mangas guardados en mangas.json")
