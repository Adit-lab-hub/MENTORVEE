from pydantic import BaseModel, Field
from typing import Dict, List, Any, Optional

class Assertion(BaseModel):
    metric: str = Field(..., description="Target metric name (e.g. page_fault_rate, is_thrashing, average_waiting_time, estimated_latency_ms, cache_hit_ratio)")
    operator: str = Field(..., description="Comparison operator (<=, >=, ==, <, >)")
    value: Any = Field(..., description="Expected threshold value (float, int, or boolean)")
    description: Optional[str] = Field("", description="Human readable description of grading criteria")

class OSSimulationScenario(BaseModel):
    process_id: str = Field(..., description="Process identifier e.g. P1, P2")
    burst_time: float = Field(..., description="CPU burst duration in ms")
    arrival_time: float = Field(0.0, description="Arrival timestamp in ms")
    priority: int = Field(1, description="Process priority (1 = high)")
    memory_pages: List[int] = Field(default_factory=list, description="Sequence of virtual page references")

class DBMSSimulationScenario(BaseModel):
    query_type: str = Field("point", description="Query profile type: point, range, or scan")
    num_records: int = Field(100000, description="Total table row count")
    range_fraction: float = Field(0.1, description="Range query selectivity fraction")
    concurrent_requests: int = Field(1, description="Number of concurrent query transactions")

class FacultyModuleSchema(BaseModel):
    system_type: str = Field(..., description="OS or DBMS")
    title: str = Field(..., description="Title of the lab simulation module")
    description: str = Field("", description="Detailed instructions and scenario context for students")
    concept_focus: Optional[str] = Field("", description="Core concept targeted (e.g. LRU Thrashing, B-Tree Indexing)")
    configuration: Dict[str, Any] = Field(
        default_factory=dict,
        description="Engine settings overrides (ram_size_mb, algorithm, quantum, buffer_pool_size, storage_type, index_type)"
    )
    scenarios: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="List of process workloads (OS) or query load profiles (DBMS)"
    )
    assertions: List[Assertion] = Field(
        default_factory=list,
        description="Automated grading rules evaluated against simulator execution"
    )
    explanation: Optional[str] = Field("", description="AI commentary explaining how this schema fulfills the prompt")

class GenerateSimulationRequest(BaseModel):
    prompt: str = Field(..., description="Faculty natural language description of simulation requirements")
    target_system: Optional[str] = Field("auto", description="Target system: auto, OS, or DBMS")
    difficulty: Optional[str] = Field("intermediate", description="Difficulty level: beginner, intermediate, advanced")

class GenerateSimulationResponse(BaseModel):
    success: bool = True
    simulation_schema: FacultyModuleSchema
    raw_json: str
    summary: str
    validation_status: str = "valid"
    recommended_assertions_explanation: str = ""

class LabValidationSubmission(BaseModel):
    module_id: Optional[str] = ""
    system_type: str
    student_config: Dict[str, Any]
    assertions: List[Assertion]

class LabValidationResult(BaseModel):
    passed: bool
    assertions_results: List[Dict[str, Any]]
    metrics: Dict[str, Any]
    feedback: str
