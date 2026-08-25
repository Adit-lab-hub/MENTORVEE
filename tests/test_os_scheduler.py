# pyrefly: ignore [missing-import]
from app.engines.os_engine.scheduler import OSSchedulerSimulator
# pyrefly: ignore [missing-import]
from app.engines.os_engine.process_state import PCB
# pyrefly: ignore [missing-import]
from app.engines.os_engine.memory_paging import MemoryPagingSimulator

def test_fcfs_scheduling():
    processes = [
        PCB("P1", burst_time=5.0, arrival_time=0.0),
        PCB("P2", burst_time=3.0, arrival_time=2.0)
    ]
    paging_sim = MemoryPagingSimulator()
    scheduler = OSSchedulerSimulator(algorithm="FCFS", context_switch_overhead=0.0)
    gantt, states, memory = scheduler.run_simulation(processes, paging_sim)
    p1 = next(s for s in states if s["process_id"] == "P1")
    p2 = next(s for s in states if s["process_id"] == "P2")
    assert p1["waiting_time"] == 0.0
    assert p1["turnaround_time"] == 5.0
    assert p2["waiting_time"] == 3.0
    assert p2["turnaround_time"] == 6.0

def test_rr_thrashing_time_inflation():
    # 16KB RAM, 4KB Page size = 4 frames
    paging_sim = MemoryPagingSimulator(ram_size_mb=0.015625, page_size_kb=4)
    processes = [
        PCB("P1", burst_time=10.0, arrival_time=0.0, memory_pages=[1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
    ]
    scheduler = OSSchedulerSimulator(algorithm="Round Robin", quantum=1.0, context_switch_overhead=0.0)
    gantt, states, memory = scheduler.run_simulation(processes, paging_sim)
    
    p1 = next(s for s in states if s["process_id"] == "P1")
    assert p1["remaining_time"] == 0.0
    assert p1["turnaround_time"] > 10.0

def test_thrashing_fcfs_inflation():
    # 16KB RAM, 4KB Page size = 4 frames
    paging_sim = MemoryPagingSimulator(ram_size_mb=0.015625, page_size_kb=4)
    processes = [
        PCB("P1", burst_time=12.0, arrival_time=0.0, memory_pages=[1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
    ]
    scheduler = OSSchedulerSimulator(algorithm="FCFS", context_switch_overhead=0.0)
    gantt, states, memory = scheduler.run_simulation(processes, paging_sim)
    
    p1 = next(s for s in states if s["process_id"] == "P1")
    assert p1["remaining_time"] == 0.0
    assert p1["turnaround_time"] > 12.0


