#!/bin/bash

# Script: update_info_json.sh

# Chemin vers le fichier info.json
JSON_FILE="info.json"

meshtastic --host 192.168.1.38 --info > $JSON_FILE

/usr/bin/scp $JSON_FILE root@100.120.148.60:/opt/WebSites/projectsend/. 

