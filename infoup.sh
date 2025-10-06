#!/bin/bash

# Script: update_info_json.sh
# Usage: Appeler ce script après la génération du fichier info.json

# Chemin vers le fichier info.json
JSON_FILE="info.json"

meshtastic --host 192.168.1.38 --info > $JSON_FILE

# Vérifier que le JSON reste valide
if ! jq empty "$JSON_FILE" > /dev/null 2>&1; then
    # Si l'ajout casse le JSON, on retire la dernière ligne
    sed -i '$d' "$JSON_FILE"
    echo "Avertissement: Le timestamp n'a pas été ajouté pour préserver la validité JSON" >&2
fi


/usr/bin/scp $JSON_FILE root@100.120.148.60:/opt/WebSites/projectsend/. 

