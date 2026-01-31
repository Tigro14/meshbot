#!/usr/bin/env python3
"""
Script de diagnostic pour config_priv.py
Aide à identifier pourquoi config_priv.py n'est pas importé correctement
"""

import os
import sys
import py_compile
import tempfile

def main():
    print("=" * 70)
    print("DIAGNOSTIC config_priv.py")
    print("=" * 70)
    print()
    
    # 1. Vérifier le répertoire de travail
    current_dir = os.getcwd()
    print(f"1. Répertoire de travail actuel: {current_dir}")
    print()
    
    # 2. Vérifier l'emplacement du script config.py
    config_py_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.py')
    config_dir = os.path.dirname(config_py_path)
    print(f"2. Répertoire de config.py: {config_dir}")
    print()
    
    # 3. Chercher config_priv.py
    config_priv_path = os.path.join(config_dir, 'config_priv.py')
    print(f"3. Chemin attendu pour config_priv.py: {config_priv_path}")
    print(f"   Fichier existe: {os.path.exists(config_priv_path)}")
    print()
    
    if not os.path.exists(config_priv_path):
        print("❌ PROBLÈME: config_priv.py n'existe pas!")
        print()
        print("SOLUTION:")
        print(f"   cd {config_dir}")
        print("   cp config.priv.py.sample config_priv.py")
        print("   nano config_priv.py")
        print("   # Remplir vos valeurs réelles")
        print()
        return 1
    
    # 4. Vérifier les permissions
    stat_info = os.stat(config_priv_path)
    permissions = oct(stat_info.st_mode)[-3:]
    print(f"4. Permissions du fichier: {permissions}")
    print(f"   Lisible: {os.access(config_priv_path, os.R_OK)}")
    print()
    
    if not os.access(config_priv_path, os.R_OK):
        print("❌ PROBLÈME: Fichier non lisible!")
        print()
        print("SOLUTION:")
        print(f"   chmod 644 {config_priv_path}")
        print()
        return 1
    
    # 5. Vérifier la taille
    size = os.path.getsize(config_priv_path)
    print(f"5. Taille du fichier: {size} octets")
    print()
    
    if size == 0:
        print("❌ PROBLÈME: Fichier vide!")
        print()
        print("SOLUTION:")
        print(f"   cd {config_dir}")
        print("   cp config.priv.py.sample config_priv.py")
        print("   nano config_priv.py")
        print()
        return 1
    
    # 6. Afficher le contenu (masqué)
    print("6. Contenu du fichier (valeurs masquées):")
    try:
        with open(config_priv_path, 'r') as f:
            lines = f.readlines()
            for i, line in enumerate(lines[:20], 1):  # Afficher les 20 premières lignes
                # Masquer les valeurs sensibles
                if '=' in line and not line.strip().startswith('#'):
                    key, value = line.split('=', 1)
                    print(f"   {i:3d}: {key.strip()} = ***MASQUÉ***")
                else:
                    print(f"   {i:3d}: {line.rstrip()}")
        if len(lines) > 20:
            print(f"   ... ({len(lines) - 20} lignes supplémentaires)")
    except Exception as e:
        print(f"   ❌ Erreur de lecture: {e}")
    print()
    
    # 7. Vérifier la syntaxe Python
    print("7. Vérification de la syntaxe Python:")
    try:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.pyc', delete=False) as tmp:
            tmp_path = tmp.name
        
        py_compile.compile(config_priv_path, tmp_path, doraise=True)
        print("   ✅ Syntaxe Python correcte")
        os.remove(tmp_path)
    except py_compile.PyCompileError as e:
        print(f"   ❌ ERREUR DE SYNTAXE:")
        print(f"      {e}")
        print()
        print("SOLUTION:")
        print("   Corriger l'erreur de syntaxe dans config_priv.py")
        print("   Vérifier les guillemets, virgules, crochets, etc.")
        print()
        return 1
    print()
    
    # 8. Tester l'import
    print("8. Test d'import:")
    try:
        # Ajouter le répertoire au path si nécessaire
        if config_dir not in sys.path:
            sys.path.insert(0, config_dir)
        
        # Supprimer le module du cache s'il existe
        if 'config_priv' in sys.modules:
            del sys.modules['config_priv']
        
        # Tenter l'import
        import config_priv
        
        print("   ✅ Import réussi!")
        print()
        
        # Vérifier que les variables requises sont définies
        required_vars = [
            'TELEGRAM_BOT_TOKEN',
            'TELEGRAM_AUTHORIZED_USERS',
            'REBOOT_PASSWORD',
        ]
        
        missing_vars = []
        for var in required_vars:
            if not hasattr(config_priv, var):
                missing_vars.append(var)
        
        if missing_vars:
            print(f"   ⚠️  Variables manquantes: {missing_vars}")
            print()
            print("SOLUTION:")
            print("   Ajouter ces variables dans config_priv.py")
            print("   Voir config.priv.py.sample pour les exemples")
            print()
            return 1
        else:
            print("   ✅ Toutes les variables requises sont présentes")
            
            # Afficher les valeurs (partiellement masquées)
            print()
            print("   Variables trouvées:")
            if hasattr(config_priv, 'TELEGRAM_BOT_TOKEN'):
                token = config_priv.TELEGRAM_BOT_TOKEN
                if token and token != "******************":
                    masked = f"{token[:10]}...{token[-4:]}" if len(token) > 14 else "***"
                    print(f"      TELEGRAM_BOT_TOKEN = {masked}")
                else:
                    print(f"      TELEGRAM_BOT_TOKEN = {token} (⚠️  valeur par défaut)")
            
            if hasattr(config_priv, 'REBOOT_PASSWORD'):
                pwd = config_priv.REBOOT_PASSWORD
                if pwd and pwd != "your_password_secret":
                    print(f"      REBOOT_PASSWORD = ***{len(pwd)} caractères***")
                else:
                    print(f"      REBOOT_PASSWORD = {pwd} (⚠️  valeur par défaut)")
            
            if hasattr(config_priv, 'TELEGRAM_AUTHORIZED_USERS'):
                users = config_priv.TELEGRAM_AUTHORIZED_USERS
                print(f"      TELEGRAM_AUTHORIZED_USERS = {len(users)} utilisateur(s)")
        
    except ImportError as e:
        print(f"   ❌ ERREUR D'IMPORT: {e}")
        print()
        print("   Cela peut arriver si:")
        print("   - Il y a une erreur dans le fichier")
        print("   - Il manque des imports dans config_priv.py")
        print("   - Le nom du fichier n'est pas exactement 'config_priv.py'")
        print()
        return 1
    except Exception as e:
        print(f"   ❌ ERREUR INATTENDUE: {e}")
        import traceback
        traceback.print_exc()
        print()
        return 1
    
    print()
    print("=" * 70)
    print("✅ DIAGNOSTIC TERMINÉ - Aucun problème détecté")
    print("=" * 70)
    print()
    print("Si le bot utilise toujours les valeurs par défaut, vérifier:")
    print("  1. Que le bot démarre depuis le bon répertoire")
    print(f"     (doit être: {config_dir})")
    print("  2. Que le service systemd a les bonnes permissions")
    print("  3. Redémarrer le bot: sudo systemctl restart meshbot")
    print()
    
    return 0

if __name__ == '__main__':
    sys.exit(main())
