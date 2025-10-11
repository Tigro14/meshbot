#!/usr/bin/env python3
"""
Générateur de carte mesh basé sur les données actuelles (pas besoin de neighbor_info)
Utilise les positions GPS + signaux RSSI/SNR reçus par le nœud central
"""

import json
import time
import meshtastic.tcp_interface
from datetime import datetime

def make_json_safe(obj, max_depth=5, current_depth=0):
    """Convertir en JSON-safe"""
    if current_depth > max_depth or obj is None:
        return None
    
    if isinstance(obj, (bool, int, float, str)):
        return obj
    
    if isinstance(obj, bytes):
        return obj.hex()
    
    if isinstance(obj, (list, tuple)):
        return [make_json_safe(item, max_depth, current_depth + 1) for item in obj]
    
    if isinstance(obj, dict):
        return {str(k): make_json_safe(v, max_depth, current_depth + 1) for k, v in obj.items()}
    
    try:
        if hasattr(obj, '__dict__'):
            obj_dict = {}
            for key, value in obj.__dict__.items():
                if not key.startswith('_'):
                    obj_dict[key] = make_json_safe(value, max_depth, current_depth + 1)
            return obj_dict
        return str(obj)
    except:
        return str(obj)

def extract_node_data(node_id, node_info):
    """Extraire les données essentielles d'un nœud"""
    node_data = {
        'id': f"!{node_id:08x}" if isinstance(node_id, int) else str(node_id),
        'name': 'Unknown',
        'short_name': 'UNK',
        'lat': None,
        'lon': None,
        'snr': 0,
        'rssi': 0,
        'hops_away': 99,
        'last_heard': 0,
        'has_position': False
    }
    
    # User info
    if isinstance(node_info, dict):
        if 'user' in node_info:
            user = node_info['user']
            if isinstance(user, dict):
                node_data['name'] = user.get('longName', 'Unknown')
                node_data['short_name'] = user.get('shortName', 'UNK')
            else:
                node_data['name'] = getattr(user, 'longName', 'Unknown')
                node_data['short_name'] = getattr(user, 'shortName', 'UNK')
        
        # Position
        if 'position' in node_info:
            pos = node_info['position']
            if isinstance(pos, dict):
                lat = pos.get('latitude', pos.get('latitudeI', 0))
                lon = pos.get('longitude', pos.get('longitudeI', 0))
            else:
                lat = getattr(pos, 'latitude', getattr(pos, 'latitudeI', 0))
                lon = getattr(pos, 'longitude', getattr(pos, 'longitudeI', 0))
            
            if lat != 0 and lon != 0:
                # Conversion si format integer (1e7)
                if abs(lat) > 1000:
                    lat = lat / 1e7
                if abs(lon) > 1000:
                    lon = lon / 1e7
                
                node_data['lat'] = lat
                node_data['lon'] = lon
                node_data['has_position'] = True
        
        # Métriques
        node_data['snr'] = node_info.get('snr', 0)
        node_data['rssi'] = node_info.get('rssi', 0)
        node_data['hops_away'] = node_info.get('hopsAway', 99)
        node_data['last_heard'] = node_info.get('lastHeard', 0)
    
    return node_data

