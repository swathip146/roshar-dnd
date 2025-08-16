"""
Input Parser Module for Modular DM Assistant

This module provides pluggable command handling for the DM assistant,
allowing for different parsing strategies (manual command mapping vs AI-based intent detection).
"""

from .base_command_handler import BaseCommandHandler
from .manual_command_handler import ManualCommandHandler

__all__ = ['BaseCommandHandler', 'ManualCommandHandler']
