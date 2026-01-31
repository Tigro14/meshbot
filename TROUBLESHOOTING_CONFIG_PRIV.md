# Guide de dépannage: Bot utilise les valeurs par défaut au lieu de config_priv.py

## Symptôme

Le bot démarre mais utilise les valeurs par défaut au lieu de votre `config_priv.py`:
```
TELEGRAM_BOT_TOKEN = "******************"  ❌ Au lieu de votre vrai token
```

## Diagnostic rapide

### Étape 1: Exécuter le script de diagnostic

```bash
cd /home/dietpi/bot
python3 diagnose_config_priv.py
```

Ce script vérifie automatiquement:
- ✅ Le répertoire de travail
- ✅ L'emplacement de config.py
- ✅ L'existence de config_priv.py
- ✅ Les permissions du fichier
- ✅ La syntaxe Python
- ✅ L'import réel

### Étape 2: Lire les messages d'erreur du bot

Depuis la dernière mise à jour, le bot affiche des informations détaillées:

```
⚠️  ATTENTION: Impossible d'importer config_priv.py!
   Répertoire actuel: /home/dietpi/bot
   Fichier recherché: /home/dietpi/bot/config_priv.py
   Fichier existe: True/False
   Permissions: 644
   Taille: 1234 octets
   ⚠️  ERREUR: [Type d'erreur et détails]
```

## Causes communes et solutions

### Cause 1: Le fichier n'existe pas

**Symptôme dans les logs:**
```
Fichier existe: False
→ Le fichier n'existe pas à cet emplacement
```

**Solution:**
```bash
cd /home/dietpi/bot
cp config.priv.py.sample config_priv.py
nano config_priv.py
# Remplir vos vraies valeurs
sudo systemctl restart meshbot
```

### Cause 2: Erreur de syntaxe Python

**Symptôme dans les logs:**
```
⚠️  ERREUR: SyntaxError: invalid syntax (config_priv.py, line 15)
→ Le fichier contient une ERREUR DE SYNTAXE Python
→ Ligne 15: TELEGRAM_AUTHORIZED_USERS = [123 456]  ← Virgule manquante
```

**Solution:**
```bash
# Vérifier la syntaxe
cd /home/dietpi/bot
python3 -m py_compile config_priv.py

# Corriger l'erreur
nano config_priv.py

# Exemples d'erreurs courantes:
# ❌ TELEGRAM_AUTHORIZED_USERS = [123 456]      # Manque virgule
# ✅ TELEGRAM_AUTHORIZED_USERS = [123, 456]

# ❌ TELEGRAM_BOT_TOKEN = 123456:ABC...         # Manque guillemets
# ✅ TELEGRAM_BOT_TOKEN = "123456:ABC..."

# ❌ REBOOT_AUTHORIZED_USERS = [0x16fad3dc,]    # Virgule finale incorrecte
# ✅ REBOOT_AUTHORIZED_USERS = [0x16fad3dc]

# Redémarrer le bot
sudo systemctl restart meshbot
```

### Cause 3: Mauvaises permissions

**Symptôme dans les logs:**
```
Permissions: 000
→ Fichier non lisible
```

**Solution:**
```bash
cd /home/dietpi/bot
chmod 644 config_priv.py
ls -la config_priv.py  # Vérifier: -rw-r--r--
sudo systemctl restart meshbot
```

### Cause 4: Fichier dans le mauvais répertoire

**Symptôme dans les logs:**
```
Répertoire actuel: /home/dietpi/bot
Fichier recherché: /home/dietpi/bot/config_priv.py
Fichier existe: False
```

**Solution:**
```bash
# Vérifier où le bot cherche le fichier
sudo journalctl -u meshbot | grep "Répertoire actuel"

# Vérifier où est votre fichier
find /home/dietpi -name "config_priv.py" -type f

# Déplacer le fichier au bon endroit si nécessaire
mv /path/to/wrong/location/config_priv.py /home/dietpi/bot/

# Redémarrer
sudo systemctl restart meshbot
```

### Cause 5: Service démarre depuis le mauvais répertoire

**Solution:**
```bash
# Vérifier le service
cat /etc/systemd/system/meshbot.service

# Doit contenir:
# [Service]
# WorkingDirectory=/home/dietpi/bot
# ExecStart=/usr/bin/python3 /home/dietpi/bot/main_script.py

# Si incorrect, éditer:
sudo nano /etc/systemd/system/meshbot.service

# Recharger et redémarrer:
sudo systemctl daemon-reload
sudo systemctl restart meshbot
```

### Cause 6: Variables manquantes dans config_priv.py

**Symptôme:**
Le bot démarre mais certaines fonctionnalités ne marchent pas

