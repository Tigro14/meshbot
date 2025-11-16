#!/bin/bash
# Script de validation des données de cartes Meshtastic
# Vérifie que les fichiers JSON sont valides et complets

set -euo pipefail

# Couleurs
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Détection du répertoire
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo -e "${BLUE}=========================================${NC}"
echo -e "${BLUE}Validation des données de cartes${NC}"
echo -e "${BLUE}=========================================${NC}\n"

# Compteur d'erreurs
ERRORS=0

# ============================================================================
# FONCTION DE VALIDATION
# ============================================================================

validate_file() {
    local file="$1"
    local min_size="${2:-100}"

    echo -e "${BLUE}Vérification: ${file}${NC}"

    # Existe ?
    if [ ! -f "$file" ]; then
        echo -e "${RED}  ✗ Fichier non trouvé${NC}"
        ((ERRORS++))
        return 1
    fi

    # Taille
    local size=$(stat -c %s "$file" 2>/dev/null || echo 0)
    if [ "$size" -lt "$min_size" ]; then
        echo -e "${RED}  ✗ Trop petit: ${size} bytes (min: ${min_size})${NC}"
        ((ERRORS++))
        return 1
    fi
    echo -e "${GREEN}  ✓ Taille: ${size} bytes${NC}"

    # JSON valide
    if ! python3 -m json.tool "$file" > /dev/null 2>&1; then
        echo -e "${RED}  ✗ JSON invalide${NC}"
        ((ERRORS++))
        return 1
    fi
    echo -e "${GREEN}  ✓ JSON valide${NC}"

    return 0
}

