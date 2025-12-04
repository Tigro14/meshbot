#!/usr/bin/env python3
"""
Commandes de gestion de la base de données SQLite
Opérations de maintenance, stats et nettoyage
"""

import os
import time
from utils import error_print, debug_print, info_print
import traceback


class DBCommands:
    """
    Gestionnaire unifié des opérations de base de données
    Accessible depuis Mesh ET Telegram avec adaptation automatique
    """

    def __init__(self, traffic_monitor, sender):
        """
        Args:
            traffic_monitor: Instance de TrafficMonitor (avec persistence)
            sender: Instance de MessageSender
        """
        self.traffic_monitor = traffic_monitor
        self.sender = sender
        self.persistence = traffic_monitor.persistence if traffic_monitor else None

    def handle_db(self, sender_id, sender_info, params, channel='mesh'):
        """
        Point d'entrée unifié pour toutes les opérations DB

        Args:
            sender_id: ID de l'expéditeur
            sender_info: Infos sur l'expéditeur
            params: Liste de paramètres [subcommand, ...args]
            channel: 'mesh' ou 'telegram'
        """
        # Vérifier le throttling
        if not self.sender.check_throttling(sender_id, sender_info):
            return

        # Parser la sous-commande
        subcommand = params[0].lower() if params else ''
        args = params[1:] if len(params) > 1 else []

        try:
            if subcommand == '':
                response = self._get_help(channel)
            elif subcommand in ['stats', 's']:
                response = self._get_db_stats(channel)
            elif subcommand in ['clean', 'cleanup']:
                response = self._cleanup_db(args, channel)
            elif subcommand in ['vacuum', 'v']:
                response = self._vacuum_db(channel)
            elif subcommand in ['info', 'i']:
                response = self._get_db_info(channel)
            elif subcommand in ['purgeweather', 'pw']:
                response = self._purge_weather_cache(channel)
            elif subcommand in ['nb', 'neighbors']:
                response = self._get_neighbors_stats(channel)
            else:
                response = self._get_help(channel)

            # Envoyer la réponse
            self.sender.send_chunks(response, sender_id, sender_info)

        except Exception as e:
            error_print(f"Erreur handle_db({subcommand}): {e}")
            error_print(traceback.format_exc())
            self.sender.send_message(
                f"❌ Erreur: {str(e)[:100]}",
                sender_id, sender_info
            )

    def _get_help(self, channel='mesh'):
        """Afficher l'aide des commandes DB"""
        if channel == 'mesh':
            return (
                "🗄️ /db [cmd]\n"
                "s=stats i=info\n"
                "nb=neighbors\n"
                "clean=nettoyage\n"
                "v=vacuum pw=weather"
            )
        else:  # telegram
            return """🗄️ BASE DE DONNÉES - OPTIONS

Sous-commandes:
• stats - Statistiques DB
• info - Informations détaillées
• nb - Stats voisinage (neighbors)
• clean [hours] - Nettoyer données anciennes
• vacuum - Optimiser DB (VACUUM)

Exemples:
• /db stats - Stats DB
• /db nb - Stats voisinage
• /db clean 72 - Nettoyer > 72h
• /db vacuum - Optimiser

Raccourcis: s, i, v, nb
"""

    def _get_db_stats(self, channel='mesh'):
        """Obtenir les statistiques de la base de données"""
        if not self.persistence:
            return "❌ DB non disponible"

        try:
            import sqlite3

            # Taille du fichier
            db_path = self.persistence.db_path
            if os.path.exists(db_path):
                db_size = os.path.getsize(db_path)
                db_size_mb = db_size / (1024 * 1024)
            else:
                return "❌ Fichier DB introuvable"

            # Compter les entrées par table
            cursor = self.persistence.conn.cursor()

            # Packets
            cursor.execute("SELECT COUNT(*) FROM packets")
            packets_count = cursor.fetchone()[0]

            # Messages publics
            cursor.execute("SELECT COUNT(*) FROM public_messages")
            messages_count = cursor.fetchone()[0]

            # Node stats (si existe)
            try:
                cursor.execute("SELECT COUNT(*) FROM node_stats")
                node_stats_count = cursor.fetchone()[0]
            except:
                node_stats_count = 0

            # Plage temporelle
            cursor.execute("SELECT MIN(timestamp), MAX(timestamp) FROM packets")
            result = cursor.fetchone()
            if result and result[0]:
                min_ts, max_ts = result
                from datetime import datetime
                oldest = datetime.fromtimestamp(min_ts).strftime('%d/%m %H:%M')
                newest = datetime.fromtimestamp(max_ts).strftime('%d/%m %H:%M')
                span_hours = (max_ts - min_ts) / 3600
            else:
                oldest = newest = "N/A"
                span_hours = 0

            # Format selon canal
            if channel == 'mesh':
                lines = [
                    f"🗄️ DB: {db_size_mb:.1f}MB",
                    f"{packets_count}pkt {messages_count}msg",
                    f"{oldest}-{newest}",
                    f"({span_hours:.0f}h)"
                ]
            else:  # telegram
                lines = [
                    "🗄️ STATISTIQUES BASE DE DONNÉES",
                    "=" * 50,
                    "",
                    f"📊 Taille: {db_size_mb:.2f} MB",
                    f"Fichier: {os.path.basename(db_path)}",
                    "",
                    "📦 Entrées:",
                    f"• Paquets: {packets_count:,}",
                    f"• Messages publics: {messages_count:,}",
                    f"• Stats nœuds: {node_stats_count:,}",
                    "",
                    "⏰ Plage temporelle:",
                    f"• Plus ancien: {oldest}",
                    f"• Plus récent: {newest}",
                    f"• Durée: {span_hours:.1f} heures",
                ]

            return "\n".join(lines)

        except Exception as e:
            error_print(f"Erreur DB stats: {e}")
            return f"❌ Erreur: {str(e)[:100]}"

    def _cleanup_db(self, args, channel='mesh'):
        """Nettoyer les données anciennes de la DB"""
        if not self.persistence:
            return "❌ DB non disponible"

        # Parser les heures
        hours = 48  # Défaut
        if args:
            try:
                hours = int(args[0])
                hours = max(1, min(168, hours))  # 1h à 1 semaine
            except ValueError:
                pass

        try:
            # Compter avant
            cursor = self.persistence.conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM packets")
            before_packets = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM public_messages")
            before_messages = cursor.fetchone()[0]

            # Nettoyer
            info_print(f"🧹 Nettoyage DB: données > {hours}h")
            self.persistence.cleanup_old_data(hours=hours)

            # Compter après
            cursor.execute("SELECT COUNT(*) FROM packets")
            after_packets = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM public_messages")
            after_messages = cursor.fetchone()[0]

            deleted_packets = before_packets - after_packets
            deleted_messages = before_messages - after_messages

            # Format selon canal
            if channel == 'mesh':
                return (
                    f"🧹 Nettoyé ({hours}h)\n"
                    f"-{deleted_packets}pkt\n"
                    f"-{deleted_messages}msg"
                )
            else:  # telegram
                return (
                    f"🧹 NETTOYAGE EFFECTUÉ\n\n"
                    f"Critère: > {hours} heures\n\n"
                    f"Supprimés:\n"
                    f"• Paquets: {deleted_packets:,}\n"
                    f"• Messages: {deleted_messages:,}\n\n"
                    f"Restants:\n"
                    f"• Paquets: {after_packets:,}\n"
                    f"• Messages: {after_messages:,}"
                )

        except Exception as e:
            error_print(f"Erreur cleanup DB: {e}")
            return f"❌ Erreur: {str(e)[:100]}"

    def _vacuum_db(self, channel='mesh'):
        """Optimiser la base de données (VACUUM)"""
        if not self.persistence:
            return "❌ DB non disponible"

        try:
            # Taille avant
            db_path = self.persistence.db_path
            size_before = os.path.getsize(db_path) / (1024 * 1024)

            info_print("🔧 Optimisation DB (VACUUM)...")
            cursor = self.persistence.conn.cursor()
            cursor.execute("VACUUM")
            self.persistence.conn.commit()

            # Taille après
            size_after = os.path.getsize(db_path) / (1024 * 1024)
            saved = size_before - size_after

            if channel == 'mesh':
                return (
                    f"🔧 DB optimisée\n"
                    f"{size_before:.1f}→{size_after:.1f}MB\n"
                    f"(-{saved:.1f}MB)"
                )
            else:  # telegram
                return (
                    f"🔧 DATABASE OPTIMISÉE\n\n"
                    f"Taille avant: {size_before:.2f} MB\n"
                    f"Taille après: {size_after:.2f} MB\n"
                    f"Économisé: {saved:.2f} MB\n\n"
                    f"✅ VACUUM terminé avec succès"
                )

        except Exception as e:
            error_print(f"Erreur VACUUM: {e}")
            return f"❌ Erreur: {str(e)[:100]}"

    def _get_db_info(self, channel='mesh'):
        """Informations détaillées sur la base de données"""
        if not self.persistence:
            return "❌ DB non disponible"

        try:
            cursor = self.persistence.conn.cursor()
            db_path = self.persistence.db_path

            # Tables
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]

            # Schema info
            table_info = {}
            for table in tables:
                cursor.execute(f"PRAGMA table_info({table})")
                columns = cursor.fetchall()
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                count = cursor.fetchone()[0]
                table_info[table] = {
                    'columns': len(columns),
                    'count': count
                }

            # Indexes
            cursor.execute("SELECT name FROM sqlite_master WHERE type='index'")
            indexes = cursor.fetchall()

            if channel == 'mesh':
                lines = [
                    "🗄️ DB Info",
                    f"{len(tables)}t {len(indexes)}idx",
                ]
                for table, info in table_info.items():
                    lines.append(f"{table[:10]}:{info['count']}")
            else:  # telegram
                lines = [
                    "🗄️ INFORMATIONS BASE DE DONNÉES",
                    "=" * 50,
                    "",
                    f"Fichier: {os.path.basename(db_path)}",
                    f"Chemin: {db_path}",
                    "",
                    f"📊 Structure:",
                    f"• Tables: {len(tables)}",
                    f"• Index: {len(indexes)}",
                    "",
                    "📦 Tables:"
                ]

                for table, info in table_info.items():
                    lines.append(
                        f"• {table}: {info['count']:,} entrées, "
                        f"{info['columns']} colonnes"
                    )

            return "\n".join(lines)

        except Exception as e:
            error_print(f"Erreur DB info: {e}")
            return f"❌ Erreur: {str(e)[:100]}"

    def _purge_weather_cache(self, channel='mesh'):
        """Purger le cache météo de la base de données"""
        if not self.persistence:
            return "❌ DB non disponible"

        try:
            # Compter les entrées avant suppression
            cursor = self.persistence.conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM weather_cache")
            count_before = cursor.fetchone()[0]

            if count_before == 0:
                if channel == 'mesh':
                    return "✅ Cache météo vide"
                else:
                    return "✅ **Cache météo déjà vide**\n\nAucune donnée à purger."

            # Purger tout le cache météo (age=0 supprime tout)
            deleted = self.persistence.cleanup_weather_cache(max_age_hours=0)

            # Message de confirmation
            if channel == 'mesh':
                return f"✅ {deleted} entrées purgées"
            else:
                return f"""✅ **Cache météo purgé**

**Résumé:**
• Entrées supprimées: {deleted}
• Tables: weather_cache
• Prochaine requête météo rechargera les données

**Types de cache supprimés:**
• Prévisions météo
• Graphiques de pluie
• Données astronomiques
"""

        except Exception as e:
            error_print(f"Erreur purge weather cache: {e}")
            error_print(traceback.format_exc())
            return f"❌ Erreur: {str(e)[:100]}"

    def _get_neighbors_stats(self, channel='mesh'):
        """Obtenir les statistiques de la table neighbors"""
        if not self.persistence:
            return "❌ DB non disponible"

        try:
            cursor = self.persistence.conn.cursor()

            # Vérifier si la table neighbors existe
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='neighbors'
            """)
            if not cursor.fetchone():
                if channel == 'mesh':
                    return "❌ Table neighbors inexistante"
                else:
                    return "❌ **Table neighbors inexistante**\n\nLa table de voisinage n'est pas disponible dans cette base de données."

            # Compter les entrées totales
            cursor.execute("SELECT COUNT(*) FROM neighbors")
            total_entries = cursor.fetchone()[0]

            if total_entries == 0:
                if channel == 'mesh':
                    return "👥 Aucune donnée voisinage"
                else:
                    return """👥 **AUCUNE DONNÉE DE VOISINAGE**

