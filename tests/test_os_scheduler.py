from app.engines.os_engine.scheduler import OSSchedulerSimulator
from app.engines.os_engine.process_state import PCB
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
