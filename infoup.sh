#!/bin/bash

# Script: update_info_json.sh

# Chemin vers le fichier info.json
JSON_FILE="info.json"

meshtastic --host 192.168.1.38 --info > $JSON_FILE


# Extraire à partir de "Nodes in mesh" jusqu'à la fin
sed -n '/^Nodes in mesh:/,$ {
  s/^Nodes in mesh: /{"Nodes in mesh": /
  p
}' "$JSON_FILE" > info_clean.json

mv info_clean.json "$JSON_FILE"

echo "Fichier JSON nettoyé : $JSON_FILE"

/usr/bin/scp $JSON_FILE root@100.120.148.60:/opt/WebSites/projectsend/. 

