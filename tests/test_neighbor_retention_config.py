#!/usr/bin/env python3
"""
Test de la configuration de rétention des données de voisinage (30 jours)
Vérifie que:
1. La configuration NEIGHBOR_RETENTION_HOURS est correctement définie
2. Le bot utilise cette valeur pour le nettoyage
3. L'export script utilise 720h (30 jours)
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import os
import sys
import re

def test_config_sample():
    """Vérifier que config.py.sample contient NEIGHBOR_RETENTION_HOURS = 720"""
    print("\n📋 Test 1: Vérification de config.py.sample")
    
    config_path = "config.py.sample"
    if not os.path.exists(config_path):
        print(f"❌ FAIL: {config_path} introuvable")
        return False
    
    with open(config_path, 'r') as f:
        content = f.read()
    
    # Chercher NEIGHBOR_RETENTION_HOURS = 720
    if 'NEIGHBOR_RETENTION_HOURS' not in content:
        print(f"❌ FAIL: NEIGHBOR_RETENTION_HOURS non trouvé dans {config_path}")
        return False
    
    # Vérifier la valeur est 720
    match = re.search(r'NEIGHBOR_RETENTION_HOURS\s*=\s*(\d+)', content)
    if not match:
        print(f"❌ FAIL: Impossible de parser NEIGHBOR_RETENTION_HOURS")
        return False
    
    value = int(match.group(1))
    if value != 720:
        print(f"❌ FAIL: NEIGHBOR_RETENTION_HOURS = {value}, attendu 720")
        return False
    
    print(f"✅ PASS: NEIGHBOR_RETENTION_HOURS = {value} (30 jours)")
    return True


def test_main_bot_usage():
    """Vérifier que main_bot.py utilise NEIGHBOR_RETENTION_HOURS"""
    print("\n📋 Test 2: Vérification de main_bot.py")
    
    main_bot_path = "main_bot.py"
    if not os.path.exists(main_bot_path):
        print(f"❌ FAIL: {main_bot_path} introuvable")
        return False
    
    with open(main_bot_path, 'r') as f:
        content = f.read()
    
    # Vérifier que le code utilise NEIGHBOR_RETENTION_HOURS
    if 'NEIGHBOR_RETENTION_HOURS' not in content:
        print(f"❌ FAIL: NEIGHBOR_RETENTION_HOURS non utilisé dans {main_bot_path}")
        return False
    
    # Vérifier que globals().get('NEIGHBOR_RETENTION_HOURS', 48) est utilisé
    if "globals().get('NEIGHBOR_RETENTION_HOURS'" not in content:
        print(f"❌ FAIL: Pattern globals().get('NEIGHBOR_RETENTION_HOURS') non trouvé")
        return False
    
    # Vérifier que cleanup_old_persisted_data utilise retention_hours
    if 'cleanup_old_persisted_data(hours=retention_hours)' not in content:
        print(f"❌ FAIL: cleanup_old_persisted_data n'utilise pas retention_hours")
        return False
    
    print(f"✅ PASS: main_bot.py utilise correctement NEIGHBOR_RETENTION_HOURS")
    return True


def test_export_script():
    """Vérifier que infoup_db.sh exporte 720h de données"""
    print("\n📋 Test 3: Vérification de map/infoup_db.sh")
    
    script_path = "map/infoup_db.sh"
    if not os.path.exists(script_path):
        print(f"❌ FAIL: {script_path} introuvable")
        return False
    
    with open(script_path, 'r') as f:
        content = f.read()
    
    # Compter les occurrences de "720" dans les commandes d'export
    count_720 = content.count(' 720')
    
    if count_720 < 2:  # Au moins 2: neighbor export et node export
        print(f"❌ FAIL: Pas assez d'occurrences de '720' ({count_720} trouvées, 2 attendues)")
        return False
    
    # Vérifier que les anciennes valeurs de 48 ont été remplacées
    # Chercher export_neighbors_from_db.py avec 48
    if 'export_neighbors_from_db.py $DB_PATH 48' in content:
        print(f"❌ FAIL: Ancienne valeur 48 trouvée pour export_neighbors_from_db.py")
        return False
    
    # Vérifier export_nodes_from_db.py avec 48
    if 'export_nodes_from_db.py "$NODE_NAMES_FILE" "$DB_PATH" 48' in content:
        print(f"❌ FAIL: Ancienne valeur 48 trouvée pour export_nodes_from_db.py")
        return False
    
    print(f"✅ PASS: infoup_db.sh utilise 720h (30 jours) pour tous les exports")
    return True


def test_documentation():
    """Vérifier que le commentaire explique bien la rétention de 30 jours"""
    print("\n📋 Test 4: Vérification de la documentation")
    
    config_path = "config.py.sample"
    with open(config_path, 'r') as f:
        content = f.read()
    
    # Chercher les commentaires explicatifs
    if '720h = 30 jours' not in content:
        print(f"❌ FAIL: Commentaire '720h = 30 jours' non trouvé")
        return False
    
    if 'Recommandé pour avoir une carte réseau bien peuplée' not in content:
        print(f"❌ FAIL: Explication sur la carte réseau non trouvée")
        return False
    
    print(f"✅ PASS: Documentation claire et explicative")
    return True


def main():
    """Exécuter tous les tests"""
    print("=" * 60)
    print("🧪 TESTS DE RÉTENTION DES DONNÉES DE VOISINAGE (30 JOURS)")
    print("=" * 60)
    
    all_passed = True
    
    all_passed &= test_config_sample()
    all_passed &= test_main_bot_usage()
    all_passed &= test_export_script()
    all_passed &= test_documentation()
    
    print("\n" + "=" * 60)
    if all_passed:
        print("✅ TOUS LES TESTS RÉUSSIS")
        print("=" * 60)
        return 0
    else:
        print("❌ CERTAINS TESTS ONT ÉCHOUÉ")
        print("=" * 60)
        return 1


if __name__ == "__main__":
    sys.exit(main())
