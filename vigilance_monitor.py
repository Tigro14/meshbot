"""
Surveillance de la vigilance météo Météo-France

Ce module vérifie périodiquement les alertes de vigilance météorologique
pour un département français et peut déclencher des alertes automatiques
sur le réseau Meshtastic.

Utilise le package 'vigilancemeteo' pour récupérer les données de Météo-France.
"""

import time
from typing import Optional, Dict, Any
from utils import info_print, error_print, debug_print


class VigilanceMonitor:
    """
    Moniteur de vigilance météorologique Météo-France

    Vérifie périodiquement l'état de vigilance pour un département
    et peut déclencher des alertes automatiques en cas de vigilance
    Orange ou Rouge.
    """

    def __init__(self, departement: str, check_interval: int = 900,
                 alert_throttle: int = 3600, alert_levels: list = None):
        """
        Initialiser le moniteur de vigilance

        Args:
            departement: Numéro du département (ex: '25' pour Doubs)
            check_interval: Intervalle de vérification en secondes (défaut: 15min)
            alert_throttle: Durée minimum entre 2 alertes (défaut: 1h)
            alert_levels: Niveaux de vigilance pour alerter (défaut: ['Orange', 'Rouge'])
        """
        self.departement = departement
        self.check_interval = check_interval
        self.alert_throttle = alert_throttle
        self.alert_levels = alert_levels or ['Orange', 'Rouge']

        # État interne
        self.last_check_time = 0
        self.last_alert_time = 0
        self.last_color = None
        self.last_bulletin_date = None

        info_print(f"🌦️ Vigilance monitor initialisé pour département {departement}")
        info_print(f"   Check interval: {check_interval}s, Alert throttle: {alert_throttle}s")
        info_print(f"   Alert levels: {', '.join(self.alert_levels)}")

    def check_vigilance(self) -> Optional[Dict[str, Any]]:
        """
        Vérifier l'état de vigilance actuel avec retry logic

        Returns:
            dict: Informations de vigilance ou None si erreur
                {
                    'color': str,           # 'Vert', 'Jaune', 'Orange', 'Rouge'
                    'summary': str,         # Message de synthèse
                    'bulletin_date': datetime,  # Date du bulletin
                    'url': str              # URL d'info
                }
        """
        current_time = time.time()

        # Vérifier si c'est le moment de checker
        if current_time - self.last_check_time < self.check_interval:
            return None

        # Retry logic avec exponential backoff
        max_retries = 3
        retry_delay = 2  # secondes
        
        for attempt in range(max_retries):
            try:
                import vigilancemeteo
                
                if attempt > 0:
                    info_print(f"🌦️ Vigilance tentative {attempt + 1}/{max_retries}...")

                # Créer l'objet de vigilance pour le département
                # Cette opération peut échouer avec RemoteDisconnected
                zone = vigilancemeteo.DepartmentWeatherAlert(self.departement)

                # Récupérer les informations
                color = zone.department_color
                summary = zone.summary_message('text')
                bulletin_date = zone.bulletin_date
                url = zone.additional_info_URL

                # Log de vérification
                if attempt > 0:
                    info_print(f"✅ Vigilance récupérée après {attempt + 1} tentative(s)")
                else:
                    info_print(f"✅ Vigilance check département {self.departement}: {color}")

                # Debug détaillé si changement
                if color != self.last_color:
                    debug_print(f"   Changement de niveau: {self.last_color} → {color}")
                    if color in self.alert_levels:
                        debug_print(f"   Summary: {summary}")

                # Mettre à jour l'état
                self.last_check_time = current_time
                self.last_color = color
                self.last_bulletin_date = bulletin_date

                return {
                    'color': color,
                    'summary': summary,
                    'bulletin_date': bulletin_date,
                    'url': url
                }

            except ImportError as e:
                # Module vigilancemeteo non disponible - erreur fatale
                error_print(f"❌ Module vigilancemeteo non disponible: {e}")
                self.last_check_time = current_time
                return None
                
            except Exception as e:
                # Erreurs réseau ou autres - retry possible
                error_type = type(e).__name__
                error_msg = str(e)
                
                # Log l'erreur avec plus de détails
                if attempt < max_retries - 1:
                    error_print(f"⚠️ Erreur vigilance ({error_type}): {error_msg}")
                    error_print(f"   Tentative {attempt + 1}/{max_retries} échouée, nouvelle tentative dans {retry_delay}s...")
                    time.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                else:
                    # Dernière tentative échouée
                    error_print(f"❌ Erreur vérification vigilance après {max_retries} tentatives:")
                    error_print(f"   Type: {error_type}")
                    error_print(f"   Message: {error_msg}")
                    
                    # Log traceback complet uniquement en mode debug
                    import traceback
                    debug_print("Traceback complet:")
                    debug_print(traceback.format_exc())
                    
                    self.last_check_time = current_time  # Éviter spam en cas d'erreur
                    return None

    def should_alert(self, vigilance_info: Dict[str, Any]) -> bool:
        """
        Déterminer si une alerte doit être envoyée

        Args:
            vigilance_info: Informations de vigilance depuis check_vigilance()

        Returns:
            bool: True si une alerte doit être envoyée
        """
        if not vigilance_info:
            return False

        color = vigilance_info['color']

        # Vérifier si le niveau nécessite une alerte
        if color not in self.alert_levels:
            return False

        # Vérifier le throttle (pas d'alerte si dernière < throttle)
        current_time = time.time()
        if current_time - self.last_alert_time < self.alert_throttle:
            debug_print(f"   Alerte throttlée (dernière il y a {int(current_time - self.last_alert_time)}s)")
            return False

        # Éviter duplicata : ne pas alerter si même couleur et bulletin déjà alerté
        if (color == self.last_color and
            vigilance_info['bulletin_date'] == self.last_bulletin_date):
            debug_print(f"   Alerte déjà envoyée pour ce bulletin")
            return False

        return True

    def format_alert_message(self, vigilance_info: Dict[str, Any],
                            compact: bool = True) -> str:
        """
        Formater le message d'alerte

        Args:
            vigilance_info: Informations de vigilance
            compact: True pour format court (LoRa), False pour format long (Telegram)

        Returns:
            str: Message formaté
        """
        color = vigilance_info['color']
        summary = vigilance_info['summary']

        # Émoji selon la couleur
        emoji_map = {
            'Vert': '✅',
            'Jaune': '⚠️',
            'Orange': '🟠',
            'Rouge': '🔴'
        }
        emoji = emoji_map.get(color, '🌦️')

        if compact:
            # Format court pour LoRa (< 180 chars)
            lines = [f"{emoji} VIGILANCE {color.upper()}"]
            lines.append(f"Dept {self.departement}")

            # Extraire les phénomènes depuis le summary
            # Ex: "Alerte météo Orange en cours :\n - Vent violent: Orange"
            if summary and ':' in summary:
                phenomena = summary.split('\n')[1:]  # Sauter première ligne
                for pheno in phenomena[:2]:  # Max 2 phénomènes
                    if pheno.strip().startswith('-'):
                        lines.append(pheno.strip()[2:])  # Retirer '- '

            return '\n'.join(lines)
        else:
            # Format long pour Telegram
            lines = [f"{emoji} VIGILANCE MÉTÉO {color.upper()}"]
            lines.append(f"Département {self.departement}")
            lines.append("")
            lines.append(summary)

            if vigilance_info.get('url'):
                lines.append("")
                lines.append(f"Info: {vigilance_info['url']}")

            return '\n'.join(lines)

    def record_alert_sent(self):
        """Enregistrer qu'une alerte a été envoyée"""
        self.last_alert_time = time.time()
        info_print(f"📢 Alerte vigilance envoyée pour département {self.departement}")

    def get_status(self) -> str:
        """
        Obtenir le status actuel du moniteur

        Returns:
            str: Status formaté
        """
        if self.last_color is None:
            return f"Vigilance monitor département {self.departement}: Non initialisé"

        lines = [
            f"Vigilance département {self.departement}:",
            f"  Niveau: {self.last_color}",
            f"  Dernière vérif: {int(time.time() - self.last_check_time)}s",
        ]

        if self.last_alert_time > 0:
            lines.append(f"  Dernière alerte: {int(time.time() - self.last_alert_time)}s")

        return '\n'.join(lines)
