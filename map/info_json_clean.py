#!/usr/bin/env python3
"""
Script pour nettoyer le fichier info.json de Meshtastic
et extraire uniquement les données des nœuds
"""

import json
import re
import sys

def clean_meshtastic_output(input_file, output_file):
    """
    Lit le fichier de sortie Meshtastic et extrait le JSON des nœuds
    """
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Chercher la section "Nodes in mesh:"
        match = re.search(r'Nodes in mesh:\s*(\{.*?\n\})\s*\nPreferences:', content, re.DOTALL)
        
        if not match:
            print("❌ Impossible de trouver la section 'Nodes in mesh'")
            return False
        
        nodes_json_str = match.group(1)
        
        # Parser le JSON
        try:
            nodes_data = json.loads(nodes_json_str)
        except json.JSONDecodeError as e:
            print(f"❌ Erreur lors du parsing JSON: {e}")
            return False
        
        # Créer la structure finale
        output_data = {
            "Nodes in mesh": nodes_data
        }
        
        # Écrire le fichier propre
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)
        
        node_count = len(nodes_data)
        print(f"✅ Fichier nettoyé avec succès!")
        print(f"📊 Nombre de nœuds: {node_count}")
        print(f"💾 Fichier sauvegardé: {output_file}")
        
        return True
        
    except FileNotFoundError:
        print(f"❌ Fichier '{input_file}' non trouvé")
        return False
    except Exception as e:
        print(f"❌ Erreur: {e}")
        return False

if __name__ == "__main__":
    input_file = "info.json"
    output_file = "info_clean.json"
    
    if len(sys.argv) > 1:
        input_file = sys.argv[1]
    if len(sys.argv) > 2:
        output_file = sys.argv[2]
    
    print(f"🔄 Nettoyage de {input_file}...")
    success = clean_meshtastic_output(input_file, output_file)
    
    if success:
        print("\n✨ Vous pouvez maintenant utiliser info_clean.json avec votre carte HTML")
        print("💡 Pensez à renommer 'info_clean.json' en 'info.json' ou à modifier meshlink.html")
    else:
        sys.exit(1)
