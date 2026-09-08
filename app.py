def scrape_all_mangas():
    """Extrae TODOS los mangas de la página de exploración"""
    all_mangas = []
    page = 1
    
    while True:
        try:
            url = f"https://manhwashot.lat/explorar/?page={page}"
            print(f"Scrapeando página {page}...")
            
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code != 200:
                break
                
            soup = BeautifulSoup(response.text, 'html.parser')
            cards = soup.select('.s-card, .manga-item, .manga-card')
            
            if not cards:
                break
                
            for card in cards:
                # Extraer datos...
                # (código similar al de la función get_mangas)
                pass
                
            all_mangas.extend(mangas_de_la_pagina)
            page += 1
            
            # Si la página no tiene mangas, salir
            if len(cards) < 20:  # asumiendo 20 por página
                break
                
        except Exception as e:
            print(f"Error en página {page}: {e}")
            break
    
    return all_mangas
