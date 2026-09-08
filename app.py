from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
from cachetools import TTLCache
import logging

app = Flask(__name__)
CORS(app)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Caché de 10 minutos para el catálogo completo
catalog_cache = TTLCache(maxsize=1, ttl=600)
# Caché para detalles de mangas (opcional)
detail_cache = TTLCache(maxsize=100, ttl=600)

# URL del JSON con el catálogo completo (¡cámbiala por la tuya!)
CATALOG_URL = "https://gist.githubusercontent.com/jemmdlher-boop/.../raw/mangas.json"

def load_catalog():
    """Carga el catálogo desde el JSON, con caché."""
    if 'catalog' in catalog_cache:
        return catalog_cache['catalog']
    try:
        resp = requests.get(CATALOG_URL, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        catalog_cache['catalog'] = data
        logger.info(f"Catálogo cargado: {len(data)} mangas")
        return data
    except Exception as e:
        logger.error(f"Error cargando catálogo: {e}")
        return []

@app.route('/')
def home():
    return jsonify({
        'status': 'online',
        'name': 'Manga API - Catálogo desde JSON',
        'endpoints': {
            '/api/mangas': 'Lista paginada de mangas (?page=1&limit=20)',
            '/api/manga/{id}': 'Detalle de un manga (con capítulos)'
        }
    })

@app.route('/api/mangas')
def get_mangas():
    page = int(request.args.get('page', 1))
    limit = int(request.args.get('limit', 20))
    catalog = load_catalog()
    if not catalog:
        return jsonify({'success': False, 'error': 'Catálogo no disponible'}), 500
    
    start = (page - 1) * limit
    end = start + limit
    paginated = catalog[start:end]
    
    return jsonify({
        'success': True,
        'data': paginated,
        'page': page,
        'limit': limit,
        'total': len(catalog),
        'total_pages': (len(catalog) + limit - 1) // limit
    })

@app.route('/api/manga/<manga_id>')
def get_manga_detail(manga_id):
    # Verificar caché de detalles
    if manga_id in detail_cache:
        return jsonify({'success': True, 'data': detail_cache[manga_id], 'source': 'cache'})
    
    # Encontrar el manga en el catálogo (para tener su URL)
    catalog = load_catalog()
    manga_info = next((m for m in catalog if m['id'] == manga_id), None)
    if not manga_info:
        return jsonify({'success': False, 'error': 'Manga no encontrado'}), 404
    
    # Aquí podrías hacer scraping de la página del manga para obtener detalles y capítulos,
    # o si tu JSON incluye capítulos, devolverlos directamente.
    # Por ahora, devolvemos datos mínimos + un mensaje.
    detail = {
        'id': manga_id,
        'title': manga_info.get('title', 'Sin título'),
        'cover': manga_info.get('cover'),
        'description': 'Descripción disponible en la web',
        'chapters': []  # Podrías scrapear aquí o tenerlos en el JSON
    }
    detail_cache[manga_id] = detail
    return jsonify({'success': True, 'data': detail})

@app.route('/health')
def health():
    return jsonify({
        'status': 'healthy',
        'catalog_size': len(load_catalog()),
        'cache_size': len(catalog_cache) + len(detail_cache)
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
