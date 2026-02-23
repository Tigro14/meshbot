#!/usr/bin/env python3
"""
Dual Interface Manager - Support for simultaneous Meshtastic and MeshCore networks

This module allows the bot to connect to BOTH a Meshtastic network AND a MeshCore network
simultaneously, operating on separate frequencies/networks.

Architecture:
- Manages two separate interface instances
- Routes incoming messages from both networks
- Aggregates statistics from both sources
- Maintains separate message tracking per network
- Handles replies appropriately based on message source

Use Case:
When you want the bot to be present on TWO SEPARATE mesh networks:
- Network A: Meshtastic (e.g., primary community network)
- Network B: MeshCore (e.g., experimental or secondary network)
"""

import time
import threading
from utils import debug_print, info_print, error_print
import traceback


class NetworkSource:
    """Enumeration of network sources"""
    MESHTASTIC = 'meshtastic'
    MESHCORE = 'meshcore'
    UNKNOWN = 'unknown'


class DualInterfaceManager:
    """
    Manages dual network interfaces (Meshtastic + MeshCore)
    
    This manager allows the bot to:
    1. Connect to both Meshtastic and MeshCore simultaneously
    2. Receive messages from both networks
    3. Track which network each message came from
    4. Route replies back to the correct network
    5. Aggregate statistics from both networks
    """
    
    def __init__(self, message_callback=None):
        """
        Initialize dual interface manager
        
        Args:
            message_callback: Function to call when messages arrive (from either network)
                             Signature: callback(packet, interface, network_source)
        """
        self.meshtastic_interface = None
        self.meshcore_interface = None
        self.message_callback = message_callback
        
        # Thread locks for safe concurrent access
        self._meshtastic_lock = threading.Lock()
        self._meshcore_lock = threading.Lock()
        
        # Statistics
        self._meshtastic_packet_count = 0
        self._meshcore_packet_count = 0
        self._last_meshtastic_packet_time = 0
        self._last_meshcore_packet_time = 0
        
        # Strong references to pubsub listeners so they are not garbage-collected.
        # pypubsub 4.x stores bound methods via weakref: if the listener object is
        # not kept alive by a strong reference elsewhere the subscription silently
        # becomes dead after the next GC cycle.  Storing them here on 'self' keeps
        # them alive for the lifetime of this manager instance.
        self._meshtastic_pubsub_listener = None
        self._meshcore_callback_listener = None
        
        debug_print("🔄 DualInterfaceManager initialized")
    
    def set_meshtastic_interface(self, interface):
        """
        Set the Meshtastic interface
        
        Args:
            interface: Meshtastic interface instance (Serial or TCP)
        """
        with self._meshtastic_lock:
            self.meshtastic_interface = interface
            debug_print(f"✅ Meshtastic interface set: {type(interface).__name__}")
    
    def set_meshcore_interface(self, interface):
        """
        Set the MeshCore interface
        
        Args:
            interface: MeshCore interface instance
        """
        with self._meshcore_lock:
            self.meshcore_interface = interface
            debug_print(f"✅ MeshCore interface set: {type(interface).__name__}")
    
    def has_meshtastic(self):
        """Check if Meshtastic interface is available"""
        return self.meshtastic_interface is not None
    
    def has_meshcore(self):
        """Check if MeshCore interface is available"""
        return self.meshcore_interface is not None
    
    def is_dual_mode(self):
        """Check if both interfaces are active"""
        return self.has_meshtastic() and self.has_meshcore()
    
    def get_interface(self, network_source):
        """
        Get interface for specific network
        
        Args:
            network_source: NetworkSource enum value
            
        Returns:
            Interface instance or None
        """
        if network_source == NetworkSource.MESHTASTIC:
            return self.meshtastic_interface
        elif network_source == NetworkSource.MESHCORE:
            return self.meshcore_interface
        else:
            return None
    
    def get_primary_interface(self):
        """
        Get primary interface (prefers Meshtastic for full capabilities)
        
        Returns:
            Primary interface or None
        """
        if self.has_meshtastic():
            return self.meshtastic_interface
        elif self.has_meshcore():
            return self.meshcore_interface
        else:
            return None
    
    def on_meshtastic_message(self, packet, interface):
        """
        Callback for messages from Meshtastic network
        
        Args:
            packet: Meshtastic packet dict
            interface: Source interface
        """
        try:
            with self._meshtastic_lock:
                self._meshtastic_packet_count += 1
                self._last_meshtastic_packet_time = time.time()
            
            debug_print(f"📡 [MESHTASTIC] Packet #{self._meshtastic_packet_count} received")
            
            # Forward to main callback with network source tag
            if self.message_callback:
                self.message_callback(packet, interface, NetworkSource.MESHTASTIC)
        except Exception as e:
            error_print(f"Error in on_meshtastic_message: {e}")
            error_print(traceback.format_exc())
    
    def on_meshcore_message(self, packet, interface):
        """
        Callback for messages from MeshCore network
        
        Args:
            packet: MeshCore packet dict
            interface: Source interface
        """
        try:
            with self._meshcore_lock:
                self._meshcore_packet_count += 1
                self._last_meshcore_packet_time = time.time()
            
            debug_print(f"📡 [MESHCORE] Packet #{self._meshcore_packet_count} received")
            
            # MC DEBUG: Detailed packet reception logging (DEBUG level)
            from utils import debug_print_mc
            if packet:
                from_id = packet.get('from', 0)
                to_id = packet.get('to', 0)
                decoded = packet.get('decoded', {})
                portnum = decoded.get('portnum', 'UNKNOWN')
                debug_print_mc(f"📡 Packet #{self._meshcore_packet_count}: {portnum} from 0x{from_id:08x} → 0x{to_id:08x}")
            
            # Forward to main callback with network source tag
            if self.message_callback:
                self.message_callback(packet, interface, NetworkSource.MESHCORE)
            else:
                error_print("❌ MC DEBUG: No message_callback set!")
        except Exception as e:
            error_print(f"Error in on_meshcore_message: {e}")
            error_print(traceback.format_exc())
    
    def setup_message_callbacks(self):
        """
        Setup message callbacks for both interfaces.
        This must be called after both interfaces are set.

        IMPORTANT: pubsub 4.x stores listeners via weakref.  An anonymous
        lambda passed to pub.subscribe() has no other strong reference, so it
        is garbage-collected almost immediately and the subscription silently
        dies.  We therefore store each listener as an instance attribute
        (_meshtastic_pubsub_listener / _meshcore_callback_listener) so that it
        stays alive for the full lifetime of this DualInterfaceManager.
        """
        if self.has_meshtastic():
            from pubsub import pub
            # Store the listener strongly to prevent GC killing the subscription.
            self._meshtastic_pubsub_listener = self._on_meshtastic_pubsub
            pub.subscribe(self._meshtastic_pubsub_listener, "meshtastic.receive")
            info_print("✅ Meshtastic pubsub callback registered")
        
        if self.has_meshcore():
            if hasattr(self.meshcore_interface, 'set_message_callback'):
                # Store strongly so the MeshCore wrapper keeps the reference alive.
                self._meshcore_callback_listener = self._on_meshcore_callback
                self.meshcore_interface.set_message_callback(
                    self._meshcore_callback_listener
                )
                info_print("✅ MeshCore message callback registered")

    def _on_meshtastic_pubsub(self, packet, interface=None):
        """Bound method used as pubsub listener for 'meshtastic.receive'.

        Using a bound method (instead of an anonymous lambda) means pypubsub
        can keep a live weak-reference to it as long as *self* is alive.  The
        strong reference stored in self._meshtastic_pubsub_listener ensures it
        is never prematurely GC-collected.
        """
        self.on_meshtastic_message(
            packet,
            interface if interface else self.meshtastic_interface
        )

    def _on_meshcore_callback(self, packet, interface=None):
        """Bound method used as MeshCore message callback.

        Kept alive via self._meshcore_callback_listener.
        """
        self.on_meshcore_message(packet, self.meshcore_interface)
    
    def send_message(self, text, destination_id, network_source=None, channelIndex=0):
        """
        Send message to appropriate network
        
        Args:
            text: Message text
            destination_id: Target node ID (use 0xFFFFFFFF for broadcast)
            network_source: Which network to use (NetworkSource enum)
                           If None, uses primary interface (Meshtastic preferred)
            channelIndex: Channel index (0 = public/default channel)
        
        Returns:
            bool: True if sent successfully
        """
        try:
            # Determine which interface to use
            if network_source == NetworkSource.MESHTASTIC:
                interface = self.meshtastic_interface
            elif network_source == NetworkSource.MESHCORE:
                interface = self.meshcore_interface
            else:
                # Auto-select: prefer Meshtastic for full capabilities
                interface = self.get_primary_interface()
            
            if not interface:
                error_print("❌ No interface available for sending")
                return False
            
            # Send via interface with channelIndex support
            if hasattr(interface, 'sendText'):
                # Check if interface is MeshCore (requires both destinationId and channelIndex)
                is_meshcore = hasattr(interface, '__class__') and 'MeshCore' in interface.__class__.__name__
                
                if is_meshcore:
                    # MeshCore requires explicit destinationId and channelIndex
                    interface.sendText(text, destinationId=destination_id, channelIndex=channelIndex)
                else:
                    # Meshtastic: channelIndex is optional
                    interface.sendText(text, destinationId=destination_id, channelIndex=channelIndex)
                
                network_name = "Meshtastic" if interface == self.meshtastic_interface else "MeshCore"
                debug_print(f"✅ Message sent via {network_name} (channel {channelIndex}): '{text[:50]}'")
                return True
            else:
                error_print(f"❌ Interface {type(interface).__name__} doesn't support sendText")
                return False
        except Exception as e:
            error_print(f"Error sending message: {e}")
            error_print(traceback.format_exc())
            return False
    
    def get_statistics(self):
        """
        Get statistics from both networks
        
        Returns:
            dict: Statistics including packet counts and activity
        """
        stats = {
            'dual_mode': self.is_dual_mode(),
            'meshtastic': {
                'active': self.has_meshtastic(),
                'packets': self._meshtastic_packet_count,
                'last_packet': self._last_meshtastic_packet_time,
            },
            'meshcore': {
                'active': self.has_meshcore(),
                'packets': self._meshcore_packet_count,
                'last_packet': self._last_meshcore_packet_time,
            },
            'total_packets': self._meshtastic_packet_count + self._meshcore_packet_count,
        }
        return stats
    
    def get_status_report(self, compact=False):
        """
        Generate a status report for both networks
        
        Args:
            compact: If True, generate compact format for LoRa (180 chars)
        
        Returns:
            str: Formatted status report
        """
        stats = self.get_statistics()
        
        if compact:
            # Compact format for LoRa
            lines = []
            if stats['meshtastic']['active']:
                lines.append(f"🌐M:{stats['meshtastic']['packets']}p")
            if stats['meshcore']['active']:
                lines.append(f"🔗C:{stats['meshcore']['packets']}p")
            if stats['dual_mode']:
                lines.append(f"Tot:{stats['total_packets']}p")
            return " | ".join(lines) if lines else "No networks active"
        else:
            # Detailed format for Telegram
            lines = ["📊 **Dual Network Status**", ""]
            
            if stats['meshtastic']['active']:
                last_time = time.time() - stats['meshtastic']['last_packet']
                lines.append(f"🌐 **Meshtastic Network**")
                lines.append(f"  • Packets: {stats['meshtastic']['packets']}")
                lines.append(f"  • Last: {last_time:.0f}s ago")
                lines.append("")
            
            if stats['meshcore']['active']:
                last_time = time.time() - stats['meshcore']['last_packet']
                lines.append(f"🔗 **MeshCore Network**")
                lines.append(f"  • Packets: {stats['meshcore']['packets']}")
                lines.append(f"  • Last: {last_time:.0f}s ago")
                lines.append("")
            
            if stats['dual_mode']:
                lines.append(f"📈 **Total**: {stats['total_packets']} packets across both networks")
            
            return "\n".join(lines)
    
    def close(self):
        """Close both interfaces gracefully"""
        info_print("🛑 Closing dual interfaces...")
        
        if self.meshtastic_interface:
            try:
                if hasattr(self.meshtastic_interface, 'close'):
                    self.meshtastic_interface.close()
                info_print("✅ Meshtastic interface closed")
            except Exception as e:
                error_print(f"Error closing Meshtastic: {e}")
        
        if self.meshcore_interface:
            try:
                if hasattr(self.meshcore_interface, 'close'):
                    self.meshcore_interface.close()
                info_print("✅ MeshCore interface closed")
            except Exception as e:
                error_print(f"Error closing MeshCore: {e}")