**Solution:**
Comparer votre fichier avec le template:
```bash
cd /home/dietpi/bot
diff -u config.priv.py.sample config_priv.py

# Ajouter les variables manquantes
nano config_priv.py
```

Variables requises minimales:
```python
TELEGRAM_BOT_TOKEN = "votre_token_ici"
TELEGRAM_AUTHORIZED_USERS = []
TELEGRAM_ALERT_USERS = []
TELEGRAM_TO_MESH_MAPPING = {}
MQTT_NEIGHBOR_PASSWORD = "votre_password_mqtt"
REBOOT_AUTHORIZED_USERS = []
REBOOT_PASSWORD = "votre_password_reboot"
MESH_ALERT_SUBSCRIBED_NODES = []
CLI_TO_MESH_MAPPING = {}
```

## Vérification finale

Après avoir corrigé le problème:

```bash
# 1. Vérifier la syntaxe
python3 -m py_compile /home/dietpi/bot/config_priv.py

# 2. Tester l'import
cd /home/dietpi/bot
python3 -c "from config_priv import TELEGRAM_BOT_TOKEN; print('Token:', TELEGRAM_BOT_TOKEN[:10] + '...')"

# 3. Redémarrer le bot
sudo systemctl restart meshbot

# 4. Vérifier les logs
sudo journalctl -u meshbot -n 50

# 5. Vérifier que le bot utilise vos valeurs
sudo journalctl -u meshbot | grep "TELEGRAM_BOT_TOKEN"
# Ne devrait PAS afficher "******************"
```

## Logs à surveiller

### ✅ BON - Import réussi
```
# Aucun message d'avertissement sur config_priv.py
# Le bot démarre normalement
```

### ❌ MAUVAIS - Import échoué
```
⚠️  ATTENTION: Impossible d'importer config_priv.py!
   Répertoire actuel: /home/dietpi/bot
   Fichier recherché: /home/dietpi/bot/config_priv.py
   Fichier existe: False
```

## Aide supplémentaire

Si le problème persiste après avoir essayé toutes les solutions:

1. **Créer un fichier de test minimal:**
```bash
cd /home/dietpi/bot
cat > config_priv_test.py << 'EOF'
TELEGRAM_BOT_TOKEN = "test123"
REBOOT_PASSWORD = "test456"
TELEGRAM_AUTHORIZED_USERS = []
TELEGRAM_ALERT_USERS = []
TELEGRAM_TO_MESH_MAPPING = {}
MQTT_NEIGHBOR_PASSWORD = "test"
REBOOT_AUTHORIZED_USERS = []
MESH_ALERT_SUBSCRIBED_NODES = []
CLI_TO_MESH_MAPPING = {}
EOF

# Tester l'import
python3 -c "from config_priv_test import TELEGRAM_BOT_TOKEN; print(TELEGRAM_BOT_TOKEN)"
# Devrait afficher: test123

# Si ça marche, copier vers config_priv.py
cp config_priv_test.py config_priv.py
nano config_priv.py  # Remplir vos vraies valeurs
```

2. **Vérifier les logs en temps réel:**
```bash
sudo journalctl -u meshbot -f
```

3. **Tester manuellement:**
```bash
cd /home/dietpi/bot
python3 main_script.py --debug
# Observer les messages d'erreur en direct
```

## Changements récents (2026-01-31)

✅ **Nouvelles fonctionnalités:**
- Diagnostics détaillés dans config.py
- Script diagnose_config_priv.py
- Meilleurs messages d'erreur
- Support des SyntaxError

✅ **Avant vs Après:**

**AVANT:**
```
⚠️  ATTENTION: config.priv.py introuvable!
ImportError: cannot import name 'REBOOT_PASSWORD'
💥 Bot crash
```

**APRÈS:**
```
⚠️  ATTENTION: Impossible d'importer config_priv.py!
   Fichier existe: True
   Permissions: 644
   ⚠️  ERREUR: SyntaxError: invalid syntax (line 15)
   → Utilisation des valeurs par défaut
✅ Bot démarre (mais avec defaults)
```

## Contact

Si vous avez toujours des problèmes, fournir ces informations:

```bash
# Exécuter et copier la sortie:
cd /home/dietpi/bot
echo "=== Diagnostic complet ===" > diagnostic.txt
python3 diagnose_config_priv.py >> diagnostic.txt 2>&1
ls -la config* >> diagnostic.txt
cat config_priv.py | head -20 >> diagnostic.txt  # (masquer tokens!)
sudo journalctl -u meshbot -n 100 >> diagnostic.txt

# Partager diagnostic.txt (en masquant les tokens sensibles!)
```
