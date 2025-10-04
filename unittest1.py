# test_wrapper.py
from message_handler import MessageHandler
from unittest.mock import MagicMock

# Créer des mocks
llama_mock = MagicMock()
llama_mock.query_llama_telegram = MagicMock(return_value="Test réponse")

mh = MessageHandler(
    llama_mock,
    MagicMock(),
    MagicMock(),
    MagicMock(),
    MagicMock(),
    MagicMock(),
    MagicMock()
)

# Tester
assert hasattr(mh, 'llama_client'), "❌ llama_client manquant"
assert mh.llama_client == llama_mock, "❌ llama_client incorrect"
assert hasattr(mh.llama_client, 'query_llama_telegram'), "❌ Méthode manquante"

print("✅ Tous les tests passent")
