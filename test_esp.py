#!/usr/bin/env python3
"""
Script de test pour récupération des données ESPHome - Version debug
"""

import requests
import json
import re
from bs4 import BeautifulSoup
from datetime import datetime

# Configuration
ESPHOME_HOST = "192.168.1.27"
ESPHOME_PORT = 80

def debug_html_structure(html_content):
    """Debug complet de la structure HTML"""
    print("=" * 60)
    print("DEBUG STRUCTURE HTML COMPLÈTE")
    print("=" * 60)
    
    print(f"Taille du HTML: {len(html_content)} caractères")
    print("\nContenu HTML brut (premiers 500 caractères):")
    print("-" * 40)
    print(html_content[:500])
    print("-" * 40)
    
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Analyser toutes les balises
    print("\nTOUTES LES BALISES TROUVÉES:")
    all_tags = set()
    for element in soup.find_all():
        all_tags.add(element.name)
    print(f"Balises: {sorted(all_tags)}")
    
    # Chercher du contenu qui ressemble à vos données
    print("\nRECHERCHE DE CONTENU RESSEMBLANT À VOS DONNÉES:")
    search_terms = [
        'BME280', 'Temperature', 'battery', 'voltage', 'current',
        'panel', 'power', 'yield', 'humidity', 'pressure'
    ]
    
    for term in search_terms:
        # Recherche insensible à la casse
        if term.lower() in html_content.lower():
            print(f"✅ Trouvé '{term}' dans le HTML")
            
            # Extraire le contexte autour du terme
            pattern = re.compile(f'.{{0,50}}{re.escape(term)}.{{0,50}}', re.IGNORECASE)
            matches = pattern.findall(html_content)
            for match in matches[:3]:  # Max 3 matches par terme
                clean_match = re.sub(r'\s+', ' ', match.strip())
                print(f"    Contexte: {clean_match}")
        else:
            print(f"❌ '{term}' non trouvé")
    
    # Analyser les divs
    print(f"\nNOMBRE DE DIVS: {len(soup.find_all('div'))}")
    divs = soup.find_all('div')
    for i, div in enumerate(divs[:10]):  # Analyser les 10 premiers divs
        text = div.get_text(strip=True)
        if text and len(text) < 100:  # Texte court qui pourrait être un capteur
            print(f"  Div {i+1}: {text}")
    
    # Chercher des structures alternatives
    print(f"\nAUTRES STRUCTURES:")
    print(f"  Spans: {len(soup.find_all('span'))}")
    print(f"  Paragraphes: {len(soup.find_all('p'))}")
    print(f"  Listes (ul/ol): {len(soup.find_all(['ul', 'ol']))}")
    
    # Afficher le contenu des spans s'il y en a
    spans = soup.find_all('span')
    if spans:
        print("\nContenu des spans:")
        for i, span in enumerate(spans[:10]):
            text = span.get_text(strip=True)
            if text:
                print(f"  Span {i+1}: {text}")

def extract_with_regex(html_content):
    """Extraction avec regex sur le HTML brut"""
    print("\n" + "=" * 60)
    print("EXTRACTION PAR REGEX")
    print("=" * 60)
    
    sensors_data = {}
    
    # Pattern pour chercher des paires nom/valeur
    patterns = [
        # Pattern 1: "BME280 Temperature</td><td>16.4 °C"
        r'([^<>]+?)</td>\s*<td[^>]*>([^<]+)',
        # Pattern 2: "BME280 Temperature: 16.4 °C"
        r'([A-Za-z0-9\s]+?):\s*([0-9.,]+\s*[°%\w/³]*)',
        # Pattern 3: avec balises quelconques
        r'>([A-Za-z0-9\s]+?)<[^>]*>[^<]*<[^>]*>([0-9.,]+\s*[°%\w/³]*)',
    ]
    
    for i, pattern in enumerate(patterns, 1):
        print(f"\nPattern {i}: {pattern}")
        matches = re.findall(pattern, html_content, re.IGNORECASE)
        print(f"  Matches trouvés: {len(matches)}")
        
        for match in matches:
            name, value = match
            name = re.sub(r'\s+', ' ', name.strip())
            value = re.sub(r'\s+', ' ', value.strip())
            
            # Filtrer les résultats pertinents
            if (len(name) > 2 and len(value) > 0 and 
                len(name) < 50 and len(value) < 30 and
                any(keyword in name.lower() for keyword in ['temp', 'voltage', 'current', 'power', 'humidity', 'pressure', 'bme', 'battery'])):
                sensors_data[f"regex_{i}_{name}"] = value
                print(f"    {name}: {value}")
    
    return sensors_data

def test_all_methods():
    """Test toutes les méthodes d'extraction"""
    print("TEST COMPLET D'EXTRACTION ESPHome")
    print(f"Host: {ESPHOME_HOST}:{ESPHOME_PORT}")
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        # Récupérer la page
        print(f"\nConnexion à http://{ESPHOME_HOST}:{ESPHOME_PORT}/")
        response = requests.get(f"http://{ESPHOME_HOST}:{ESPHOME_PORT}/", timeout=10)
        
        if response.status_code != 200:
            print(f"❌ Erreur HTTP: {response.status_code}")
            return
        
        print(f"✅ Connexion réussie ({len(response.text)} caractères)")
        
        # Debug de la structure
        debug_html_structure(response.text)
        
        # Extraction par regex
        sensors_data = extract_with_regex(response.text)
        
        if sensors_data:
            print(f"\n📊 DONNÉES EXTRAITES ({len(sensors_data)} capteurs):")
            for name, value in sensors_data.items():
                clean_name = re.sub(r'^regex_\d+_', '', name)
                print(f"  {clean_name}: {value}")
        else:
            print("\n❌ Aucune donnée extraite")
            
            # Sauvegarder le HTML pour analyse manuelle
            with open('esphome_debug.html', 'w') as f:
                f.write(response.text)
            print("📄 HTML sauvegardé dans 'esphome_debug.html' pour analyse manuelle")
            
    except Exception as e:
        print(f"❌ Erreur: {e}")

if __name__ == "__main__":
    test_all_methods()
