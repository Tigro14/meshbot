#!/bin/bash
# Met à jour les fichiers JSON depuis la base de données MeshBot
# Version améliorée: utilise la base de données SQLite au lieu d'une connexion TCP
# Évite les conflits de connexion TCP unique

# Configuration
JSON_FILE="/home/dietpi/bot/map/info.json"
JSON_LINKS_FILE="/home/dietpi/bot/map/info_neighbors.json"
DB_PATH="/home/dietpi/bot/traffic_history.db"
NODE_NAMES_FILE="/home/dietpi/bot/node_names.json"

cd /home/dietpi/bot/map

echo "🗄️  Export des voisins depuis la base de données..."
# Utiliser le nouveau script qui lit depuis la DB au lieu de se connecter en TCP
# Logs vont sur stderr, JSON va sur stdout
/home/dietpi/bot/map/export_neighbors_from_db.py "$DB_PATH" 48 > $JSON_LINKS_FILE

echo "📡 Récupération des infos nœuds depuis la base de données..."
# Utiliser le nouveau script qui lit depuis node_names.json et la DB au lieu de se connecter en TCP
# Logs vont sur stderr, JSON va sur stdout
/home/dietpi/bot/map/export_nodes_from_db.py "$NODE_NAMES_FILE" "$DB_PATH" 48 > $JSON_FILE

echo "📤 Envoi vers le serveur web..."
# Envoie les JSON vers le serveur qui héberge map.html et meshlink.html
/usr/bin/scp $JSON_FILE root@100.120.148.60:/opt/WebSites/projectsend/. 
/usr/bin/scp $JSON_LINKS_FILE root@100.120.148.60:/opt/WebSites/projectsend/.

echo "✅ Mise à jour terminée!"
