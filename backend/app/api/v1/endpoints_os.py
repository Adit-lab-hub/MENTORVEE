from fastapi import APIRouter, HTTPException
from app.schemas.os_schemas import OSSimulationRequest, OSSimulationResult
from app.engines.os_engine.scheduler import OSSchedulerSimulator
from app.engines.os_engine.process_state import PCB
from app.engines.os_engine.memory_paging import MemoryPagingSimulator

router = APIRouter()

@router.post("/simulate", response_model=OSSimulationResult)
def simulate_os(payload: OSSimulationRequest):
    try:
        processes = [
            PCB(
                process_id=p.process_id,
                burst_time=p.burst_time,
                arrival_time=p.arrival_time,
                priority=p.priority,
                memory_pages=p.memory_pages
            )
            for p in payload.processes
        ]
        scheduler = OSSchedulerSimulator(
            algorithm=payload.config.algorithm,
            quantum=payload.config.quantum,
            context_switch_overhead=payload.config.context_switch_overhead
        )
        paging_sim = MemoryPagingSimulator(
            ram_size_mb=payload.config.ram_size_mb,
            page_size_kb=payload.config.page_size_kb,
            policy=payload.config.page_replacement_policy
        )
        gantt, states, memory = scheduler.run_simulation(processes, paging_sim)
        total_waiting = sum(p["waiting_time"] for p in states)
        total_turnaround = sum(p["turnaround_time"] for p in states)
        avg_waiting = total_waiting / len(states) if states else 0.0
        avg_turnaround = total_turnaround / len(states) if states else 0.0
        return {
            "processes": states,
            "gantt_chart": gantt,
            "memory_summary": memory,
            "average_waiting_time": avg_waiting,
            "average_turnaround_time": avg_turnaround
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
