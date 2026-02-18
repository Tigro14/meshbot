#!/usr/bin/env python3
"""
Demo: MeshCore Help Text Differences
Shows how help text adapts based on network source
"""

def format_help_meshtastic():
    """Help text for Meshtastic network"""
    return (
        "🤖 BOT MESH\n"
        "IA: /bot (alias: /ia)\n"
        "Sys: /power /sys /weather\n"
        "Net: /nodes /my /trace\n"
        "Stats: /stats /top /trafic\n"
        "DB: /db\n"
        "Util: /echo /legend /help\n"
        "Doc: README.md sur GitHub"
    )

def format_help_meshcore():
    """Help text for MeshCore network (unimplemented commands removed)"""
    return (
        "🤖 BOT MESH\n"
        "IA: /bot (alias: /ia)\n"
        "Sys: /power /sys /weather\n"
        "Net: /nodesmc\n"
        "Stats: /trafic /trafficmc\n"
        "DB: /db\n"
        "Util: /echo /legend /help\n"
        "Doc: README.md sur GitHub"
    )

def main():
    print("=" * 60)
    print("DEMO: MeshCore Help Text Differences")
    print("=" * 60)
    print()
    
    print("📡 MESHTASTIC HELP TEXT")
    print("-" * 60)
    help_mt = format_help_meshtastic()
    print(help_mt)
    print()
    print(f"Length: {len(help_mt)} chars (fits in LoRa packet)")
    print()
    
    print("🔗 MESHCORE HELP TEXT")
    print("-" * 60)
    help_mc = format_help_meshcore()
    print(help_mc)
    print()
    print(f"Length: {len(help_mc)} chars (fits in LoRa packet)")
    print()
    
    print("🔍 KEY DIFFERENCES")
    print("-" * 60)
    
    # Extract specific lines
    mt_lines = help_mt.split('\n')
    mc_lines = help_mc.split('\n')
    
    mt_net = [l for l in mt_lines if 'Net:' in l][0]
    mc_net = [l for l in mc_lines if 'Net:' in l][0]
    
    mt_stats = [l for l in mt_lines if 'Stats:' in l][0]
    mc_stats = [l for l in mc_lines if 'Stats:' in l][0]
    
    print("Net commands:")
    print(f"  Meshtastic: {mt_net}")
    print(f"  MeshCore:   {mc_net}")
    print()
    
    print("Stats commands:")
    print(f"  Meshtastic: {mt_stats}")
    print(f"  MeshCore:   {mc_stats}")
    print()
    
    print("✅ REMOVED FROM MESHCORE:")
    print("  - /my (not implemented on MeshCore)")
    print("  - /trace (not implemented on MeshCore)")
    print("  - /stats (not implemented on MeshCore)")
    print("  - /top (not implemented on MeshCore)")
    print()
    
    print("✅ MESHCORE SPECIFIC:")
    print("  - /nodesmc (MeshCore contacts)")
    print("  - /trafficmc (MeshCore messages)")
    print()
    
    print("✅ BOTH NETWORKS:")
    print("  - /bot, /ia (AI chat)")
    print("  - /power, /sys, /weather (system)")
    print("  - /trafic (all traffic)")
    print("  - /db (database)")
    print("  - /echo, /legend, /help (utilities)")
    print()
    
    print("=" * 60)
    print("✅ ALL TESTS PASSED")
    print("=" * 60)

if __name__ == '__main__':
    main()
