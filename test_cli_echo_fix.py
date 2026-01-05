#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test pour vérifier que CLIMessageSender a bien la méthode _get_interface()

This test verifies the fix for:
AttributeError: 'CLIMessageSender' object has no attribute '_get_interface'

The fix adds the _get_interface() method to CLIMessageSender to allow
the /echo command to access the shared Meshtastic interface.
"""

import unittest
import ast


class TestCLIEchoFix(unittest.TestCase):
    """Test CLIMessageSender _get_interface() fix"""
    
    def test_cli_message_sender_has_get_interface_method(self):
        """Verify CLIMessageSender has _get_interface() method"""
        with open('platforms/cli_server_platform.py', 'r') as f:
            tree = ast.parse(f.read())
        
        # Find CLIMessageSender class
        cli_sender_class = None
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == 'CLIMessageSender':
                cli_sender_class = node
                break
        
        self.assertIsNotNone(cli_sender_class, "CLIMessageSender class should exist")
        
        # Check _get_interface method exists
        has_get_interface = False
        for item in cli_sender_class.body:
            if isinstance(item, ast.FunctionDef) and item.name == '_get_interface':
                has_get_interface = True
                break
        
        self.assertTrue(has_get_interface, 
                       "CLIMessageSender must have _get_interface() method")
    
    def test_cli_message_sender_init_has_interface_provider(self):
        """Verify CLIMessageSender.__init__() has interface_provider parameter"""
        with open('platforms/cli_server_platform.py', 'r') as f:
            tree = ast.parse(f.read())
        
        # Find CLIMessageSender class
        cli_sender_class = None
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == 'CLIMessageSender':
                cli_sender_class = node
                break
        
        self.assertIsNotNone(cli_sender_class, "CLIMessageSender class should exist")
        
        # Find __init__ method
        init_method = None
        for item in cli_sender_class.body:
            if isinstance(item, ast.FunctionDef) and item.name == '__init__':
                init_method = item
                break
        
        self.assertIsNotNone(init_method, "__init__ method should exist")
        
        # Check parameters
        args = [arg.arg for arg in init_method.args.args]
        self.assertIn('interface_provider', args,
                     "__init__ should have interface_provider parameter")
    
    def test_cli_message_sender_instantiation_includes_interface_provider(self):
        """Verify CLIMessageSender is instantiated with interface_provider"""
        with open('platforms/cli_server_platform.py', 'r') as f:
            content = f.read()
        
        # Check for updated instantiation pattern
        self.assertIn('CLIMessageSender(self, user_id, interface_provider=router.interface)', 
                     content,
                     "CLIMessageSender instantiation should include interface_provider=router.interface")
    
    def test_get_interface_method_implementation(self):
        """Verify _get_interface() method implementation details"""
        with open('platforms/cli_server_platform.py', 'r') as f:
            content = f.read()
        
        # Check for key implementation details
        self.assertIn('def _get_interface(self):', content,
                     "_get_interface method should be defined")
        
        # Check it handles None interface_provider
        self.assertIn('if self.interface_provider is None:', content,
                     "_get_interface should check for None interface_provider")
        
        # Check it handles get_interface() method
        self.assertIn("hasattr(self.interface_provider, 'get_interface')", content,
                     "_get_interface should check for get_interface() method")
    
    def test_utility_commands_uses_get_interface(self):
        """Verify utility_commands.py handle_echo() uses _get_interface()"""
        with open('handlers/command_handlers/utility_commands.py', 'r') as f:
            content = f.read()
        
        # Check that handle_echo uses _get_interface
        self.assertIn('current_sender._get_interface()', content,
                     "handle_echo should call current_sender._get_interface()")


if __name__ == '__main__':
    # Run tests with verbose output
    unittest.main(verbosity=2)
