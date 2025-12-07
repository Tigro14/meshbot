#!/bin/bash
# Met à jour les fichiers JSON depuis la base de données MeshBot
# Version améliorée: utilise la base de données SQLite au lieu d'une connexion TCP
# Évite les conflits de connexion TCP unique
#
# Ce script génère un fichier info.json unifié contenant:
# - Informations des nœuds (depuis node_names.json + traffic_history.db)
# - Données de voisinage (depuis neighbors table dans traffic_history.db)
# Les deux sont fusionnés pour que map.html puisse afficher:
# - Couleurs des nœuds selon la distance (hopsAway)
# - Liens entre voisins avec qualité du signal (SNR)

# Configuration
JSON_FILE="/home/dietpi/bot/map/info.json"
JSON_LINKS_FILE="/home/dietpi/bot/map/info_neighbors.json"
DB_PATH="/home/dietpi/bot/traffic_history.db"
NODE_NAMES_FILE="/home/dietpi/bot/node_names.json"

# HYBRID MODE CONFIGURATION
# Set to enable TCP query for complete neighbor data (may conflict with bot)
# Recommended: Set TCP_QUERY_HOST only if bot uses a different node or is stopped
# Leave empty for database-only mode (safe, no conflicts)
TCP_QUERY_HOST=""  # Example: "192.168.1.38"
TCP_QUERY_PORT="4403"

cd /home/dietpi/bot/map

# Build export command based on mode
if [ -n "$TCP_QUERY_HOST" ]; then
    echo "🔌 Mode HYBRIDE: database + requête TCP vers $TCP_QUERY_HOST:$TCP_QUERY_PORT"
    echo "⚠️  ATTENTION: Peut causer des conflits si le bot utilise ce nœud!"
    EXPORT_CMD="/home/dietpi/bot/map/export_neighbors_from_db.py --tcp-query $TCP_QUERY_HOST:$TCP_QUERY_PORT $DB_PATH 720"
else
    echo "🗄️  Mode DATABASE UNIQUEMENT (sûr, pas de conflits TCP)"
    EXPORT_CMD="/home/dietpi/bot/map/export_neighbors_from_db.py $DB_PATH 720"
fi

echo "📊 Export des voisins..."
# Exporter les voisins dans un fichier séparé
# Logs vont sur stderr, JSON va sur stdout
$EXPORT_CMD > $JSON_LINKS_FILE

echo "📡 Récupération des infos nœuds depuis la base de données..."
# Exporter les infos de nœuds (avec hopsAway mais sans neighbors)
# Logs vont sur stderr, JSON va sur stdout
# Utilise 720 heures (30 jours) pour cohérence avec export neighbors
/home/dietpi/bot/map/export_nodes_from_db.py "$NODE_NAMES_FILE" "$DB_PATH" 720 > /tmp/info_temp.json

echo "🔀 Fusion des données de voisinage dans info.json..."
# Fusionner info_neighbors.json dans info.json pour avoir tout en un seul fichier
# Cela permet à map.html d'afficher les liens et les couleurs des nœuds
/home/dietpi/bot/map/merge_neighbor_data.py /tmp/info_temp.json $JSON_LINKS_FILE $JSON_FILE

echo "📤 Envoi vers le serveur web..."
# Envoie les JSON vers le serveur qui héberge map.html et meshlink.html
/usr/bin/scp $JSON_FILE root@100.120.148.60:/opt/WebSites/projectsend/. 
/usr/bin/scp $JSON_LINKS_FILE root@100.120.148.60:/opt/WebSites/projectsend/.

echo "✅ Mise à jour terminée!"
