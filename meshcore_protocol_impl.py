# This file contains the complete MeshCore protocol implementation
# to be integrated into meshcore_serial_interface.py

# The full implementation is too large for a single edit
# I'll provide it in sections that can be integrated

def send_frame(self, payload):
    """
    Envoie une trame au format MeshCore (inbound: app -> radio)
    Format: 0x3C ('<') + 2 bytes length (little-endian) + payload
    """
    if not self.serial or not self.serial.is_open:
        return False
    
    try:
        length = len(payload)
        frame = bytearray([0x3C])  # '<' marker
        frame.extend(struct.pack('<H', length))  # Length little-endian
        frame.extend(payload)
        
        self.serial.write(frame)
        debug_print(f"📤 [MESHCORE] Envoyé: {length} octets")
        return True
    except Exception as e:
        error_print(f"❌ [MESHCORE] Erreur envoi trame: {e}")
        return False

def _parse_frame(self, buffer):
    """
    Parse une trame MeshCore du buffer
    Format outbound: 0x3E ('>') + 2 bytes length + payload
    
    Returns:
        bytes: Payload de la trame ou None si incomplète
    """
    if len(buffer) < 3:
        return None
    
    # Vérifier le marker
    if buffer[0] != 0x3E:  # '>' marker
        # Chercher le prochain marker valide
        try:
            marker_pos = buffer.index(0x3E)
            del buffer[:marker_pos]
        except ValueError:
            buffer.clear()
        return None
    
    # Lire la longueur
    length = struct.unpack('<H', buffer[1:3])[0]
    frame_size = 3 + length  # marker(1) + length(2) + payload(N)
    
    if len(buffer) < frame_size:
        return None  # Trame incomplète
    
    # Extraire le payload
    payload = bytes(buffer[3:frame_size])
    del buffer[:frame_size]
    
    return payload

def _send_device_query(self):
    """Envoie une requête d'info device"""
    payload = bytearray([CMD_DEVICE_QUERY, 3])  # app_target_ver = 3
    return self.send_frame(payload)

def _send_app_start(self):
    """Envoie la commande APP_START"""
    payload = bytearray([CMD_APP_START, 3])  # app_ver = 3
    payload.extend(b'\x00' * 6)  # reserved
    payload.extend(b'MeshBot\x00')  # app_name
    return self.send_frame(payload)

def _send_sync_next_message(self):
    """Demande le prochain message de la queue"""
    payload = bytearray([CMD_SYNC_NEXT_MESSAGE])
    return self.send_frame(payload)

def _process_resp_device_info(self, payload):
    """Traite RESP_CODE_DEVICE_INFO"""
    if len(payload) < 2:
        return
    
    firmware_ver = payload[1]
    info_print(f"✅ [MESHCORE] Device info: firmware v{firmware_ver}")
    
    self.device_info = {
        'firmware_ver': firmware_ver
    }

def _process_resp_self_info(self, payload):
    """Traite RESP_CODE_SELF_INFO"""
    if len(payload) < 40:
        return
    
    node_type = payload[1]
    public_key = payload[4:36]
    
    # Extraire l'ID du node depuis la clé publique (derniers 4 bytes)
    node_id = struct.unpack('<I', public_key[-4:])[0]
    
    # Mettre à jour localNode
    self.localNode.nodeNum = node_id
    
    info_print(f"✅ [MESHCORE] Self info: node_id=0x{node_id:08x}, type={node_type}")
    
    self.self_info = {
        'type': node_type,
        'public_key': public_key,
        'node_id': node_id
    }

def _process_contact_msg_recv(self, payload):
    """Traite RESP_CODE_CONTACT_MSG_RECV (DM reçu)"""
    if len(payload) < 40:
        return
    
    # Structure: code(1) + public_key(32) + timestamp(4) + txt_len(2) + text
    public_key = payload[1:33]
    timestamp = struct.unpack('<I', payload[33:37])[0]
    txt_len = struct.unpack('<H', payload[37:39])[0]
    
    if len(payload) < 39 + txt_len:
        return
    
    text = payload[39:39+txt_len].decode('utf-8', errors='ignore')
    
    # Extraire l'ID de l'expéditeur
    sender_id = struct.unpack('<I', public_key[-4:])[0]
    
    info_print(f"📬 [MESHCORE-DM] De: 0x{sender_id:08x} | Message: {text[:50]}{'...' if len(text) > 50 else ''}")
    
    # Créer un pseudo-packet compatible
    packet = {
        'from': sender_id,
        'to': self.localNode.nodeNum,
        'decoded': {
            'portnum': 'TEXT_MESSAGE_APP',
            'payload': text.encode('utf-8')
        }
    }
    
    # Appeler le callback
    if self.message_callback:
        self.message_callback(packet, None)

def _process_push_msg_waiting(self, payload):
    """Traite PUSH_CODE_MSG_WAITING"""
    debug_print("📨 [MESHCORE] Message en attente, synchronisation...")
    # Demander le prochain message
    self._send_sync_next_message()

def _process_frame_payload(self, payload):
    """Traite le payload d'une trame reçue"""
    if len(payload) == 0:
        return
    
    code = payload[0]
    
    # Responses
    if code == RESP_CODE_DEVICE_INFO:
        self._process_resp_device_info(payload)
    elif code == RESP_CODE_SELF_INFO:
        self._process_resp_self_info(payload)
    elif code == RESP_CODE_CONTACT_MSG_RECV:
        self._process_contact_msg_recv(payload)
    elif code == RESP_CODE_NO_MORE_MESSAGES:
        debug_print("📭 [MESHCORE] Pas de nouveaux messages")
    elif code == RESP_CODE_OK:
        debug_print("✅ [MESHCORE] Commande OK")
    elif code == RESP_CODE_ERR:
        debug_print("❌ [MESHCORE] Erreur commande")
    
    # Push notifications
    elif code == PUSH_CODE_MSG_WAITING:
        self._process_push_msg_waiting(payload)
    elif code == PUSH_CODE_ADVERT:
        debug_print("📢 [MESHCORE] Nouvelle annonce reçue")
    
    else:
        debug_print(f"⚠️ [MESHCORE] Code non géré: 0x{code:02x}")
