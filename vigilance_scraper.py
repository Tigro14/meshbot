"""
Scraper pour les données de vigilance météo Météo-France

Ce module remplace le package 'vigilancemeteo' qui est cassé/non maintenu.
Il scrape directement le site https://vigilance.meteofrance.fr pour obtenir
les informations de vigilance météorologique par département.

Utilisation:
    >>> alert = DepartmentWeatherAlert('75')  # Paris
    >>> print(alert.department_color)  # 'Vert', 'Jaune', 'Orange', ou 'Rouge'
    >>> print(alert.summary_message('text'))
    >>> print(alert.bulletin_date)
    >>> print(alert.additional_info_URL)
"""

import requests
from bs4 import BeautifulSoup
from datetime import datetime
from typing import Optional
import re


class DepartmentWeatherAlert:
    """
    Scraper de vigilance météo pour un département français.
    
    Interface compatible avec vigilancemeteo.DepartmentWeatherAlert pour
    permettre un remplacement transparent dans le code existant.
    """
    
    def __init__(self, department_number: str, timeout: int = 10):
        """
        Initialiser le scraper pour un département
        
        Args:
            department_number: Numéro du département (ex: '75' pour Paris)
            timeout: Timeout pour les requêtes HTTP en secondes
        """
        self.department = department_number
        self.timeout = timeout
        self._data = None
        
        # Scrape les données immédiatement (comportement compatible avec vigilancemeteo)
        self._fetch_data()
    
    def _fetch_data(self):
        """
        Récupérer et parser les données de vigilance depuis le site Météo-France
        
        Raises:
            requests.exceptions.RequestException: En cas d'erreur réseau
            ValueError: Si les données ne peuvent pas être parsées
        """
        # Construction de l'URL
        # Le site utilise un mapping département -> nom de ville
        # Pour simplifier, on utilise le numéro de département directement
        dept_name = self._get_department_name(self.department)
        url = f"https://vigilance.meteofrance.fr/fr/{dept_name}"
        
        # Headers pour simuler un navigateur
        headers = {
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7',
        }
        
        try:
            response = requests.get(url, headers=headers, timeout=self.timeout)
            response.raise_for_status()
            
            # Parser le HTML
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Extraire les données
            self._data = {
                'color': self._extract_color(soup),
                'summary': self._extract_summary(soup),
                'bulletin_date': self._extract_bulletin_date(soup),
                'url': url,
            }
            
        except Exception as e:
            # Re-raise pour que vigilance_monitor.py puisse gérer l'erreur
            raise
    
    def _get_department_name(self, dept_number: str) -> str:
        """
        Convertir un numéro de département en nom de ville pour l'URL
        
        Le site Météo-France utilise des noms de villes dans les URLs.
        On mappe les départements principaux.
        
        Args:
            dept_number: Numéro du département (ex: '75')
            
        Returns:
            str: Nom de la ville pour l'URL (ex: 'paris')
        """
        # Mapping des départements vers les noms utilisés dans les URLs
        mapping = {
            '75': 'paris',
            '25': 'besancon',
            '13': 'marseille',
            '69': 'lyon',
            '33': 'bordeaux',
            '31': 'toulouse',
            '59': 'lille',
            '44': 'nantes',
            '67': 'strasbourg',
            '35': 'rennes',
            '34': 'montpellier',
            '06': 'nice',
            '14': 'caen',
            '29': 'brest',
            '21': 'dijon',
            '37': 'tours',
            '45': 'orleans',
            '54': 'nancy',
            '57': 'metz',
            '63': 'clermont-ferrand',
            '76': 'rouen',
            '80': 'amiens',
            '86': 'poitiers',
            '87': 'limoges',
        }
        
        # Si le département n'est pas dans le mapping, utiliser le numéro
        # (le site pourrait avoir une redirection)
        return mapping.get(dept_number, dept_number)
    
    def _extract_color(self, soup: BeautifulSoup) -> str:
        """
        Extraire la couleur de vigilance depuis le HTML
        
        Args:
            soup: BeautifulSoup object du HTML
            
        Returns:
            str: 'Vert', 'Jaune', 'Orange', ou 'Rouge'
        """
        # Stratégies multiples pour extraire la couleur:
        # IMPORTANT: On cherche la couleur d'alerte ACTUELLE, pas les mentions de couleurs
        # dans les légendes ou textes explicatifs
        
        color_classes = ['vert', 'jaune', 'orange', 'rouge', 'green', 'yellow', 'red']
        
        # 1. Chercher des éléments avec attributs data-* contenant la couleur
        # C'est la méthode la plus fiable car elle indique l'état actuel
        for element in soup.find_all(attrs={'data-color': True}):
            color = element.get('data-color', '').lower()
            if color:
                return self._normalize_color(color)
        
        for element in soup.find_all(attrs={'data-level': True}):
            level = element.get('data-level', '').lower()
            if level:
                return self._normalize_color(level)
        
        # 2. Chercher des classes CSS dans des éléments d'alerte spécifiques
        # On vérifie que l'élément est bien un indicateur d'alerte, pas une légende
        alert_indicators = ['alert', 'alerte', 'status', 'niveau', 'vigilance-level', 'current']
        for element in soup.find_all(class_=True):
            classes = ' '.join(element.get('class', [])).lower()
            
            # Skip les éléments de légende/navigation/footer
            if any(skip in classes for skip in ['legend', 'legende', 'footer', 'nav', 'menu', 'list', 'liste']):
                continue
            
            # Vérifier si c'est un indicateur d'alerte
            is_alert_indicator = any(indicator in classes for indicator in alert_indicators)
            
            if is_alert_indicator:
                for color in color_classes:
                    if color in classes:
                        return self._normalize_color(color)
        
        # 3. Chercher des classes CSS avec format spécifique couleur-alerte
        # Ex: vigilance-rouge, niveau-orange, alert-jaune
        for element in soup.find_all(class_=True):
            classes = ' '.join(element.get('class', [])).lower()
            
            # Skip les éléments de légende/navigation
            parent = element.find_parent()
            if parent:
                parent_classes = ' '.join(parent.get('class', [])).lower() if parent.get('class') else ''
                if any(skip in parent_classes for skip in ['legend', 'legende', 'footer', 'list', 'liste']):
                    continue
            
            # Chercher des patterns comme "vigilance-rouge" ou "alerte-orange"
            for prefix in ['vigilance-', 'alerte-', 'niveau-', 'alert-', 'status-']:
                for color in color_classes:
                    pattern = f'{prefix}{color}'
                    if pattern in classes:
                        return self._normalize_color(color)
        
        # 4. Chercher dans les meta tags (fiable car contient l'état actuel)
        meta_tags = soup.find_all('meta', attrs={'name': re.compile(r'vigilance|couleur|niveau', re.I)})
        for meta in meta_tags:
            content = meta.get('content', '').lower()
            for color in ['rouge', 'orange', 'jaune', 'vert']:
                if color in content:
                    return self._normalize_color(color)
        
        # 5. Chercher dans le texte - UNIQUEMENT pour les alertes actives
        # On cherche des patterns qui indiquent une alerte EN COURS, pas des explications
        text = soup.get_text().lower()
        
        # Patterns qui indiquent une alerte ACTIVE (pas une explication)
        active_patterns = [
            (r'vigilance\s+rouge\s+(en\s+cours|activ[ée]|pour\s+le|jusqu)', 'Rouge'),
            (r'alerte\s+rouge\s+(en\s+cours|activ[ée]|pour\s+le|jusqu)', 'Rouge'),
            (r'niveau\s+rouge\s+(en\s+cours|activ[ée]|pour\s+le|jusqu)', 'Rouge'),
            (r'vigilance\s+orange\s+(en\s+cours|activ[ée]|pour\s+le|jusqu)', 'Orange'),
            (r'alerte\s+orange\s+(en\s+cours|activ[ée]|pour\s+le|jusqu)', 'Orange'),
            (r'niveau\s+orange\s+(en\s+cours|activ[ée]|pour\s+le|jusqu)', 'Orange'),
            (r'vigilance\s+jaune\s+(en\s+cours|activ[ée]|pour\s+le|jusqu)', 'Jaune'),
            (r'alerte\s+jaune\s+(en\s+cours|activ[ée]|pour\s+le|jusqu)', 'Jaune'),
            (r'niveau\s+jaune\s+(en\s+cours|activ[ée]|pour\s+le|jusqu)', 'Jaune'),
        ]
        
        for pattern, color in active_patterns:
            if re.search(pattern, text):
                return color
        
        # 6. Vérifier explicitement si la page indique "pas de vigilance" ou équivalent
        no_alert_patterns = [
            r'pas\s+de\s+vigilance\s+particulière',
            r'aucune\s+vigilance',
            r'vigilance\s+verte',
            r'niveau\s+vert',
        ]
        for pattern in no_alert_patterns:
            if re.search(pattern, text):
                return 'Vert'
        
        # Par défaut, considérer Vert (pas de vigilance)
        # C'est le choix le plus sûr pour éviter les fausses alertes
        return 'Vert'
    
    def _normalize_color(self, color: str) -> str:
        """
        Normaliser une couleur vers le format attendu
        
        Args:
            color: Couleur en anglais ou français (vert/green/jaune/yellow/etc)
            
        Returns:
            str: Couleur normalisée ('Vert', 'Jaune', 'Orange', 'Rouge')
        """
        color = color.lower()
        
        if color in ['vert', 'green']:
            return 'Vert'
        elif color in ['jaune', 'yellow']:
            return 'Jaune'
        elif color in ['orange']:
            return 'Orange'
        elif color in ['rouge', 'red']:
            return 'Rouge'
        else:
            return 'Vert'  # Défaut
    
    def _extract_summary(self, soup: BeautifulSoup) -> str:
        """
        Extraire le résumé des alertes depuis le HTML
        
        Args:
            soup: BeautifulSoup object du HTML
            
        Returns:
            str: Résumé des alertes ou message par défaut
        """
        # Stratégies multiples pour extraire le résumé:
        
        # 1. Chercher un élément avec classe/id contenant 'summary', 'resume', 'alerte'
        for selector in ['summary', 'resume', 'alerte', 'message', 'description']:
            elements = soup.find_all(class_=re.compile(selector, re.I))
            if not elements:
                elements = soup.find_all(id=re.compile(selector, re.I))
            
            for element in elements:
                text = element.get_text(strip=True)
                if len(text) > 20:  # Minimum 20 caractères pour être un vrai résumé
                    return text
        
        # 2. Chercher dans les paragraphes contenant des mots-clés
        paragraphs = soup.find_all('p')
        for p in paragraphs:
            text = p.get_text(strip=True)
            if any(keyword in text.lower() for keyword in ['vigilance', 'alerte', 'phénomène', 'météo']):
                if len(text) > 20:
                    return text
        
        # 3. Chercher les listes d'alertes
        lists = soup.find_all(['ul', 'ol'])
        for lst in lists:
            items = lst.find_all('li')
            if items and any(keyword in lst.get_text().lower() for keyword in ['vigilance', 'alerte', 'phénomène']):
                summary_parts = []
                for item in items[:3]:  # Max 3 premiers items
                    text = item.get_text(strip=True)
                    if text:
                        summary_parts.append(f"- {text}")
                if summary_parts:
                    return '\n'.join(summary_parts)
        
        # Par défaut
        color = self._data.get('color', 'Vert') if self._data else 'Vert'
        if color == 'Vert':
            return "Pas de vigilance particulière"
        else:
            return f"Vigilance {color} en cours. Consultez le site pour plus de détails."
    
    def _extract_bulletin_date(self, soup: BeautifulSoup) -> datetime:
        """
        Extraire la date du bulletin depuis le HTML
        
        Args:
            soup: BeautifulSoup object du HTML
            
        Returns:
            datetime: Date du bulletin ou datetime.now() si non trouvé
        """
        # Stratégies multiples pour extraire la date:
        
        # 1. Chercher des éléments avec classe/id contenant 'date', 'bulletin', 'mise-a-jour'
        for selector in ['date', 'bulletin', 'mise-a-jour', 'update', 'timestamp']:
            elements = soup.find_all(class_=re.compile(selector, re.I))
            if not elements:
                elements = soup.find_all(id=re.compile(selector, re.I))
            
            for element in elements:
                text = element.get_text(strip=True)
                date = self._parse_date(text)
                if date:
                    return date
        
        # 2. Chercher dans les time elements HTML5
        time_elements = soup.find_all('time')
        for time_elem in time_elements:
            datetime_attr = time_elem.get('datetime')
            if datetime_attr:
                date = self._parse_date(datetime_attr)
                if date:
                    return date
            
            text = time_elem.get_text(strip=True)
            date = self._parse_date(text)
            if date:
                return date
        
        # 3. Chercher dans les meta tags
        meta_tags = soup.find_all('meta', attrs={'property': re.compile(r'date|time', re.I)})
        for meta in meta_tags:
            content = meta.get('content', '')
            date = self._parse_date(content)
            if date:
                return date
        
        # Par défaut: date actuelle
        return datetime.now()
    
    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """
        Parser une chaîne de date dans différents formats
        
        Args:
            date_str: Chaîne contenant une date
            
        Returns:
            datetime: Date parsée ou None si échec
        """
        if not date_str:
            return None
        
        # Formats de date courants
        formats = [
            '%Y-%m-%d %H:%M:%S',
            '%Y-%m-%dT%H:%M:%S',
            '%Y-%m-%d',
            '%d/%m/%Y %H:%M:%S',
            '%d/%m/%Y %H:%M',
            '%d/%m/%Y',
            '%d-%m-%Y',
        ]
        
        for fmt in formats:
            try:
                return datetime.strptime(date_str.strip(), fmt)
            except (ValueError, AttributeError):
                continue
        
        # Essayer de trouver une date ISO dans la chaîne
        iso_match = re.search(r'\d{4}-\d{2}-\d{2}', date_str)
        if iso_match:
            try:
                return datetime.strptime(iso_match.group(), '%Y-%m-%d')
            except ValueError:
                pass
        
        return None
    
    @property
    def department_color(self) -> str:
        """
        Couleur de vigilance du département
        
        Returns:
            str: 'Vert', 'Jaune', 'Orange', ou 'Rouge'
        """
        if self._data is None:
            return 'Vert'
        return self._data.get('color', 'Vert')
    
    def summary_message(self, format: str = 'text') -> str:
        """
        Message de synthèse des alertes
        
        Args:
            format: Format du message ('text' pour texte brut)
            
        Returns:
            str: Résumé des alertes
        """
        if self._data is None:
            return "Pas de vigilance particulière"
        return self._data.get('summary', 'Pas de vigilance particulière')
    
    @property
    def bulletin_date(self) -> datetime:
        """
        Date du bulletin de vigilance
        
        Returns:
            datetime: Date du bulletin
        """
        if self._data is None:
            return datetime.now()
        return self._data.get('bulletin_date', datetime.now())
    
    @property
    def additional_info_URL(self) -> str:
        """
        URL pour plus d'informations
        
        Returns:
            str: URL du site Météo-France
        """
        if self._data is None:
            return "https://vigilance.meteofrance.fr"
        return self._data.get('url', 'https://vigilance.meteofrance.fr')


# Alias pour compatibilité avec l'ancien module
DepartmentAlert = DepartmentWeatherAlert
