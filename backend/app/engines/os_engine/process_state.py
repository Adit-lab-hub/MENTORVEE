from enum import Enum
from typing import List, Optional

class ProcessState(str, Enum):
    NEW = "NEW"
    READY = "READY"
    RUNNING = "RUNNING"
    WAITING = "WAITING"
    TERMINATED = "TERMINATED"

class PCB:
    def __init__(
        self, 
        process_id: str, 
        burst_time: float, 
        arrival_time: float = 0.0, 
        priority: int = 1,
        memory_pages: Optional[List[int]] = None
    ):
        self.process_id = process_id
        self.burst_time = burst_time
        self.remaining_time = burst_time
        self.arrival_time = arrival_time
        self.priority = priority
        self.memory_pages = memory_pages or []
        self.page_index = 0
        
        self.state = ProcessState.NEW
        self.waiting_time = 0.0
        self.turnaround_time = 0.0
        self.completion_time = 0.0
        self.last_scheduled_time = 0.0
        self.started_executing = False

    def admit(self):
        if self.state == ProcessState.NEW:
            self.state = ProcessState.READY
            
    def dispatch(self, current_time: float):
        if self.state == ProcessState.READY:
            self.state = ProcessState.RUNNING
            if not self.started_executing:
                self.started_executing = True
            self.last_scheduled_time = current_time

    def timeout(self, run_duration: float, current_time: float):
        if self.state == ProcessState.RUNNING:
            self.remaining_time -= run_duration
            if self.remaining_time <= 1e-9:
                self.remaining_time = 0
                self.state = ProcessState.TERMINATED
                self.completion_time = current_time
            else:
                self.state = ProcessState.READY

    def block(self):
        if self.state == ProcessState.RUNNING:
            self.state = ProcessState.WAITING

    def wakeup(self):
        if self.state == ProcessState.WAITING:
            self.state = ProcessState.READY
