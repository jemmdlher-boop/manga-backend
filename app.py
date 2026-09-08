from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
from bs4 import BeautifulSoup
import re
from cachetools import TTLCache
import logging
import time

app = Flask(__name__)
CORS(app)

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Caché de 10 minutos (para no saturar el sitio)
cache = TTLCache(maxsize=100, ttl=600)

# Headers para simular navegador
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

# --- FUNCIÓN PARA SCRAPEAR TODOS LOS MANGAS ---
def scrape_all_mangas():
    """Extrae todos los mangas de la página principal y explorar"""
    all_mangas = []
    seen_ids = set()
    
    # 1. Scrapear página principal (últimas actualizaciones)
    try:
        logger.info("Scrapeando página principal...")
        response = requests.get('https://manhwashot.lat/', headers=HEADERS, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Buscar tarjetas de mangas
        cards = soup.select('.s-card, .manga-item, .manga-card, .entry-thumb')
        for card in cards:
            try:
                manga = extract_manga_from_card(card)
                if manga and manga['id'] not in seen_ids:
                    all_mangas.append(manga)
                    seen_ids.add(manga['id'])
            except Exception as e:
                logger.warning(f"Error en card: {e}")
                continue
    except Exception as e:
        logger.error(f"Error en página principal: {e}")
    
    # 2. Scrapear página de exploración (catálogo completo)
    try:
        logger.info("Scrapeando catálogo completo...")
        page = 1
        max_pages = 10  # Límite para evitar timeout en Render
        
        while page <= max_pages:
            url = f"https://manhwashot.lat/explorar/page/{page}/" if page > 1 else "https://manhwashot.lat/explorar/"
            logger.info(f"Scrapeando página {page}: {url}")
            
            response = requests.get(url, headers=HEADERS, timeout=15)
            if response.status_code != 200:
                break
                
            soup = BeautifulSoup(response.text, 'html.parser')
            cards = soup.select('.s-card, .manga-item, .manga-card, .entry-thumb')
            
            if not cards:
                break
                
            for card in cards:
                try:
                    manga = extract_manga_from_card(card)
                    if manga and manga['id'] not in seen_ids:
                        all_mangas.append(manga)
                        seen_ids.add(manga['id'])
                except Exception as e:
                    continue
            
            # Si hay menos de 20, es la última página
            if len(cards) < 20:
                break
                
            page += 1
            time.sleep(0.5)  # Pequeña pausa para no saturar
            
    except Exception as e:
        logger.error(f"Error en explorar: {e}")
    
    logger.info(f"Total mangas encontrados: {len(all_mangas)}")
    return all_mangas

def extract_manga_from_card(card):
    """Extrae datos de una tarjeta de manga"""
    # Título
    title_elem = card.select_one('.s-card-title, .manga-title, .title, h3')
    if not title_elem:
        return None
    title = title_elem.text.strip()
    
    # Imagen
    img_elem = card.select_one('img')
    cover = None
    if img_elem:
        cover = img_elem.get('src') or img_elem.get('data-src')
        if cover and not cover.startswith('http'):
            cover = 'https://manhwashot.lat' + cover
    
    # Enlace
    link_elem = card.select_one('a')
    link = link_elem.get('href') if link_elem else ''
    if link and not link.startswith('http'):
        link = 'https://manhwashot.lat' + link
    
    # ID del manga
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

# --- ENDPOINTS ---

@app.route('/')
def home():
    return jsonify({
        'status': 'online',
        'name': 'Manga API - Catálogo Completo',
        'endpoints': {
            '/api/mangas': 'Lista de todos los mangas',
            '/api/manga/{id}': 'Detalles de un manga'
        }
    })

@app.route('/api/mangas')
def get_mangas():
    # Verificar caché
    if 'all_mangas' in cache:
        logger.info("Sirviendo desde caché")
        return jsonify({
            'success': True,
            'data': cache['all_mangas'],
            'count': len(cache['all_mangas']),
            'source': 'cache'
        })
    
    try:
        mangas = scrape_all_mangas()
        
        # Si no se encontraron mangas, usar datos de ejemplo
        if not mangas:
            logger.warning("No se encontraron mangas, usando fallback")
            mangas = [
                {'id': 'solo-leveling', 'title': 'Solo Leveling', 'cover': 'https://i.imgur.com/6Xq8HqN.jpg', 'url': 'https://manhwashot.lat/manga/solo-leveling/'},
                {'id': 'noblesse', 'title': 'Noblesse', 'cover': 'https://i.imgur.com/TXnXqZT.jpg', 'url': 'https://manhwashot.lat/manga/noblesse/'}
            ]
        
        cache['all_mangas'] = mangas
        return jsonify({
            'success': True,
            'data': mangas,
            'count': len(mangas),
            'source': 'scraping'
        })
        
    except Exception as e:
        logger.error(f"Error en /api/mangas: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'data': []
        }), 500

@app.route('/api/manga/<manga_id>')
def get_manga_detail(manga_id):
    cache_key = f'manga_{manga_id}'
    if cache_key in cache:
        return jsonify({
            'success': True,
            'data': cache[cache_key],
            'source': 'cache'
        })
    
    try:
        url = f"https://manhwashot.lat/manga/{manga_id}/"
        response = requests.get(url, headers=HEADERS, timeout=15)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Título
        title_elem = soup.select_one('h1, .entry-title, .manga-title')
        title = title_elem.text.strip() if title_elem else manga_id
        
        # Descripción
        desc_elem = soup.select_one('.description, .summary, .entry-content p')
        description = desc_elem.text.strip() if desc_elem else "Sin descripción disponible"
        
        # Portada
        cover_elem = soup.select_one('.cover img, .thumb img')
        cover = cover_elem.get('src') if cover_elem else None
        
        # Capítulos
        chapters = []
        chapter_elems = soup.select('.chapter-list li, .chapters li, .wp-manga-chapter')
        
        for chapter in chapter_elems:
            link_elem = chapter.select_one('a')
            if link_elem:
                chapter_title = link_elem.text.strip()
                number_match = re.search(r'(\d+\.?\d*)', chapter_title)
                number = float(number_match.group(1)) if number_match else 0
                chapter_url = link_elem.get('href')
                if chapter_url and not chapter_url.startswith('http'):
                    chapter_url = 'https://manhwashot.lat' + chapter_url
                chapters.append({
                    'number': number,
                    'title': chapter_title,
                    'url': chapter_url
                })
        
        chapters.sort(key=lambda x: x['number'], reverse=True)
        
        result = {
            'id': manga_id,
            'title': title,
            'description': description,
            'cover': cover,
            'chapters': chapters
        }
        
        cache[cache_key] = result
        return jsonify({
            'success': True,
            'data': result,
            'source': 'scraping'
        })
        
    except Exception as e:
        logger.error(f"Error en detalle: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/health')
def health():
    return jsonify({
        'status': 'healthy',
        'cache_size': len(cache),
        'uptime': 'online'
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
