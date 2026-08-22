from pydantic import BaseModel
from typing import List, Dict, Any, Optional

class ProcessCreate(BaseModel):
    process_id: str
    burst_time: float
    arrival_time: float = 0.0
    priority: int = 1
    memory_pages: List[int] = []

class OSConfig(BaseModel):
    algorithm: str = "Round Robin"  # FCFS, Round Robin, Priority, MLFQ
    quantum: float = 2.0
    context_switch_overhead: float = 0.1
    ram_size_mb: int = 16
    page_size_kb: int = 4
    page_replacement_policy: str = "LRU" # LRU, FIFO

class OSSimulationRequest(BaseModel):
    processes: List[ProcessCreate]
    config: OSConfig

class ProcessStateSummary(BaseModel):
    process_id: str
    state: str
    burst_time: float
    remaining_time: float
    waiting_time: float
    turnaround_time: float

class GanttInterval(BaseModel):
    start_time: float
    end_time: float
    process_id: str
    action: str  # "execute", "context_switch", "idle"

class PageTableEntry(BaseModel):
    page_num: int
    frame_num: Optional[int]
    referenced_time: float

class MemoryStateSummary(BaseModel):
    page_table: Dict[str, List[PageTableEntry]]
    frames_allocated: int
    total_frames: int
    page_faults: int
    page_fault_rate: float
    is_thrashing: bool

class OSSimulationResult(BaseModel):
    processes: List[ProcessStateSummary]
    gantt_chart: List[GanttInterval]
    memory_summary: MemoryStateSummary
    average_waiting_time: float
    average_turnaround_time: float
