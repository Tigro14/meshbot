#!/usr/bin/env python3
"""
Analyseur des logs de conversations du bot Meshtastic
"""

import re
import sys
from datetime import datetime, timedelta
from collections import defaultdict, Counter

LOG_FILE = "/home/dietpi/logs/bot_conversations.log"

def parse_conversations(log_file):
    """Parse le fichier de logs et extrait les conversations"""
    conversations = []
    
    try:
        with open(log_file, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Regex pour extraire les conversations
        pattern = r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) - INFO - ={80}\n.*?CONVERSATION - (.*?)\n.*?QUERY: (.*?)\n.*?RESPONSE: (.*?)\n.*?(?:PROCESSING_TIME: ([\d.]+)s\n)?'
        
        matches = re.findall(pattern, content, re.DOTALL)
        
        for match in matches:
            timestamp_str, sender, query, response, processing_time = match
            
            timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
            
            conversations.append({
                'timestamp': timestamp,
                'sender': sender.strip(),
                'query': query.strip(),
                'response': response.strip(),
                'processing_time': float(processing_time) if processing_time else None
            })
            
    except FileNotFoundError:
        print(f"❌ Fichier de logs non trouvé: {log_file}")
        return []
    except Exception as e:
        print(f"❌ Erreur de lecture: {e}")
        return []
    
    return conversations

def analyze_conversations(conversations):
    """Analyse les conversations"""
    if not conversations:
        print("📊 Aucune conversation à analyser")
        return
    
    print("📊 ANALYSE DES CONVERSATIONS")
    print("=" * 50)
    
    # Statistiques générales
    total = len(conversations)
    print(f"📈 Total des conversations: {total}")
    
    # Période couverte
    if conversations:
        start_date = min(conv['timestamp'] for conv in conversations)
        end_date = max(conv['timestamp'] for conv in conversations)
        print(f"📅 Période: {start_date.strftime('%Y-%m-%d %H:%M')} → {end_date.strftime('%Y-%m-%d %H:%M')}")
        
        # Durée totale
        duration = end_date - start_date
        print(f"⏱️  Durée totale: {duration.days} jours, {duration.seconds//3600}h{(duration.seconds//60)%60}m")
    
    print()
    
    # Utilisateurs les plus actifs
    user_counts = Counter(conv['sender'] for conv in conversations)
    print("👥 UTILISATEURS LES PLUS ACTIFS:")
    for user, count in user_counts.most_common(10):
        print(f"  • {user}: {count} conversations ({count/total*100:.1f}%)")
    print()
    
    # Analyse temporelle
    hourly_stats = defaultdict(int)
    daily_stats = defaultdict(int)
    
    for conv in conversations:
        hour = conv['timestamp'].hour
        date = conv['timestamp'].date()
        hourly_stats[hour] += 1
        daily_stats[date] += 1
    
    print("🕐 RÉPARTITION PAR HEURE:")
    for hour in range(24):
        count = hourly_stats[hour]
        bar = "█" * min(count, 50)
        print(f"  {hour:2d}h: {count:3d} {bar}")
    print()
    
    print("📅 ACTIVITÉ DES 7 DERNIERS JOURS:")
    for i in range(7):
        date = (datetime.now().date() - timedelta(days=i))
        count = daily_stats[date]
        print(f"  {date}: {count} conversations")
    print()
    
    # Analyse des temps de traitement
    processing_times = [conv['processing_time'] for conv in conversations if conv['processing_time']]
    if processing_times:
        avg_time = sum(processing_times) / len(processing_times)
        min_time = min(processing_times)
        max_time = max(processing_times)
        
        print("⚡ TEMPS DE TRAITEMENT:")
        print(f"  Moyen: {avg_time:.2f}s")
        print(f"  Min: {min_time:.2f}s")
        print(f"  Max: {max_time:.2f}s")
        
        # Répartition par tranches
        quick = len([t for t in processing_times if t < 2])
        normal = len([t for t in processing_times if 2 <= t < 10])
        slow = len([t for t in processing_times if t >= 10])
        
        print(f"  Rapide (<2s): {quick} ({quick/len(processing_times)*100:.1f}%)")
        print(f"  Normal (2-10s): {normal} ({normal/len(processing_times)*100:.1f}%)")
        print(f"  Lent (>10s): {slow} ({slow/len(processing_times)*100:.1f}%)")
    print()
    
    # Questions les plus fréquentes (mots-clés)
    all_queries = ' '.join(conv['query'].lower() for conv in conversations)
    words = re.findall(r'\b\w+\b', all_queries)
    common_words = Counter(words).most_common(10)
    
    print("🔤 MOTS-CLÉS LES PLUS FRÉQUENTS:")
    for word, count in common_words:
        if len(word) > 2:  # Ignorer les mots trop courts
            print(f"  • {word}: {count}")
    print()

def show_recent_conversations(conversations, limit=10):
    """Affiche les conversations les plus récentes"""
    recent = sorted(conversations, key=lambda x: x['timestamp'], reverse=True)[:limit]
    
    print(f"💬 CONVERSATIONS RÉCENTES ({limit} dernières):")
    print("=" * 50)
    
    for i, conv in enumerate(recent, 1):
        timestamp = conv['timestamp'].strftime('%Y-%m-%d %H:%M:%S')
        sender = conv['sender']
        query = conv['query'][:100] + "..." if len(conv['query']) > 100 else conv['query']
        response = conv['response'][:100] + "..." if len(conv['response']) > 100 else conv['response']
        processing_time = f" ({conv['processing_time']:.1f}s)" if conv['processing_time'] else ""
        
        print(f"\n{i}. [{timestamp}] {sender}{processing_time}")
        print(f"   Q: {query}")
        print(f"   R: {response}")

def main():
    if len(sys.argv) > 1:
        command = sys.argv[1]
    else:
        command = "analyze"
    
    conversations = parse_conversations(LOG_FILE)
    
    if command == "analyze":
        analyze_conversations(conversations)
    elif command == "recent":
        limit = int(sys.argv[2]) if len(sys.argv) > 2 else 10
        show_recent_conversations(conversations, limit)
    elif command == "search":
        if len(sys.argv) < 3:
            print("Usage: python3 conversation_analyzer.py search <mot_clé>")
            sys.exit(1)
        
        keyword = sys.argv[2].lower()
        matches = [conv for conv in conversations 
                  if keyword in conv['query'].lower() or keyword in conv['response'].lower()]
        
        print(f"🔍 CONVERSATIONS CONTENANT '{keyword}' ({len(matches)} résultats):")
        show_recent_conversations(matches, len(matches))
    else:
        print("Usage:")
        print("  python3 conversation_analyzer.py analyze     # Analyse complète")
        print("  python3 conversation_analyzer.py recent [N]  # N conversations récentes")
        print("  python3 conversation_analyzer.py search <mot> # Recherche par mot-clé")

if __name__ == "__main__":
    main()
