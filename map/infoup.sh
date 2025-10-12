#!/bin/bash
# Met à jour les fichier JSON depuis le node MESH vers les cartes HTML/JS/CSS

# Chemin vers le fichier info.json
JSON_FILE="/home/dietpi/bot/map/info.json"
JSON_LINKS_FILE="/home/dietpi/bot/map/info_neighbors.json"

cd /home/dietpi/bot/map

/home/dietpi/bot/map/export_neighbors.py > $JSON_LINKS_FILE

meshtastic --host 192.168.1.38 --info > $JSON_FILE

python3 info_json_clean.py info.json info_clean.json

mv info_clean.json $JSON_FILE

# Envoie les JSON vers le serveur qui héberge map.html et meshlink.html
/usr/bin/scp $JSON_FILE root@100.120.148.60:/opt/WebSites/projectsend/. 
/usr/bin/scp $JSON_LINKS_FILE root@100.120.148.60:/opt/WebSites/projectsend/. 

