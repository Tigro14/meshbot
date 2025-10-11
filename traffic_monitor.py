def get_traffic_report(self, hours=8):
    """
    Générer un rapport de trafic complet pour une période donnée
    Combine messages publics + top talkers
    
    Args:
        hours: Période à analyser (défaut: 8h)
    
    Returns:
        str: Rapport formaté
    """
    try:
        current_time = time.time()
        cutoff_time = current_time - (hours * 3600)
        
        # Compter les messages de la période
        recent_messages = [
            msg for msg in self.public_messages
            if msg['timestamp'] >= cutoff_time
        ]
        
        if not recent_messages:
            return f"📊 Aucune activité publique dans les {hours}h"
        
        # Statistiques de base
        lines = []
        lines.append(f"📊 TRAFIC PUBLIC ({hours}h)")
        lines.append(f"{'='*30}")
        lines.append(f"Messages: {len(recent_messages)}")
        
        # Nœuds actifs
        unique_nodes = set(msg['from_id'] for msg in recent_messages)
        lines.append(f"Nœuds actifs: {len(unique_nodes)}")
        
        # Moyenne messages/heure
        avg_per_hour = len(recent_messages) / hours
        lines.append(f"Moy: {avg_per_hour:.1f} msg/h")
        
        lines.append("")
        
        # Top 5 talkers de la période
        talker_counts = defaultdict(lambda: {'count': 0, 'name': ''})
        for msg in recent_messages:
            from_id = msg['from_id']
            talker_counts[from_id]['count'] += 1
            talker_counts[from_id]['name'] = msg['sender_name']
        
        # Trier par nombre de messages
        sorted_talkers = sorted(
            talker_counts.items(),
            key=lambda x: x[1]['count'],
            reverse=True
        )[:5]
        
        if sorted_talkers:
            lines.append("🏆 TOP 5:")
            for i, (node_id, data) in enumerate(sorted_talkers, 1):
                name_short = truncate_text(data['name'], 10)
                count = data['count']
                percentage = (count / len(recent_messages) * 100)
                
                # Emoji selon le rang
                if i == 1:
                    emoji = "🥇"
                elif i == 2:
                    emoji = "🥈"
                elif i == 3:
                    emoji = "🥉"
                else:
                    emoji = f"{i}."
                
                lines.append(f"{emoji} {name_short}: {count} ({percentage:.0f}%)")
        
        # Heure de pointe
        lines.append("")
        hourly_distribution = defaultdict(int)
        for msg in recent_messages:
            hour = datetime.fromtimestamp(msg['timestamp']).hour
            hourly_distribution[hour] += 1
        
        if hourly_distribution:
            peak = max(hourly_distribution.items(), key=lambda x: x[1])
            lines.append(f"⏰ Pointe: {peak[0]:02d}h00 ({peak[1]} msgs)")
        
        return "\n".join(lines)
        
    except Exception as e:
        error_print(f"Erreur génération rapport trafic: {e}")
        import traceback
        error_print(traceback.format_exc())
        return f"❌ Erreur: {str(e)[:50]}"