validate_info_json() {
    local file="$1"

    if ! validate_file "$file" 100; then
        return 1
    fi

    # Compter les nœuds
    local node_count=$(python3 -c "
import json
with open('$file') as f:
    data = json.load(f)
    nodes = data.get('Nodes in mesh', {})
    print(len(nodes))
" 2>/dev/null || echo 0)

    if [ "$node_count" -eq 0 ]; then
        echo -e "${RED}  ✗ Aucun nœud trouvé${NC}"
        ((ERRORS++))
        return 1
    fi

    echo -e "${GREEN}  ✓ Nœuds: ${node_count}${NC}"

    # Compter les nœuds avec GPS
    local gps_count=$(python3 -c "
import json
with open('$file') as f:
    data = json.load(f)
    nodes = data.get('Nodes in mesh', {})
    count = sum(1 for n in nodes.values() if 'position' in n and 'latitude' in n.get('position', {}))
    print(count)
" 2>/dev/null || echo 0)

    echo -e "${GREEN}  ✓ Nœuds avec GPS: ${gps_count}${NC}"

    return 0
}

validate_neighbors_json() {
    local file="$1"

    if ! validate_file "$file" 100; then
        return 1
    fi

    # Statistiques
    local stats=$(python3 -c "
import json
with open('$file') as f:
    data = json.load(f)
    total = data.get('total_nodes', 0)
    stats = data.get('statistics', {})
    with_neighbors = stats.get('nodes_with_neighbors', 0)
    total_entries = stats.get('total_neighbor_entries', 0)
    avg = stats.get('average_neighbors', 0.0)
    print(f'{total}|{with_neighbors}|{total_entries}|{avg:.1f}')
" 2>/dev/null || echo "0|0|0|0.0")

    IFS='|' read -r total with_neighbors total_entries avg <<< "$stats"

    echo -e "${GREEN}  ✓ Total nœuds: ${total}${NC}"
    echo -e "${GREEN}  ✓ Nœuds avec voisins: ${with_neighbors}${NC}"
    echo -e "${GREEN}  ✓ Total entrées voisins: ${total_entries}${NC}"
    echo -e "${GREEN}  ✓ Moyenne voisins/nœud: ${avg}${NC}"

    if [ "$with_neighbors" -eq 0 ]; then
        echo -e "${YELLOW}  ⚠ Aucun nœud avec données de voisinage${NC}"
        echo -e "${YELLOW}    Possible que neighborinfo ne soit pas activé${NC}"
    fi

    return 0
}

check_server_connectivity() {
    local host="$1"
    local user="${2:-root}"

    echo -e "\n${BLUE}Vérification connectivité serveur${NC}"
    echo -e "${BLUE}Serveur: ${user}@${host}${NC}"

    # Ping
    if ping -c 1 -W 2 "$host" > /dev/null 2>&1; then
        echo -e "${GREEN}  ✓ Ping OK${NC}"
    else
        echo -e "${RED}  ✗ Ping échoué${NC}"
        ((ERRORS++))
        return 1
    fi

    # SSH
    if timeout 5 ssh -o BatchMode=yes -o ConnectTimeout=5 "${user}@${host}" "echo OK" > /dev/null 2>&1; then
        echo -e "${GREEN}  ✓ SSH OK${NC}"
    else
        echo -e "${RED}  ✗ SSH échoué (vérifier clés)${NC}"
        ((ERRORS++))
        return 1
    fi

    return 0
}

check_meshtastic_connectivity() {
    local host="$1"
    local port="${2:-4403}"

    echo -e "\n${BLUE}Vérification connectivité Meshtastic${NC}"
    echo -e "${BLUE}Nœud: ${host}:${port}${NC}"

    # TCP
    if timeout 5 nc -zv "$host" "$port" > /dev/null 2>&1; then
        echo -e "${GREEN}  ✓ TCP ${port} ouvert${NC}"
    else
        echo -e "${RED}  ✗ TCP ${port} fermé/inaccessible${NC}"
        ((ERRORS++))
        return 1
    fi

    # Test meshtastic CLI
    if command -v meshtastic > /dev/null 2>&1; then
        echo -e "${GREEN}  ✓ CLI meshtastic installé${NC}"
    else
        echo -e "${YELLOW}  ⚠ CLI meshtastic non installé${NC}"
    fi

    return 0
}

show_file_ages() {
    echo -e "\n${BLUE}Âge des fichiers${NC}"

    local now=$(date +%s)

    for file in info.json info_neighbors.json info.json.backup info_neighbors.json.backup; do
        if [ -f "$file" ]; then
            local mtime=$(stat -c %Y "$file" 2>/dev/null || echo 0)
            local age=$((now - mtime))
            local age_min=$((age / 60))

            if [ "$age_min" -lt 10 ]; then
                echo -e "${GREEN}  ${file}: ${age_min} min${NC}"
            elif [ "$age_min" -lt 60 ]; then
                echo -e "${YELLOW}  ${file}: ${age_min} min${NC}"
            else
                local age_h=$((age_min / 60))
                echo -e "${RED}  ${file}: ${age_h}h (${age_min} min)${NC}"
            fi
        else
            echo -e "${RED}  ${file}: non trouvé${NC}"
        fi
    done
}

show_logs() {
    echo -e "\n${BLUE}Dernières lignes de log${NC}"

    if [ -f "infoup.log" ]; then
        echo -e "${BLUE}──────────────────────────────────────${NC}"
        tail -10 infoup.log
        echo -e "${BLUE}──────────────────────────────────────${NC}"
    else
        echo -e "${YELLOW}  ⚠ Pas de fichier infoup.log${NC}"
    fi
}

# ============================================================================
# MAIN
# ============================================================================

# 1. Validation info.json
echo ""
if validate_info_json "info.json"; then
    echo -e "${GREEN}✅ info.json OK${NC}\n"
else
    echo -e "${RED}❌ info.json INVALIDE${NC}\n"
fi

# 2. Validation info_neighbors.json
if validate_neighbors_json "info_neighbors.json"; then
    echo -e "${GREEN}✅ info_neighbors.json OK${NC}\n"
else
    echo -e "${RED}❌ info_neighbors.json INVALIDE${NC}\n"
fi

# 3. Backups
echo -e "${BLUE}Vérification backups${NC}"
for backup in info.json.backup info_neighbors.json.backup; do
    if [ -f "$backup" ]; then
        if validate_file "$backup" 100 > /dev/null 2>&1; then
            echo -e "${GREEN}  ✓ ${backup} valide${NC}"
        else
            echo -e "${RED}  ✗ ${backup} invalide${NC}"
        fi
    else
        echo -e "${YELLOW}  ⚠ ${backup} non trouvé${NC}"
    fi
done

# 4. Connectivité Meshtastic
if check_meshtastic_connectivity "192.168.1.38" 4403; then
    echo -e "${GREEN}✅ Meshtastic accessible${NC}"
else
    echo -e "${RED}❌ Meshtastic inaccessible${NC}"
fi

# 5. Connectivité serveur (si configuré)
if [ -n "${REMOTE_HOST:-}" ]; then
    if check_server_connectivity "${REMOTE_HOST}" "${REMOTE_USER:-root}"; then
        echo -e "${GREEN}✅ Serveur accessible${NC}"
    else
        echo -e "${RED}❌ Serveur inaccessible${NC}"
    fi
fi

# 6. Âge des fichiers
show_file_ages

# 7. Logs récents
show_logs

# Résumé final
echo -e "\n${BLUE}=========================================${NC}"
if [ "$ERRORS" -eq 0 ]; then
    echo -e "${GREEN}✅ Validation réussie - Aucune erreur${NC}"
    exit 0
else
    echo -e "${RED}❌ Validation échouée - ${ERRORS} erreur(s)${NC}"
    exit 1
fi
