from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional
from .enums import FieldPriority


@dataclass
class FieldConfig:
    name: str
    field_type: type
    description: str
    priority: FieldPriority = FieldPriority.MEDIUM
    cluster: Optional[str] = None
    custom_question: Optional[str] = None
    examples: List[str] = field(default_factory=list)
    validation_hint: Optional[str] = None
    dependencies: List[str] = field(default_factory=list)
    skip_if: Optional[Callable[[Dict[str, Any]], bool]] = None
    required: bool = True
    default: Any = None