def generate_html_map(nodes_data, central_node_id, output_file="mesh_map.html"):
    """Générer une carte HTML interactive avec Leaflet"""
    
    # Filtrer les nœuds avec position
    nodes_with_pos = [n for n in nodes_data if n['has_position']]
    
    print(f"📍 {len(nodes_with_pos)}/{len(nodes_data)} nœuds avec position GPS")
    
    if not nodes_with_pos:
        print("❌ Aucun nœud avec position GPS, impossible de générer la carte")
        return False
    
    # Trouver le centre de la carte (moyenne des positions)
    avg_lat = sum(n['lat'] for n in nodes_with_pos) / len(nodes_with_pos)
    avg_lon = sum(n['lon'] for n in nodes_with_pos) / len(nodes_with_pos)
    
    # Trouver le nœud central
    central_node = next((n for n in nodes_data if n['id'] == central_node_id), None)
    if central_node and central_node['has_position']:
        center_lat, center_lon = central_node['lat'], central_node['lon']
    else:
        center_lat, center_lon = avg_lat, avg_lon
    
    # Générer les données pour la carte
    nodes_json = json.dumps([n for n in nodes_with_pos], ensure_ascii=False)
    
    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Carte Réseau Mesh - {len(nodes_with_pos)} nœuds</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
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
        .info-panel {{
            position: absolute;
            top: 10px;
            right: 10px;
            background: white;
            padding: 15px;
            border-radius: 5px;
            box-shadow: 0 0 15px rgba(0,0,0,0.2);
            z-index: 1000;
            max-width: 300px;
        }}
        .info-panel h3 {{
            margin-top: 0;
        }}
        .legend {{
            position: absolute;
            bottom: 30px;
            left: 10px;
            background: white;
            padding: 10px;
            border-radius: 5px;
            box-shadow: 0 0 15px rgba(0,0,0,0.2);
            z-index: 1000;
        }}
        .legend-item {{
            margin: 5px 0;
        }}
        .legend-color {{
            display: inline-block;
            width: 20px;
            height: 20px;
            margin-right: 5px;
            border-radius: 50%;
            vertical-align: middle;
        }}
    </style>
</head>
<body>
    <div id="map"></div>
    
    <div class="info-panel">
        <h3>🗺️ Réseau Mesh</h3>
        <p><strong>Nœuds affichés:</strong> {len(nodes_with_pos)}</p>
        <p><strong>Nœud central:</strong> {central_node['short_name'] if central_node else 'N/A'}</p>
        <p><strong>Export:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M')}</p>
        <p style="font-size: 0.9em; color: #666;">
            Les lignes vertes indiquent les connexions directes (hops=0) avec le nœud central.
        </p>
    </div>
    
    <div class="legend">
        <strong>Légende</strong>
        <div class="legend-item">
            <span class="legend-color" style="background: #ff0000;"></span>
            Nœud central
        </div>
        <div class="legend-item">
            <span class="legend-color" style="background: #00ff00;"></span>
            Direct (0 hop)
        </div>
        <div class="legend-item">
            <span class="legend-color" style="background: #ffa500;"></span>
            Relayé (1+ hops)
        </div>
        <div class="legend-item">
            <span class="legend-color" style="background: #888888;"></span>
            Inconnu
        </div>
    </div>
    
    <script>
        // Données des nœuds
        const nodes = {nodes_json};
        const centralNodeId = "{central_node_id}";
        
        // Initialiser la carte
        const map = L.map('map').setView([{center_lat}, {center_lon}], 12);
        
        // Ajouter les tuiles OpenStreetMap
        L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
            attribution: '© OpenStreetMap contributors',
            maxZoom: 19
        }}).addTo(map);
        
        // Trouver le nœud central
        const centralNode = nodes.find(n => n.id === centralNodeId);
        
        // Ajouter les marqueurs et les lignes
        nodes.forEach(node => {{
            // Déterminer la couleur
            let color = '#888888';  // Gris par défaut
            if (node.id === centralNodeId) {{
                color = '#ff0000';  // Rouge pour central
            }} else if (node.hops_away === 0) {{
                color = '#00ff00';  // Vert pour direct
            }} else if (node.hops_away > 0 && node.hops_away < 99) {{
                color = '#ffa500';  // Orange pour relayé
            }}
            
            // Créer le marqueur
            const marker = L.circleMarker([node.lat, node.lon], {{
                radius: node.id === centralNodeId ? 16 : 12,
                fillColor: color,
                color: '#000',
                weight: 1,
                opacity: 1,
                fillOpacity: 0.8
            }}).addTo(map);
            
            // Popup avec infos
            const lastHeardDate = node.last_heard > 0 ? 
                new Date(node.last_heard * 1000).toLocaleString() : 'N/A';
            
            marker.bindPopup(`
                <strong>${{node.name}}</strong><br>
                ID: ${{node.id}}<br>
                Short: ${{node.short_name}}<br>
                Hops: ${{node.hops_away === 99 ? '?' : node.hops_away}}<br>
                SNR: ${{node.snr.toFixed(1)}} dB<br>
                RSSI: ${{node.rssi}} dBm<br>
                Dernière réception: ${{lastHeardDate}}
            `);
            
            // Tracer une ligne vers le nœud central si connexion directe
            if (centralNode && node.id !== centralNodeId && node.hops_away === 0) {{
                const line = L.polyline(
                    [[centralNode.lat, centralNode.lon], [node.lat, node.lon]],
                    {{
                        color: '#00ff00',
                        weight: 2,
                        opacity: 0.5,
                        dashArray: '5, 5'
                    }}
                ).addTo(map);
                
                line.bindPopup(`
                    <strong>Connexion directe</strong><br>
                    ${{centralNode.short_name}} ↔ ${{node.short_name}}<br>
                    SNR: ${{node.snr.toFixed(1)}} dB
                `);
            }}
        }});
        
        // Ajuster le zoom pour voir tous les nœuds
        if (nodes.length > 1) {{
            const bounds = L.latLngBounds(nodes.map(n => [n.lat, n.lon]));
            map.fitBounds(bounds, {{ padding: [50, 50] }});
        }}
    </script>
