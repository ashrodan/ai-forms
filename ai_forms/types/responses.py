from dataclasses import dataclass
from typing import Any, Dict, List, Optional, TypeVar, Generic

T = TypeVar('T')


@dataclass
class FormResponse(Generic[T]):
    question: Optional[str] = None
    is_complete: bool = False
    data: Optional[T] = None
    progress: float = 0.0
    errors: List[str] = None
    retry_prompt: Optional[str] = None
    current_field: Optional[str] = None
    collected_fields: List[str] = None
    
    def __post_init__(self):
        if self.errors is None:
            self.errors = []
        if self.collected_fields is None:
            self.collected_fields = []