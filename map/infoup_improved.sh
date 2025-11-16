#!/bin/bash
# Script amélioré pour mise à jour des cartes Meshtastic
# Résout les problèmes de fichiers vides et race conditions en cron

set -euo pipefail  # Arrêt sur erreur, variables non définies, erreurs dans pipes

# ============================================================================
# CONFIGURATION
# ============================================================================

# Détection du répertoire du script (fonctionne même appelé depuis cron)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Fichiers de sortie
JSON_FILE="${SCRIPT_DIR}/info.json"
JSON_LINKS_FILE="${SCRIPT_DIR}/info_neighbors.json"
LOCK_FILE="${SCRIPT_DIR}/.infoup.lock"
LOG_FILE="${SCRIPT_DIR}/infoup.log"

# Configuration Meshtastic
MESH_HOST="192.168.1.38"
MESH_PORT=4403

# Configuration serveur distant (mettre vide pour désactiver l'upload)
REMOTE_USER="root"
REMOTE_HOST="100.120.148.60"
REMOTE_PATH="/opt/WebSites/projectsend"

# Timeouts (en secondes)
MESHTASTIC_TIMEOUT=30
EXPORT_NEIGHBORS_TIMEOUT=60
LOCK_TIMEOUT=300  # 5 minutes max

# Taille minimale pour considérer un fichier valide (en bytes)
MIN_FILE_SIZE=100

# ============================================================================
# FONCTIONS UTILITAIRES
# ============================================================================

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

error() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: $*" | tee -a "$LOG_FILE" >&2
}

cleanup() {
    # Nettoyer le lock en sortant
    if [ -f "$LOCK_FILE" ]; then
        rm -f "$LOCK_FILE"
    fi
}

# Trap pour nettoyer même en cas d'erreur
trap cleanup EXIT INT TERM

acquire_lock() {
    # Vérifier si un lock existe déjà
    if [ -f "$LOCK_FILE" ]; then
        local lock_age=$(($(date +%s) - $(stat -c %Y "$LOCK_FILE" 2>/dev/null || echo 0)))

        if [ "$lock_age" -lt "$LOCK_TIMEOUT" ]; then
            error "Instance déjà en cours (lock: ${lock_age}s). Abandon."
            exit 1
        else
            log "Lock expiré (${lock_age}s > ${LOCK_TIMEOUT}s). Suppression."
            rm -f "$LOCK_FILE"
        fi
    fi

    # Créer le lock
    echo $$ > "$LOCK_FILE"
    log "Lock acquis (PID: $$)"
}

validate_json() {
    local file="$1"

    # Vérifier que le fichier existe
    if [ ! -f "$file" ]; then
        error "Fichier non trouvé: $file"
        return 1
    fi

    # Vérifier taille minimale
    local size=$(stat -c %s "$file" 2>/dev/null || echo 0)
    if [ "$size" -lt "$MIN_FILE_SIZE" ]; then
        error "Fichier trop petit (${size} bytes < ${MIN_FILE_SIZE}): $file"
        return 1
    fi

    # Vérifier syntaxe JSON
    if ! python3 -m json.tool "$file" > /dev/null 2>&1; then
        error "JSON invalide: $file"
        return 1
    fi

    log "✓ Validation OK: $file (${size} bytes)"
    return 0
}

backup_file() {
    local file="$1"
    local backup="${file}.backup"

    if [ -f "$file" ] && validate_json "$file"; then
        cp "$file" "$backup"
        log "✓ Backup créé: $backup"
        return 0
    fi
    return 1
}

restore_backup() {
    local file="$1"
    local backup="${file}.backup"

    if [ -f "$backup" ] && validate_json "$backup"; then
        cp "$backup" "$file"
        log "✓ Backup restauré: $file"
        return 0
    fi

    error "Pas de backup valide disponible: $backup"
    return 1
}

# ============================================================================
# GÉNÉRATION DES DONNÉES
# ============================================================================

generate_neighbors_data() {
    log "Génération des données de voisinage..."

    local tmp_file="${JSON_LINKS_FILE}.tmp"

    # Exécuter avec timeout
    if timeout "$EXPORT_NEIGHBORS_TIMEOUT" "${SCRIPT_DIR}/export_neighbors.py" > "$tmp_file" 2>> "$LOG_FILE"; then
        # Valider le résultat
        if validate_json "$tmp_file"; then
            # Backup de l'ancien fichier
            backup_file "$JSON_LINKS_FILE" || true

            # Remplacer par le nouveau
            mv "$tmp_file" "$JSON_LINKS_FILE"
            log "✓ Données de voisinage mises à jour"
            return 0
        else
            error "Données de voisinage invalides"
            rm -f "$tmp_file"
            return 1
        fi
    else
        error "Timeout ou erreur lors de l'export des voisins"
        rm -f "$tmp_file"
        return 1
    fi
}

