"""Test helper utilities"""
import os
from typing import Any, Dict


def ensure_test_mode_environment():
    """Ensure test environment doesn't require API keys"""
    # Remove API keys from environment during tests to ensure test mode works
    test_env_vars = {
        'OPENAI_API_KEY': None,
        'ANTHROPIC_API_KEY': None,
    }
    
    original_values = {}
    for var, value in test_env_vars.items():
        original_values[var] = os.environ.get(var)
        if value is None and var in os.environ:
            del os.environ[var]
        elif value is not None:
            os.environ[var] = value
    
    return original_values


def restore_environment(original_values: Dict[str, Any]):
    """Restore original environment variables"""
    for var, value in original_values.items():
        if value is None and var in os.environ:
            del os.environ[var]
        elif value is not None:
            os.environ[var] = value


def is_ai_test_enabled() -> bool:
    """Check if AI integration tests should be run (when API key is available)"""
    return bool(os.environ.get('OPENAI_API_KEY') or os.environ.get('ANTHROPIC_API_KEY'))