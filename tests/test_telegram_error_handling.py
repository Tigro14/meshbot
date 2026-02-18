#!/usr/bin/env python3
"""
Test pour la gestion des erreurs Telegram (409/429)
Vérifie que les erreurs sont traitées gracieusement sans traceback complet
"""

import sys
import asyncio
import unittest
from unittest.mock import Mock, MagicMock, AsyncMock, patch
from io import StringIO


class TestTelegramErrorHandling(unittest.TestCase):
    """Tests de gestion des erreurs Telegram"""
    
    def setUp(self):
        """Configuration avant chaque test"""
        # Mock des dépendances
        sys.modules['config'] = MagicMock()
        sys.modules['config'].DEBUG_MODE = False
        sys.modules['config'].TELEGRAM_BOT_TOKEN = 'test_token'
        sys.modules['utils'] = MagicMock()
        
    def test_conflict_error_handling(self):
        """Test gestion erreur 409 Conflict"""
        from telegram_integration import TelegramIntegration
        from telegram.error import Conflict
        
        # Créer un mock pour les dépendances
        message_handler = MagicMock()
        node_manager = MagicMock()
        context_manager = MagicMock()
        
        # Créer l'intégration
        with patch('telegram_integration.BasicCommands'), \
             patch('telegram_integration.SystemCommands'), \
             patch('telegram_integration.NetworkCommands'), \
             patch('telegram_integration.StatsCommands'), \
             patch('telegram_integration.UtilityCommands'), \
             patch('telegram_integration.MeshCommands'), \
             patch('telegram_integration.AICommands'), \
             patch('telegram_integration.TraceCommands'), \
             patch('telegram_integration.AdminCommands'), \
             patch('telegram_integration.DBCommandsTelegram'), \
             patch('telegram_integration.TracerouteManager'), \
             patch('telegram_integration.AlertManager'):
            
            integration = TelegramIntegration(
                message_handler,
                node_manager,
                context_manager
            )
            
            # Créer un contexte d'erreur
            context = MagicMock()
            context.error = Conflict("terminated by other getUpdates request")
            
            # Capturer la sortie stderr
            captured_output = StringIO()
            
            # Mock de error_print pour capturer les messages
            error_messages = []
            def mock_error_print(msg):
                error_messages.append(msg)
            
            with patch('telegram_integration.error_print', side_effect=mock_error_print):
                # Exécuter le handler d'erreur
                asyncio.run(integration._error_handler(None, context))
            
            # Vérifier que le message 409 est présent
            assert any('409 CONFLICT' in msg for msg in error_messages), \
                "Message 409 CONFLICT non trouvé dans les logs"
            
            # Vérifier qu'on ne log pas le traceback complet
            assert not any('Traceback' in msg for msg in error_messages), \
                "Traceback ne devrait pas être présent pour erreur 409"
            
            print("✅ Test 409 Conflict handling: PASSED")
    
    def test_rate_limit_error_handling(self):
        """Test gestion erreur 429 Rate Limit"""
        from telegram_integration import TelegramIntegration
        from telegram.error import RetryAfter
        
        # Créer un mock pour les dépendances
        message_handler = MagicMock()
        node_manager = MagicMock()
        context_manager = MagicMock()
        
        # Créer l'intégration
        with patch('telegram_integration.BasicCommands'), \
             patch('telegram_integration.SystemCommands'), \
             patch('telegram_integration.NetworkCommands'), \
             patch('telegram_integration.StatsCommands'), \
             patch('telegram_integration.UtilityCommands'), \
             patch('telegram_integration.MeshCommands'), \
             patch('telegram_integration.AICommands'), \
             patch('telegram_integration.TraceCommands'), \
             patch('telegram_integration.AdminCommands'), \
             patch('telegram_integration.DBCommandsTelegram'), \
             patch('telegram_integration.TracerouteManager'), \
             patch('telegram_integration.AlertManager'):
            
            integration = TelegramIntegration(
                message_handler,
                node_manager,
                context_manager
            )
            
            # Créer un contexte d'erreur avec retry_after
            context = MagicMock()
            error = RetryAfter(60)
            error.retry_after = 60
            context.error = error
            
            # Mock de error_print pour capturer les messages
            error_messages = []
            def mock_error_print(msg):
                error_messages.append(msg)
            
            with patch('telegram_integration.error_print', side_effect=mock_error_print):
                # Exécuter le handler d'erreur
                asyncio.run(integration._error_handler(None, context))
            
            # Vérifier que le message 429 est présent
            assert any('429 RATE LIMIT' in msg for msg in error_messages), \
                "Message 429 RATE LIMIT non trouvé dans les logs"
            
            # Vérifier que retry_after est mentionné
            assert any('60 seconds' in msg for msg in error_messages), \
                "Retry after duration non mentionné"
            
            # Vérifier qu'on ne log pas le traceback complet
            assert not any('Traceback' in msg for msg in error_messages), \
                "Traceback ne devrait pas être présent pour erreur 429"
            
            print("✅ Test 429 Rate Limit handling: PASSED")
    
    def test_logging_configuration(self):
        """Test configuration du logging pour supprimer httpx"""
        import logging
        from main_script import setup_logging
        
        # Exécuter la configuration
        setup_logging()
        
        # Vérifier que httpx est configuré en WARNING
        httpx_logger = logging.getLogger('httpx')
        assert httpx_logger.level == logging.WARNING, \
            f"httpx logger devrait être WARNING, mais est {httpx_logger.level}"
        
        # Vérifier que telegram.ext est configuré en WARNING
        telegram_logger = logging.getLogger('telegram.ext')
        assert telegram_logger.level == logging.WARNING, \
            f"telegram.ext logger devrait être WARNING, mais est {telegram_logger.level}"
        
        print("✅ Test logging configuration: PASSED")


if __name__ == '__main__':
    # Exécuter les tests
    suite = unittest.TestLoader().loadTestsFromTestCase(TestTelegramErrorHandling)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Exit code basé sur le résultat
    sys.exit(0 if result.wasSuccessful() else 1)
