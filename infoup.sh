#!/bin/bash

# Script: update_info_json.sh


# Chemin vers le fichier info.json
JSON_FILE="/home/dietpi/bot/info.json"

cd /home/dietpi/bot

meshtastic --host 192.168.1.38 --info > $JSON_FILE

python3 info_json_clean.py info.json info_clean.json

mv info_clean.json $JSON_FILE

/usr/bin/scp $JSON_FILE root@100.120.148.60:/opt/WebSites/projectsend/. 

