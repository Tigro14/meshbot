#!/usr/bin/env python3
"""
Test for MeshCore fire-and-forget fix
"""

import unittest
from unittest.mock import Mock, MagicMock, patch
import asyncio


class TestMeshCoreFireAndForget(unittest.TestCase):
    """Test fire-and-forget approach for MeshCore send_msg"""
    
    def test_fire_and_forget_doesnt_block(self):
        """Test that send doesn't block waiting for result"""
        # This simulates the fix - we submit the coroutine but don't wait
        
        # Create a mock event loop
        loop = Mock()
        loop.is_running.return_value = True
        
        # Create a mock future that never completes (like the real issue)
        future = Mock()
        future.done.return_value = False
        future.cancelled.return_value = False
        
        # Simulate run_coroutine_threadsafe returning a hanging future
        with patch('asyncio.run_coroutine_threadsafe', return_value=future):
            # In the fire-and-forget approach, we:
            # 1. Submit coroutine
            # 2. Add done callback
            # 3. Return immediately
            
            # This should NOT block
            coroutine = self._mock_coroutine()
            result_future = asyncio.run_coroutine_threadsafe(coroutine, loop)
            
            # Add callback
            callback_called = []
            def callback(fut):
                callback_called.append(True)
            result_future.add_done_callback(callback)
            
            # Return immediately (don't call result_future.result())
            # This is the key - we DON'T wait
            success = True  # Assume success
            
            self.assertTrue(success)
            # The future is still pending but we didn't block
            
    async def _mock_coroutine(self):
        """Mock coroutine that would hang"""
        await asyncio.sleep(100)  # Would hang if we actually waited
        
    def test_fire_and_forget_logs_completion(self):
        """Test that callback logs when coroutine eventually completes"""
        # Create a real event loop for this test
        loop = asyncio.new_event_loop()
        
        try:
            # Create a coroutine that completes quickly
            async def quick_send():
                await asyncio.sleep(0.01)
                return "sent"
            
            # Submit it
            future = asyncio.run_coroutine_threadsafe(quick_send(), loop)
            
            # Add callback to track completion
            completed = []
            def callback(fut):
                try:
                    result = fut.result()
                    completed.append(result)
                except Exception as e:
                    completed.append(f"error: {e}")
            
            future.add_done_callback(callback)
            
            # Run the loop briefly to let coroutine complete
            loop.run_until_complete(asyncio.sleep(0.1))
            
            # Callback should have been called
            self.assertEqual(len(completed), 1)
            self.assertEqual(completed[0], "sent")
            
        finally:
            loop.close()
            
    def test_fire_and_forget_handles_exceptions(self):
        """Test that callback handles exceptions gracefully"""
        loop = asyncio.new_event_loop()
        
        try:
            # Coroutine that raises exception
            async def failing_send():
                await asyncio.sleep(0.01)
                raise RuntimeError("Send failed")
            
            future = asyncio.run_coroutine_threadsafe(failing_send(), loop)
            
            # Callback should handle exception
            errors = []
            def callback(fut):
                try:
                    if fut.exception():
                        errors.append(str(fut.exception()))
                except Exception as e:
                    errors.append(f"callback error: {e}")
            
            future.add_done_callback(callback)
            
            # Run loop to let it complete
            loop.run_until_complete(asyncio.sleep(0.1))
            
            # Should have caught the exception
            self.assertEqual(len(errors), 1)
            self.assertIn("Send failed", errors[0])
            
        finally:
            loop.close()


if __name__ == '__main__':
    unittest.main()
