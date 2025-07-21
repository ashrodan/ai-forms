class AIFormError(Exception):
    """Base exception for AI Forms"""
    pass


class ValidationError(AIFormError):
    """Raised when validation fails"""
    pass


class ConfigurationError(AIFormError):
    """Raised when form configuration is invalid"""
    pass


class DependencyError(AIFormError):
    """Raised when field dependencies cannot be resolved"""
    pass