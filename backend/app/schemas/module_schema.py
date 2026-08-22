from pydantic import BaseModel, Field
from typing import Dict, List, Any, Optional

class Assertion(BaseModel):
    metric: str  # e.g., "turnaround_time", "page_fault_rate", "average_latency", "deadlocks"
    operator: str  # e.g., "<=", "==", ">"
    value: Any

class FacultyModule(BaseModel):
    module_id: str = Field(..., description="Unique ID for the lab module")
    title: str = Field(..., description="Title of the lab module")
    system_type: str = Field(..., description="OS or DBMS")
    description: str = Field("", description="Module description for students")
    configuration: Dict[str, Any] = Field(
        default_factory=dict, 
        description="Engine settings overrides (quantum, ram, block size, pool size)"
    )
    scenarios: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Initial processes or database query load profiles"
    )
    assertions: List[Assertion] = Field(
        default_factory=list,
        description="Automated grading rules for students"
    )

class LabSubmission(BaseModel):
    module_id: str
    student_config: Dict[str, Any]