generate_node_info() {
    log "Récupération info nœuds depuis ${MESH_HOST}..."

    local tmp_raw="${SCRIPT_DIR}/info_raw.json.tmp"
    local tmp_clean="${SCRIPT_DIR}/info_clean.json.tmp"

    # Exécuter meshtastic avec timeout
    if timeout "$MESHTASTIC_TIMEOUT" meshtastic --host "$MESH_HOST" --info > "$tmp_raw" 2>> "$LOG_FILE"; then
        # Vérifier que le fichier n'est pas vide
        local size=$(stat -c %s "$tmp_raw" 2>/dev/null || echo 0)

        if [ "$size" -lt "$MIN_FILE_SIZE" ]; then
            error "Sortie meshtastic trop petite (${size} bytes)"
            rm -f "$tmp_raw"
            return 1
        fi

        log "✓ Données brutes récupérées (${size} bytes)"

        # Nettoyer avec info_json_clean.py
        if python3 "${SCRIPT_DIR}/info_json_clean.py" "$tmp_raw" "$tmp_clean" >> "$LOG_FILE" 2>&1; then
            # Valider le JSON nettoyé
            if validate_json "$tmp_clean"; then
                # Backup de l'ancien fichier
                backup_file "$JSON_FILE" || true

                # Remplacer par le nouveau
                mv "$tmp_clean" "$JSON_FILE"
                rm -f "$tmp_raw"
                log "✓ Info nœuds mise à jour"
                return 0
            else
                error "JSON nettoyé invalide"
                rm -f "$tmp_raw" "$tmp_clean"
                return 1
            fi
        else
            error "Échec du nettoyage JSON"
            rm -f "$tmp_raw" "$tmp_clean"
            return 1
        fi
    else
        error "Timeout ou erreur meshtastic --info"
        rm -f "$tmp_raw"
        return 1
    fi
}

upload_to_server() {
    # Vérifier si l'upload est configuré
    if [ -z "$REMOTE_HOST" ] || [ -z "$REMOTE_PATH" ]; then
        log "Upload vers serveur distant désactivé (pas de configuration)"
        return 0
    fi

    log "Upload vers ${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_PATH}..."

    local success=true

    # Upload info.json
    if [ -f "$JSON_FILE" ] && validate_json "$JSON_FILE"; then
        if scp -q "$JSON_FILE" "${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_PATH}/." 2>> "$LOG_FILE"; then
            log "✓ info.json uploadé"
        else
            error "Échec upload info.json"
            success=false
        fi
    else
        error "info.json invalide, skip upload"
        success=false
    fi

    # Upload info_neighbors.json
    if [ -f "$JSON_LINKS_FILE" ] && validate_json "$JSON_LINKS_FILE"; then
        if scp -q "$JSON_LINKS_FILE" "${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_PATH}/." 2>> "$LOG_FILE"; then
            log "✓ info_neighbors.json uploadé"
        else
            error "Échec upload info_neighbors.json"
            success=false
        fi
    else
        error "info_neighbors.json invalide, skip upload"
        success=false
    fi

    if [ "$success" = true ]; then
        log "✓ Upload terminé avec succès"
        return 0
    else
        return 1
    fi
}

# ============================================================================
# MAIN
# ============================================================================

main() {
    log "=========================================="
    log "Démarrage mise à jour cartes Meshtastic"
    log "=========================================="

    # Acquérir le lock
    acquire_lock

    # Compteur d'erreurs
    local errors=0

    # 1. Générer les données de voisinage
    if ! generate_neighbors_data; then
        ((errors++))
        # Essayer de restaurer le backup
        restore_backup "$JSON_LINKS_FILE" || true
    fi

    # 2. Générer les infos nœuds
    if ! generate_node_info; then
        ((errors++))
        # Essayer de restaurer le backup
        restore_backup "$JSON_FILE" || true
    fi

    # 3. Upload vers serveur (seulement si au moins un fichier est valide)
    if [ -f "$JSON_FILE" ] || [ -f "$JSON_LINKS_FILE" ]; then
        upload_to_server || ((errors++))
    else
        error "Aucun fichier valide à uploader"
        ((errors++))
    fi

    # Résumé
    log "=========================================="
    if [ "$errors" -eq 0 ]; then
        log "✅ Mise à jour terminée avec succès"
        log "=========================================="
        exit 0
    else
        log "⚠️  Mise à jour terminée avec ${errors} erreur(s)"
        log "=========================================="
        exit 1
    fi
}

# Lancer le script
main "$@"
