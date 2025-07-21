from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, Optional


class Validator(ABC):
    """Base class for field validators"""
    
    @abstractmethod
    def validate(self, value: Any, context: Dict[str, Any]) -> bool:
        """Validate a field value"""
        pass
    
    @abstractmethod
    def get_error_message(self, value: Any) -> str:
        """Get error message for validation failure"""
        pass


class FunctionValidator(Validator):
    """Validator that uses a function for validation"""
    
    def __init__(self, validator_func: Callable[[Any], bool], error_message: str):
        self.validator_func = validator_func
        self.error_message = error_message
    
    def validate(self, value: Any, context: Dict[str, Any]) -> bool:
        return self.validator_func(value)
    
    def get_error_message(self, value: Any) -> str:
        return self.error_message


class EmailValidator(Validator):
    """Simple email validator"""
    
    def validate(self, value: Any, context: Dict[str, Any]) -> bool:
        if not isinstance(value, str):
            return False
        
        # Basic email validation
        parts = value.split("@")
        if len(parts) != 2:
            return False
        
        local, domain = parts
        if not local or not domain:
            return False
        
        return "." in domain
    
    def get_error_message(self, value: Any) -> str:
        return f"'{value}' is not a valid email address"


class RangeValidator(Validator):
    """Validator for numeric ranges"""
    
    def __init__(self, min_val: Optional[float] = None, max_val: Optional[float] = None):
        self.min_val = min_val
        self.max_val = max_val
    
    def validate(self, value: Any, context: Dict[str, Any]) -> bool:
        try:
            num_value = float(value)
            if self.min_val is not None and num_value < self.min_val:
                return False
            if self.max_val is not None and num_value > self.max_val:
                return False
            return True
        except (ValueError, TypeError):
            return False
    
    def get_error_message(self, value: Any) -> str:
        if self.min_val is not None and self.max_val is not None:
            return f"Value must be between {self.min_val} and {self.max_val}"
        elif self.min_val is not None:
            return f"Value must be at least {self.min_val}"
        elif self.max_val is not None:
            return f"Value must be at most {self.max_val}"
        return "Invalid numeric value"