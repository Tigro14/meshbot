#!/bin/bash
# Met à jour les fichiers JSON depuis la base de données MeshBot
# Version améliorée: utilise la base de données SQLite au lieu d'une connexion TCP
# Évite les conflits de connexion TCP unique

# Configuration
JSON_FILE="/home/dietpi/bot/map/info.json"
JSON_LINKS_FILE="/home/dietpi/bot/map/info_neighbors.json"
DB_PATH="/home/dietpi/bot/traffic_history.db"

cd /home/dietpi/bot/map

echo "🗄️  Export des voisins depuis la base de données..."
# Utiliser le nouveau script qui lit depuis la DB au lieu de se connecter en TCP
/home/dietpi/bot/map/export_neighbors_from_db.py "$DB_PATH" 48 > $JSON_LINKS_FILE 2>&1

echo "📡 Récupération des infos nœuds via meshtastic..."
# Toujours utiliser meshtastic pour les infos complètes des nœuds
meshtastic --host 192.168.1.38 --info > $JSON_FILE

echo "🧹 Nettoyage du JSON..."
python3 info_json_clean.py info.json info_clean.json

echo "🔄 Remplacement du fichier..."
mv info_clean.json $JSON_FILE

echo "📤 Envoi vers le serveur web..."
# Envoie les JSON vers le serveur qui héberge map.html et meshlink.html
/usr/bin/scp $JSON_FILE root@100.120.148.60:/opt/WebSites/projectsend/. 
/usr/bin/scp $JSON_LINKS_FILE root@100.120.148.60:/opt/WebSites/projectsend/.

echo "✅ Mise à jour terminée!"