La table neighbors est vide. Les données de voisinage sont collectées:
• Depuis les paquets NEIGHBORINFO_APP reçus
• Depuis le serveur MQTT (si activé)

Vérifiez que:
• Les nœuds mesh ont neighborinfo activé
• Le bot reçoit bien les paquets
• Le collecteur MQTT fonctionne (si configuré)
"""

            # Compter les nœuds uniques (qui ont des voisins)
            cursor.execute("SELECT COUNT(DISTINCT node_id) FROM neighbors")
            unique_nodes = cursor.fetchone()[0]

            # Compter les relations uniques (node -> neighbor)
            cursor.execute("""
                SELECT COUNT(DISTINCT node_id || '-' || neighbor_id) 
                FROM neighbors
            """)
            unique_relationships = cursor.fetchone()[0]

            # Plage temporelle
            cursor.execute("SELECT MIN(timestamp), MAX(timestamp) FROM neighbors")
            result = cursor.fetchone()
            if result and result[0]:
                min_ts, max_ts = result
                from datetime import datetime
                oldest = datetime.fromtimestamp(min_ts).strftime('%d/%m %H:%M')
                newest = datetime.fromtimestamp(max_ts).strftime('%d/%m %H:%M')
                span_hours = (max_ts - min_ts) / 3600
            else:
                oldest = newest = "N/A"
                span_hours = 0

            # Moyenne de voisins par nœud
            avg_neighbors = unique_relationships / unique_nodes if unique_nodes > 0 else 0

            # Top 5 des nœuds avec le plus de voisins (pour Telegram)
            cursor.execute("""
                SELECT node_id, COUNT(DISTINCT neighbor_id) as neighbor_count
                FROM neighbors
                GROUP BY node_id
                ORDER BY neighbor_count DESC
                LIMIT 5
            """)
            top_nodes = cursor.fetchall()

            # Format selon canal
            if channel == 'mesh':
                lines = [
                    f"👥 Voisinage:",
                    f"{unique_nodes}nœuds {unique_relationships}liens",
                    f"{total_entries}entrées",
                    f"Moy:{avg_neighbors:.1f}v/nœud"
                ]
            else:  # telegram
                lines = [
                    "👥 **STATISTIQUES DE VOISINAGE**",
                    "=" * 50,
                    "",
                    f"📊 **Données globales:**",
                    f"• Total entrées: {total_entries:,}",
                    f"• Nœuds avec voisins: {unique_nodes:,}",
                    f"• Relations uniques: {unique_relationships:,}",
                    f"• Moyenne voisins/nœud: {avg_neighbors:.2f}",
                    "",
                    f"⏰ **Plage temporelle:**",
                    f"• Plus ancien: {oldest}",
                    f"• Plus récent: {newest}",
                    f"• Durée: {span_hours:.1f} heures",
                ]

                # Ajouter le top 5 pour Telegram
                if top_nodes:
                    lines.append("")
                    lines.append("🏆 **Top 5 nœuds (plus de voisins):**")
                    for node_id, count in top_nodes:
                        # Convertir node_id en int pour get_node_name
                        try:
                            if node_id.startswith('!'):
                                node_num = int(node_id[1:], 16)
                            else:
                                node_num = int(node_id, 16)
                            
                            # Obtenir le nom du nœud
                            node_name = "Unknown"
                            if self.traffic_monitor and self.traffic_monitor.node_manager:
                                node_name = self.traffic_monitor.node_manager.get_node_name(node_num)
                            
                            lines.append(f"• {node_name} ({node_id}): {count} voisins")
                        except (ValueError, AttributeError):
                            lines.append(f"• {node_id}: {count} voisins")

            return "\n".join(lines)

        except Exception as e:
            error_print(f"Erreur neighbors stats: {e}")
            error_print(traceback.format_exc())
            return f"❌ Erreur: {str(e)[:100]}"


        except Exception as e:
            error_print(f"Erreur purge weather cache: {e}")
            error_print(traceback.format_exc())
            return f"❌ Erreur: {str(e)[:100]}"
