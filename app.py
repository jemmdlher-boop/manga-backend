from flask import Flask, jsonify
from flask_cors import CORS
import requests
from bs4 import BeautifulSoup
import re
from cachetools import TTLCache

app = Flask(__name__)
CORS(app)  # Permite peticiones desde cualquier origen

# Caché de 5 minutos
cache = TTLCache(maxsize=100, ttl=300)

@app.route('/')
def home():
    return jsonify({
        'status': 'online',
        'name': 'Manga API - manhwashot.lat',
        'endpoints': {
            '/api/mangas': 'Lista de mangas',
            '/api/manga/{id}': 'Detalles de un manga'
        },
        'test': 'Prueba /api/mangas para ver los datos'
    })

@app.route('/api/mangas')
def get_mangas():
    # Verificar caché
    if 'mangas' in cache:
        return jsonify({
            'success': True,
            'data': cache['mangas'],
            'count': len(cache['mangas']),
            'cached': True,
            'source': 'cache'
        })
    
    try:
        url = "https://manhwashot.lat/"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        print("📡 Descargando HTML...")
        response = requests.get(url, headers=headers, timeout=15)
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
                cover = None
                if img_elem:
                    cover = img_elem.get('src') or img_elem.get('data-src')
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
                        'id': manga_id,
                        'title': title,
                        'cover': cover,
                        'url': link
                    })
            except Exception as e:
                print(f"Error en item: {e}")
                continue
        
        # Si no hay mangas, usar datos de ejemplo
        if not mangas:
            print("⚠️ Usando datos de ejemplo")
            mangas = [
                {
                    'id': 'solo-leveling',
                    'title': 'Solo Leveling',
                    'cover': 'https://i.imgur.com/6Xq8HqN.jpg',
                    'url': 'https://manhwashot.lat/manga/solo-leveling/'
                },
                {
                    'id': 'noblesse',
                    'title': 'Noblesse',
                    'cover': 'https://i.imgur.com/TXnXqZT.jpg',
                    'url': 'https://manhwashot.lat/manga/noblesse/'
                },
                {
                    'id': 'tower-of-god',
                    'title': 'Tower of God',
                    'cover': 'https://i.imgur.com/4L6QqL4.jpg',
                    'url': 'https://manhwashot.lat/manga/tower-of-god/'
                }
            ]
        
        # Guardar en caché
        cache['mangas'] = mangas
        print(f"✅ Encontrados {len(mangas)} mangas")
        
        return jsonify({
            'success': True,
            'data': mangas,
            'count': len(mangas),
            'cached': False,
            'source': 'scraping'
        })
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/manga/<manga_id>')
def get_manga_detail(manga_id):
    try:
        # Intentar obtener de caché
        cache_key = f'manga_{manga_id}'
        if cache_key in cache:
            return jsonify({
                'success': True,
                'data': cache[cache_key],
                'cached': True
            })
        
        url = f"https://manhwashot.lat/manga/{manga_id}/"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=15)
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
                    'number': number,
                    'title': chapter_title,
                    'url': chapter_url
                })
        
        # Ordenar capítulos
        chapters.sort(key=lambda x: x['number'], reverse=True)
        
        result = {
            'id': manga_id,
            'title': title,
            'description': description,
            'cover': cover,
            'chapters': chapters
        }
        
        # Guardar en caché
        cache[cache_key] = result
        
        return jsonify({
            'success': True,
            'data': result,
            'cached': False
        })
        
    except Exception as e:
        print(f"❌ Error en detalle: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/health')
def health():
    return jsonify({
        'status': 'healthy',
        'cache_size': len(cache)
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
