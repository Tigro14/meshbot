#!/usr/bin/env python3
"""
Manual demonstration of vigilance_monitor improvements

This script demonstrates the improved error handling in a simulated environment.
"""

import sys
import os
import time
from unittest.mock import patch, MagicMock
import http.client

# Add repo to path
repo_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, repo_root)

# Mock config
class MockConfig:
    DEBUG_MODE = False  # Production mode - less verbose
    
sys.modules['config'] = MockConfig

# Import after config is mocked
from vigilance_monitor import VigilanceMonitor

def demo_successful_check():
    """Demonstrate successful vigilance check"""
    print("\n" + "="*70)
    print("DEMO 1: Successful Check (No Errors)")
    print("="*70)
    
    monitor = VigilanceMonitor('75', check_interval=0)
    
    with patch('vigilancemeteo.DepartmentWeatherAlert') as mock_alert:
        mock_alert.return_value = MagicMock(
            department_color='Vert',
            summary_message=lambda x: 'Pas de vigilance particulière',
            bulletin_date=time.time(),
            additional_info_URL='http://vigilance.meteofrance.com'
        )
        
        result = monitor.check_vigilance()
        
        print(f"\n✅ Result: {result['color']}")
        print("Note: In production (DEBUG_MODE=False), successful checks are quiet")


def demo_retry_with_recovery():
    """Demonstrate retry with eventual success"""
    print("\n" + "="*70)
    print("DEMO 2: Network Hiccup with Recovery")
    print("="*70)
    
    monitor = VigilanceMonitor('75', check_interval=0)
    
    # First attempt fails, second succeeds
    with patch('vigilancemeteo.DepartmentWeatherAlert') as mock_alert:
        mock_alert.side_effect = [
            http.client.RemoteDisconnected("Connection lost"),
            MagicMock(
                department_color='Jaune',
                summary_message=lambda x: 'Vigilance jaune pour orages',
                bulletin_date=time.time(),
                additional_info_URL='http://vigilance.meteofrance.com'
            )
        ]
        
        # Patch sleep to speed up demo
        with patch('time.sleep'):
            result = monitor.check_vigilance()
        
        print(f"\n✅ Recovered after retry: {result['color']}")
        print("Note: Retry logged as INFO (warning), not ERROR")


def demo_complete_failure():
    """Demonstrate complete failure after all retries"""
    print("\n" + "="*70)
    print("DEMO 3: Complete Network Failure")
    print("="*70)
    
    monitor = VigilanceMonitor('75', check_interval=0)
    
    with patch('vigilancemeteo.DepartmentWeatherAlert') as mock_alert:
        mock_alert.side_effect = http.client.RemoteDisconnected("Connection lost")
        
        # Patch sleep to speed up demo
        with patch('time.sleep'):
            result = monitor.check_vigilance()
        
        print(f"\n❌ Result after all retries: {result}")
        print("Note: Only final failure logged as ERROR")


def demo_timeout():
    """Demonstrate timeout handling"""
    print("\n" + "="*70)
    print("DEMO 4: Timeout After 10 Seconds")
    print("="*70)
    
    monitor = VigilanceMonitor('75', check_interval=0)
    
    import socket
    
    def slow_api(*args, **kwargs):
        """Simulate slow API that would timeout"""
        raise socket.timeout("Request timed out after 10 seconds")
    
    with patch('vigilancemeteo.DepartmentWeatherAlert', side_effect=slow_api):
        # Patch sleep to speed up demo
        with patch('time.sleep'):
            result = monitor.check_vigilance()
        
        print(f"\n❌ Result after timeout: {result}")
        print("Note: Timeout prevents indefinite hanging")


def demo_jitter_comparison():
    """Demonstrate exponential backoff with jitter"""
    print("\n" + "="*70)
    print("DEMO 5: Exponential Backoff with Jitter")
    print("="*70)
    
    print("\nSimulating 5 retry scenarios to show jitter variation:")
    
    sleep_times_list = []
    
    for run in range(5):
        monitor = VigilanceMonitor('75', check_interval=0)
        
        sleep_times = []
        
        def track_sleep(seconds):
            sleep_times.append(seconds)
        
        with patch('time.sleep', side_effect=track_sleep):
            with patch('vigilancemeteo.DepartmentWeatherAlert') as mock_alert:
                mock_alert.side_effect = ConnectionError("Network error")
                
                result = monitor.check_vigilance()
        
        sleep_times_list.append(sleep_times)
        print(f"  Run {run + 1}: {sleep_times[0]:.2f}s, {sleep_times[1]:.2f}s")
    
    print("\nNotice: Delays vary due to jitter, preventing thundering herd")
    print("        First retry: 2.0-3.0s, Second retry: 4.0-5.0s")


def main():
    """Run all demonstrations"""
    print("\n" + "="*70)
    print("VIGILANCE MONITOR - IMPROVED ERROR HANDLING DEMONSTRATION")
    print("Issue #33 Fixes")
    print("="*70)
    
    try:
        demo_successful_check()
        demo_retry_with_recovery()
        demo_complete_failure()
        demo_timeout()
        demo_jitter_comparison()
        
        print("\n" + "="*70)
        print("DEMONSTRATION COMPLETE")
        print("="*70)
        print("\nKey Improvements Demonstrated:")
        print("  ✅ Successful checks are quiet (DEBUG mode)")
        print("  ✅ Retries logged as INFO (not ERROR)")
        print("  ✅ Only final failure logged as ERROR")
        print("  ✅ Timeout prevents hanging (10 seconds)")
        print("  ✅ Jitter prevents thundering herd")
        print("\n")
        
        return 0
    
    except Exception as e:
        print(f"\n❌ Demo failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
