from flask import Flask, jsonify
from flask_cors import CORS
import requests
from bs4 import BeautifulSoup
import re
from cachetools import TTLCache
import logging

app = Flask(__name__)
CORS(app)

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Caché de 5 minutos
cache = TTLCache(maxsize=100, ttl=300)

# --- DATOS DE EJEMPLO (FALLBACK) ---
MANGAS_EJEMPLO = [
    {
        "id": "solo-leveling",
        "title": "Solo Leveling",
        "cover": "https://i.imgur.com/6Xq8HqN.jpg",
        "url": "https://manhwashot.lat/manga/solo-leveling/"
    },
    {
        "id": "noblesse",
        "title": "Noblesse",
        "cover": "https://i.imgur.com/TXnXqZT.jpg",
        "url": "https://manhwashot.lat/manga/noblesse/"
    },
    {
        "id": "tower-of-god",
        "title": "Tower of God",
        "cover": "https://i.imgur.com/4L6QqL4.jpg",
        "url": "https://manhwashot.lat/manga/tower-of-god/"
    }
]

# --- ENDPOINTS ---

@app.route('/')
def home():
    return jsonify({
        "status": "online",
        "name": "Manga API",
        "version": "1.0",
        "endpoints": {
            "/api/mangas": "Lista de mangas",
            "/api/manga/{id}": "Detalles de un manga"
        }
    })

@app.route('/api/mangas')
def get_mangas():
    try:
        # Intentar obtener de caché
        if 'mangas' in cache:
            logger.info("Sirviendo desde caché")
            return jsonify({
                "success": True,
                "data": cache['mangas'],
                "count": len(cache['mangas']),
                "source": "cache"
            })

        logger.info("Intentando scraping...")
        url = "https://manhwashot.lat/"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')
        mangas = []

        # Buscar tarjetas de mangas
        cards = soup.select('.s-card, .manga-item, .manga-card')
        for card in cards:
            try:
                title_elem = card.select_one('.s-card-title, .manga-title, .title')
                if not title_elem:
                    continue
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
                    mangas.append({
                        "id": manga_id,
                        "title": title,
                        "cover": cover,
                        "url": link
                    })
            except Exception as e:
                logger.warning(f"Error procesando item: {e}")
                continue

        # Si no se encontraron, usar datos de ejemplo
        if not mangas:
            logger.warning("No se encontraron mangas, usando datos de ejemplo")
            mangas = MANGAS_EJEMPLO

        # Guardar en caché
        cache['mangas'] = mangas
        logger.info(f"Devolviendo {len(mangas)} mangas")
        return jsonify({
            "success": True,
            "data": mangas,
            "count": len(mangas),
            "source": "scraping" if mangas != MANGAS_EJEMPLO else "fallback"
        })

    except Exception as e:
        logger.error(f"Error en /api/mangas: {e}")
        # Siempre devolver datos de ejemplo en caso de error
        return jsonify({
            "success": True,
            "data": MANGAS_EJEMPLO,
            "count": len(MANGAS_EJEMPLO),
            "source": "error_fallback"
        })

@app.route('/api/manga/<manga_id>')
def get_manga_detail(manga_id):
    try:
        cache_key = f'manga_{manga_id}'
        if cache_key in cache:
            return jsonify({
                "success": True,
                "data": cache[cache_key],
                "source": "cache"
            })

        # Intentar scraping
        url = f"https://manhwashot.lat/manga/{manga_id}/"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')

        # Título
        title_elem = soup.select_one('h1, .entry-title, .manga-title')
        title = title_elem.text.strip() if title_elem else manga_id

        # Descripción
        desc_elem = soup.select_one('.description, .summary, .entry-content p')
        description = desc_elem.text.strip() if desc_elem else ""

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
                    "number": number,
                    "title": chapter_title,
                    "url": chapter_url
                })

        chapters.sort(key=lambda x: x['number'], reverse=True)

        result = {
            "id": manga_id,
            "title": title,
            "description": description,
            "cover": cover,
            "chapters": chapters
        }

        cache[cache_key] = result
        return jsonify({
            "success": True,
            "data": result,
            "source": "scraping"
        })

    except Exception as e:
        logger.error(f"Error en /api/manga/{manga_id}: {e}")
        # Devolver datos de ejemplo
        return jsonify({
            "success": True,
            "data": {
                "id": manga_id,
                "title": manga_id.replace('-', ' ').title(),
                "description": "Manga disponible en manhwashot.lat",
                "cover": "https://i.imgur.com/6Xq8HqN.jpg",
                "chapters": [
                    {"number": 1, "title": "Capítulo 1", "url": f"https://manhwashot.lat/manga/{manga_id}/chapter-1/"},
                    {"number": 2, "title": "Capítulo 2", "url": f"https://manhwashot.lat/manga/{manga_id}/chapter-2/"}
                ]
            },
            "source": "fallback"
        })

@app.route('/health')
def health():
    return jsonify({"status": "healthy", "cache_size": len(cache)})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