</body>
</html>"""
    
    # Écrire le fichier HTML
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    print(f"✅ Carte générée : {output_file}")
    return True

def export_and_map(host, port=4403):
    """Exporter les données et générer la carte"""
    print(f"🔌 Connexion à {host}:{port}...")
    
    try:
        interface = meshtastic.tcp_interface.TCPInterface(
            hostname=host,
            portNumber=port
        )
        
        print("⏳ Chargement des données (10 secondes)...")
        time.sleep(10)
        
        nodes = interface.nodes
        print(f"📊 {len(nodes)} nœuds trouvés")
        
        # Obtenir l'ID du nœud local (central)
        central_node_id = None
        if hasattr(interface, 'localNode') and interface.localNode:
            central_node_id = f"!{interface.localNode.nodeNum:08x}"
            print(f"🎯 Nœud central : {central_node_id}")
        
        # Extraire les données
        nodes_data = []
        for node_id, node_info in nodes.items():
            node_data = extract_node_data(node_id, node_info)
            nodes_data.append(node_data)
        
        interface.close()
        
        # Statistiques
        nodes_with_pos = sum(1 for n in nodes_data if n['has_position'])
        direct_nodes = sum(1 for n in nodes_data if n['hops_away'] == 0 and n['id'] != central_node_id)
        
        print(f"\n📊 Statistiques :")
        print(f"   • Nœuds avec GPS : {nodes_with_pos}/{len(nodes_data)}")
        print(f"   • Connexions directes : {direct_nodes}")
        
        # Exporter JSON
        output_json = {
            'export_time': datetime.now().isoformat(),
            'source_host': host,
            'central_node': central_node_id,
            'total_nodes': len(nodes_data),
            'nodes_with_position': nodes_with_pos,
            'direct_connections': direct_nodes,
            'nodes': nodes_data
        }
        
        json_file = 'mesh_data.json'
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(output_json, f, indent=2, ensure_ascii=False)
        print(f"✅ Données exportées : {json_file}")
        
        # Générer la carte HTML
        if nodes_with_pos > 0:
            map_file = 'mesh_map.html'
            generate_html_map(nodes_data, central_node_id, map_file)
            print(f"\n🗺️  Ouvrez {map_file} dans un navigateur pour voir la carte !")
        else:
            print(f"\n⚠️  Impossible de générer la carte : aucun nœud avec position GPS")
        
        return True
        
    except Exception as e:
        print(f"✗ Erreur : {e}")
        import traceback
        print(traceback.format_exc())
        return False

if __name__ == "__main__":
    HOST = "192.168.1.38"  # tigrog2
    PORT = 4403
    
    export_and_map(HOST, PORT)
