#!/usr/bin/env python3
import subprocess
import json
import re
from datetime import datetime

# ============ CONFIGURATION ============
MESHTASTIC_HOST = "192.168.1.38"
NODE_NAMES_FILE = "node_names.json"
OUTPUT_HTML = "mesh_map.html"

# ============ CHARGEMENT DES NOMS ============
def load_node_names():
    try:
        with open(NODE_NAMES_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return {int(node_id): name for node_id, name in data.items()}
    except Exception as e:
        print(f"Erreur chargement {NODE_NAMES_FILE}: {e}")
        return {}

# ============ RÉCUPÉRATION DES NŒUDS ============
def get_nodes_from_device():
    """Récupère la liste des nœuds depuis l'appareil Meshtastic"""
    print(f"Récupération des nœuds depuis {MESHTASTIC_HOST}...")
    
    try:
        result = subprocess.run(
            ["meshtastic", "--host", MESHTASTIC_HOST, "--nodes"],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode != 0:
            print(f"Erreur: {result.stderr}")
            return []
        
        return parse_nodes_output(result.stdout)
    
    except subprocess.TimeoutExpired:
        print("Timeout lors de la connexion à l'appareil")
        return []
    except FileNotFoundError:
        print("Commande 'meshtastic' non trouvée. Installez: pip install meshtastic")
        return []

def parse_nodes_output(output):
    """Parse la sortie texte de --nodes"""
    nodes = []
    current_node = {}
    
    for line in output.split('\n'):
        line = line.strip()
        
        # Détection d'un nouveau nœud (commence par un ID)
        if line.startswith('!'):
            if current_node and 'id' in current_node:
                nodes.append(current_node)
            
            # Extraire l'ID
            id_match = re.match(r'!([0-9a-f]{8})', line)
            if id_match:
                node_hex = id_match.group(1)
                current_node = {
                    'id': int(node_hex, 16),
                    'id_hex': node_hex
                }
        
        # Extraire les informations
        elif 'User:' in line:
            match = re.search(r"User:\s+'([^']+)'", line)
            if match:
                current_node['long_name'] = match.group(1)
        
        elif 'Position:' in line:
            # Format: Position: (48.123456, 2.123456)
            match = re.search(r'Position:\s*\(([0-9.-]+),\s*([0-9.-]+)\)', line)
            if match:
                current_node['latitude'] = float(match.group(1))
                current_node['longitude'] = float(match.group(2))
        
        elif 'SNR:' in line:
            match = re.search(r'SNR:\s*([0-9.-]+)', line)
            if match:
                current_node['snr'] = float(match.group(1))
        
        elif 'LastHeard:' in line:
            match = re.search(r'LastHeard:\s*(.+)$', line)
            if match:
                current_node['last_heard'] = match.group(1).strip()
    
    # Ajouter le dernier nœud
    if current_node and 'id' in current_node:
        nodes.append(current_node)
    
    return nodes

# ============ GÉNÉRATION DE LA CARTE HTML ============
def generate_html_map(nodes, known_names):
    """Génère une carte HTML interactive avec Leaflet"""
    
    # Filtrer les nœuds avec position et dans la liste connue
    valid_nodes = []
    for node in nodes:
        if 'latitude' in node and 'longitude' in node and node['id'] in known_names:
            node['known_name'] = known_names[node['id']]
            valid_nodes.append(node)
    
    if not valid_nodes:
        print("Aucun nœud avec position GPS trouvé dans votre liste")
        return False
    
    # Calculer le centre de la carte
    center_lat = sum(n['latitude'] for n in valid_nodes) / len(valid_nodes)
    center_lon = sum(n['longitude'] for n in valid_nodes) / len(valid_nodes)
    
    # Générer les marqueurs JavaScript
    markers_js = []
    for node in valid_nodes:
        name = node.get('known_name', node.get('long_name', f"!{node['id_hex']}"))
        lat = node['latitude']
        lon = node['longitude']
        snr = node.get('snr', 'N/A')
        last_heard = node.get('last_heard', 'Inconnu')
        
        popup_html = f"""
        <b>{name}</b><br>
        ID: !{node['id_hex']}<br>
        Position: {lat:.6f}, {lon:.6f}<br>
        SNR: {snr} dB<br>
        Vu: {last_heard}
        """
        
        markers_js.append(f"""
        L.marker([{lat}, {lon}]).addTo(map)
            .bindPopup(`{popup_html}`);
        """)
    
    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Carte Meshtastic - {len(valid_nodes)} nœuds</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <style>
        body {{
            margin: 0;
            padding: 0;
            font-family: Arial, sans-serif;
        }}
        #map {{
            position: absolute;
            top: 0;
            bottom: 0;
            width: 100%;
        }}
        .info {{
            padding: 10px;
            background: white;
            border-radius: 5px;
            box-shadow: 0 0 15px rgba(0,0,0,0.2);
        }}
        .info h3 {{
            margin: 0 0 5px;
            color: #333;
        }}
    </style>
</head>
<body>
    <div id="map"></div>
    
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <script>
        // Initialiser la carte
        const map = L.map('map').setView([{center_lat}, {center_lon}], 11);
        
        // Ajouter les tuiles OpenStreetMap
        L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
            maxZoom: 19,
            attribution: '© OpenStreetMap contributors'
        }}).addTo(map);
        
        // Ajouter les marqueurs
        {''.join(markers_js)}
        
        // Panneau d'information
        const info = L.control({{position: 'topright'}});
        info.onAdd = function(map) {{
            this._div = L.DomUtil.create('div', 'info');
            this._div.innerHTML = '<h3>Carte Meshtastic</h3>' +
                '<b>{len(valid_nodes)} nœuds</b> connus avec position<br>' +
                'Généré: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}';
            return this._div;
        }};
        info.addTo(map);
    </script>
</body>
</html>"""
    
    with open(OUTPUT_HTML, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    return True

# ============ MAIN ============
def main():
    print("Générateur de carte Meshtastic locale\n")
    
    # Charger les noms connus
    known_names = load_node_names()
    if not known_names:
        print(f"Attention: {NODE_NAMES_FILE} vide ou absent")
        return
    
    print(f"{len(known_names)} nœuds connus chargés\n")
    
    # Récupérer les nœuds depuis l'appareil
    nodes = get_nodes_from_device()
    
    if not nodes:
        print("\nAucun nœud récupéré. Vérifiez:")
        print(f"  - L'appareil est accessible sur {MESHTASTIC_HOST}")
        print("  - La commande 'meshtastic' est installée")
        return
    
    print(f"\n{len(nodes)} nœuds totaux récupérés")
    
    # Compter les nœuds avec position
    nodes_with_pos = sum(1 for n in nodes if 'latitude' in n and 'longitude' in n)
    print(f"{nodes_with_pos} nœuds avec position GPS")
    
    # Compter les nœuds connus avec position
    known_with_pos = sum(1 for n in nodes 
                        if 'latitude' in n and 'longitude' in n and n['id'] in known_names)
    print(f"{known_with_pos} nœuds connus avec position GPS")
    
    # Générer la carte
    if generate_html_map(nodes, known_names):
        print(f"\nCarte générée: {OUTPUT_HTML}")
        print(f"Ouvrez ce fichier dans votre navigateur")
    else:
        print("\nÉchec de génération de la carte")

if __name__ == "__main__":
    main()
