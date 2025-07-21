from enum import Enum


class ConversationMode(Enum):
    SEQUENTIAL = "sequential"
    ONE_SHOT = "one_shot"
    CLUSTERED = "clustered"


class FieldPriority(Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ValidationStrategy(Enum):
    IMMEDIATE = "immediate"
    END_OF_CLUSTER = "end_of_cluster"
    FINAL = "final"