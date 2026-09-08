from flask import Flask, jsonify
from flask_cors import CORS
import requests
from bs4 import BeautifulSoup
import re
import time
from cachetools import TTLCache

app = Flask(__name__)
CORS(app)

# Caché de 5 minutos
cache = TTLCache(maxsize=100, ttl=300)

@app.route('/')
def home():
    return jsonify({
        'status': 'online',
        'name': 'Manga API',
        'endpoints': {
            '/api/mangas': 'Lista de mangas',
            '/api/manga/{id}': 'Detalles de un manga'
        }
    })

@app.route('/api/mangas')
def get_mangas():
    # Verificar caché
    if 'mangas' in cache:
        return jsonify({
            'success': True,
            'data': cache['mangas'],
            'count': len(cache['mangas']),
            'cached': True
        })
    
    try:
        url = "https://manhwashot.lat/"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        
        print("📡 Descargando HTML de manhwashot.lat...")
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        mangas = []
        
        # Buscar tarjetas de mangas
        cards = soup.select('.s-card, .manga-item, .manga-card, .entry-thumb')
        
        print(f"🔍 Encontrados {len(cards)} elementos de manga")
        
        for card in cards:
            try:
                # Título
                title_elem = card.select_one('.s-card-title, .manga-title, .title, h3')
                if not title_elem:
                    continue
                
                title = title_elem.text.strip()
                
                # Imagen
                img_elem = card.select_one('img')
                cover = None
                if img_elem:
                    cover = img_elem.get('src') or img_elem.get('data-src') or img_elem.get('data-lazy-src')
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
                    mangas.append({
                        'id': manga_id,
                        'title': title,
                        'cover': cover,
                        'url': link
                    })
            except Exception as e:
                print(f"⚠️ Error procesando item: {e}")
                continue
        
        # Si no se encontraron mangas, buscar en scripts de Next.js
        if not mangas:
            print("🔄 Buscando en scripts de Next.js...")
            scripts = soup.find_all('script')
            for script in scripts:
                if script.string:
                    # Buscar datos de mangas en formato JSON
                    matches = re.findall(r'"postId":(\d+),"title":"([^"]+)"', script.string)
                    for match in matches:
                        mangas.append({
                            'id': match[0],
                            'title': match[1],
                            'cover': 'https://via.placeholder.com/300x400?text=' + match[1],
                            'url': f'https://manhwashot.lat/manga/{match[1].lower().replace(" ", "-")}/'
                        })
        
        # Si aún no hay mangas, usar datos de ejemplo
        if not mangas:
            print("⚠️ No se encontraron mangas, usando datos de ejemplo")
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
            'cached': False
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
        
        # Capítulos
        chapters = []
        chapter_elems = soup.select('.chapter-list li, .chapters li, .wp-manga-chapter')
        
        for chapter in chapter_elems:
            link = chapter.select_one('a')
            if link:
                chapter_title = link.text.strip()
                number_match = re.search(r'(\d+\.?\d*)', chapter_title)
                number = float(number_match.group(1)) if number_match else 0
                
                chapters.append({
                    'number': number,
                    'title': chapter_title,
                    'url': link.get('href')
                })
        
        return jsonify({
            'success': True,
            'data': {
                'id': manga_id,
                'title': title,
                'description': description,
                'chapters': chapters
            }
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)