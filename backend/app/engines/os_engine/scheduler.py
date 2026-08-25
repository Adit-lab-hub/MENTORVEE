from typing import List, Dict, Any, Tuple
from app.engines.os_engine.process_state import PCB, ProcessState
from app.engines.os_engine.memory_paging import MemoryPagingSimulator

class OSSchedulerSimulator:
    def __init__(self, algorithm: str = "Round Robin", quantum: float = 2.0, context_switch_overhead: float = 0.1):
        self.algorithm = algorithm
        self.quantum = quantum
        self.context_switch_overhead = context_switch_overhead

    def run_simulation(
        self, 
        processes_list: List[PCB], 
        paging_sim: MemoryPagingSimulator
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, Any]]:
        gantt_chart = []
        current_time = 0.0
        processes = sorted(processes_list, key=lambda p: p.arrival_time)
        pcbs = {p.process_id: p for p in processes}
        active_pids = list(pcbs.keys())
        last_running_pid = None
        paging_sim.reset()
        
        if self.algorithm == "FCFS":
            ready_queue = []
            completed = []
            while len(completed) < len(active_pids):
                for p in processes:
                    if p.arrival_time <= current_time and p.state == ProcessState.NEW:
                        p.admit()
                        ready_queue.append(p.process_id)
                if ready_queue:
                    pid = ready_queue.pop(0)
                    pcb = pcbs[pid]
                    if last_running_pid is not None and last_running_pid != pid:
                        if self.context_switch_overhead > 0:
                            gantt_chart.append({
                                "start_time": current_time,
                                "end_time": current_time + self.context_switch_overhead,
                                "process_id": "overhead",
                                "action": "context_switch"
                            })
                            current_time += self.context_switch_overhead
                    pcb.dispatch(current_time)
                    start = current_time
                    execution_time = pcb.remaining_time
                    if pcb.memory_pages:
                        access_count = max(1, int(execution_time))
                        for _ in range(access_count):
                            page_num = pcb.memory_pages[pcb.page_index % len(pcb.memory_pages)]
                            paging_sim.access_page(pid, page_num)
                            pcb.page_index += 1
                    elapsed_time = execution_time
                    if paging_sim.is_thrashing():
                        elapsed_time = execution_time * 3.0
                    current_time += elapsed_time
                    pcb.timeout(execution_time, current_time)
                    gantt_chart.append({
                        "start_time": start,
                        "end_time": current_time,
                        "process_id": pid,
                        "action": "execute"
                    })
                    completed.append(pid)
                    last_running_pid = pid
                else:
                    next_arrival = min([p.arrival_time for p in processes if p.state == ProcessState.NEW], default=current_time + 1.0)
                    idle_duration = next_arrival - current_time
                    if idle_duration <= 0:
                        idle_duration = 1.0
                    gantt_chart.append({
                        "start_time": current_time,
                        "end_time": current_time + idle_duration,
                        "process_id": "idle",
                        "action": "idle"
                    })
                    current_time += idle_duration
                    
        elif self.algorithm == "Round Robin":
            ready_queue = []
            completed = []
            in_queue = set()
            while len(completed) < len(active_pids):
                for pid, pcb in pcbs.items():
                    if pcb.arrival_time <= current_time and pcb.state == ProcessState.NEW:
                        pcb.admit()
                        if pid not in in_queue:
                            ready_queue.append(pid)
                            in_queue.add(pid)
                if ready_queue:
                    pid = ready_queue.pop(0)
                    in_queue.remove(pid)
                    pcb = pcbs[pid]
                    if last_running_pid is not None and last_running_pid != pid:
                        if self.context_switch_overhead > 0:
                            gantt_chart.append({
                                "start_time": current_time,
                                "end_time": current_time + self.context_switch_overhead,
                                "process_id": "overhead",
                                "action": "context_switch"
                            })
                            current_time += self.context_switch_overhead
                    pcb.dispatch(current_time)
                    start = current_time
                    run_duration = min(self.quantum, pcb.remaining_time)
                    if pcb.memory_pages:
                        access_count = max(1, int(run_duration))
                        for _ in range(access_count):
                            page_num = pcb.memory_pages[pcb.page_index % len(pcb.memory_pages)]
                            paging_sim.access_page(pid, page_num)
                            pcb.page_index += 1
                    elapsed_duration = run_duration
                    if paging_sim.is_thrashing():
                        elapsed_duration = run_duration * 3.0
                    current_time += elapsed_duration
                    pcb.timeout(run_duration, current_time)
                    gantt_chart.append({
                        "start_time": start,
                        "end_time": current_time,
                        "process_id": pid,
                        "action": "execute"
                    })
                    for arr_pid, arr_pcb in pcbs.items():
                        if arr_pcb.arrival_time <= current_time and arr_pcb.state == ProcessState.NEW:
                            arr_pcb.admit()
                            if arr_pid not in in_queue:
                                ready_queue.append(arr_pid)
                                in_queue.add(arr_pid)
                    if pcb.state == ProcessState.TERMINATED:
                        completed.append(pid)
                    else:
                        ready_queue.append(pid)
                        in_queue.add(pid)
                    last_running_pid = pid
                else:
                    next_arrival = min([p.arrival_time for p in pcbs.values() if p.state == ProcessState.NEW], default=current_time + 1.0)
                    idle_duration = next_arrival - current_time
                    if idle_duration <= 0:
                        idle_duration = 1.0
                    gantt_chart.append({
                        "start_time": current_time,
                        "end_time": current_time + idle_duration,
                        "process_id": "idle",
                        "action": "idle"
                    })
                    current_time += idle_duration
                    
        elif self.algorithm == "Priority":
            completed = []
            while len(completed) < len(active_pids):
                available = [p for p in pcbs.values() if p.arrival_time <= current_time and p.state in [ProcessState.NEW, ProcessState.READY]]
                if available:
                    available.sort(key=lambda p: p.priority, reverse=True)
                    pcb = available[0]
                    pid = pcb.process_id
                    if pcb.state == ProcessState.NEW:
                        pcb.admit()
                    if last_running_pid is not None and last_running_pid != pid:
                        if self.context_switch_overhead > 0:
                            gantt_chart.append({
                                "start_time": current_time,
                                "end_time": current_time + self.context_switch_overhead,
                                "process_id": "overhead",
                                "action": "context_switch"
                            })
                            current_time += self.context_switch_overhead
                    pcb.dispatch(current_time)
                    start = current_time
                    execution_time = pcb.remaining_time
                    if pcb.memory_pages:
                        access_count = max(1, int(execution_time))
                        for _ in range(access_count):
                            page_num = pcb.memory_pages[pcb.page_index % len(pcb.memory_pages)]
                            paging_sim.access_page(pid, page_num)
                            pcb.page_index += 1
                    elapsed_time = execution_time
                    if paging_sim.is_thrashing():
                        elapsed_time = execution_time * 3.0
                    current_time += elapsed_time
                    pcb.timeout(execution_time, current_time)
                    gantt_chart.append({
                        "start_time": start,
                        "end_time": current_time,
                        "process_id": pid,
                        "action": "execute"
                    })
                    completed.append(pid)
                    last_running_pid = pid
                else:
                    next_arrival = min([p.arrival_time for p in pcbs.values() if p.state == ProcessState.NEW], default=current_time + 1.0)
                    idle_duration = next_arrival - current_time
                    if idle_duration <= 0:
                        idle_duration = 1.0
                    gantt_chart.append({
                        "start_time": current_time,
                        "end_time": current_time + idle_duration,
                        "process_id": "idle",
                        "action": "idle"
                    })
                    current_time += idle_duration

        elif self.algorithm == "MLFQ":
            q0 = []
            q1 = []
            q2 = []
            completed = []
            queue_map = {pid: 0 for pid in active_pids}
            in_queues = set()
            while len(completed) < len(active_pids):
                for pid, pcb in pcbs.items():
                    if pcb.arrival_time <= current_time and pcb.state == ProcessState.NEW:
                        pcb.admit()
                        if pid not in in_queues:
                            q0.append(pid)
                            queue_map[pid] = 0
                            in_queues.add(pid)
                selected_pid = None
                quantum_limit = 0.0
                if q0:
                    selected_pid = q0.pop(0)
                    quantum_limit = 1.0
                elif q1:
                    selected_pid = q1.pop(0)
                    quantum_limit = 3.0
                elif q2:
                    selected_pid = q2.pop(0)
                    quantum_limit = float('inf')
                if selected_pid:
                    in_queues.remove(selected_pid)
                    pcb = pcbs[selected_pid]
                    current_q = queue_map[selected_pid]
                    if last_running_pid is not None and last_running_pid != selected_pid:
                        if self.context_switch_overhead > 0:
                            gantt_chart.append({
                                "start_time": current_time,
                                "end_time": current_time + self.context_switch_overhead,
                                "process_id": "overhead",
                                "action": "context_switch"
                            })
                            current_time += self.context_switch_overhead
                    pcb.dispatch(current_time)
                    start = current_time
                    run_duration = min(quantum_limit, pcb.remaining_time)
                    if pcb.memory_pages:
                        access_count = max(1, int(run_duration))
                        for _ in range(access_count):
                            page_num = pcb.memory_pages[pcb.page_index % len(pcb.memory_pages)]
                            paging_sim.access_page(selected_pid, page_num)
                            pcb.page_index += 1
                    elapsed_duration = run_duration
                    if paging_sim.is_thrashing():
                        elapsed_duration = run_duration * 3.0
                    current_time += elapsed_duration
                    pcb.timeout(run_duration, current_time)
                    gantt_chart.append({
                        "start_time": start,
                        "end_time": current_time,
                        "process_id": selected_pid,
                        "action": "execute"
                    })
                    for arr_pid, arr_pcb in pcbs.items():
                        if arr_pcb.arrival_time <= current_time and arr_pcb.state == ProcessState.NEW:
                            arr_pcb.admit()
                            if arr_pid not in in_queues:
                                q0.append(arr_pid)
                                queue_map[arr_pid] = 0
                                in_queues.add(arr_pid)
                    if pcb.state == ProcessState.TERMINATED:
                        completed.append(selected_pid)
                    else:
                        if run_duration >= quantum_limit:
                            next_q = min(current_q + 1, 2)
                        else:
                            next_q = current_q
                        queue_map[selected_pid] = next_q
                        if next_q == 0:
                            q0.append(selected_pid)
                        elif next_q == 1:
                            q1.append(selected_pid)
                        else:
                            q2.append(selected_pid)
                        in_queues.add(selected_pid)
                    last_running_pid = selected_pid
                else:
                    next_arrival = min([p.arrival_time for p in pcbs.values() if p.state == ProcessState.NEW], default=current_time + 1.0)
                    idle_duration = next_arrival - current_time
                    if idle_duration <= 0:
                        idle_duration = 1.0
                    gantt_chart.append({
                        "start_time": current_time,
                        "end_time": current_time + idle_duration,
                        "process_id": "idle",
                        "action": "idle"
                    })
                    current_time += idle_duration
                    
        states_summary = []
        total_waiting = 0.0
        total_turnaround = 0.0
        for pid, p in pcbs.items():
            p.turnaround_time = max(0.0, p.completion_time - p.arrival_time)
            p.waiting_time = max(0.0, p.turnaround_time - p.burst_time)
            states_summary.append({
                "process_id": pid,
                "state": p.state.value,
                "burst_time": p.burst_time,
                "remaining_time": p.remaining_time,
                "waiting_time": p.waiting_time,
                "turnaround_time": p.turnaround_time
            })
            total_waiting += p.waiting_time
            total_turnaround += p.turnaround_time
        avg_waiting = total_waiting / len(active_pids) if active_pids else 0.0
        avg_turnaround = total_turnaround / len(active_pids) if active_pids else 0.0
        
        page_table_res = {}
        for pid, pcb in pcbs.items():
            entries = []
            for page_num in pcb.memory_pages:
                frame_num = None
                for f, (allocated_pid, allocated_page) in paging_sim.frames.items():
                    if allocated_pid == pid and allocated_page == page_num:
                        frame_num = f
                        break
                entries.append({
                    "page_num": page_num,
                    "frame_num": frame_num,
                    "referenced_time": current_time
                })
            page_table_res[pid] = entries
            
        fault_rate = paging_sim.page_faults / paging_sim.page_accesses if paging_sim.page_accesses > 0 else 0.0
        memory_summary = {
            "page_table": page_table_res,
            "frames_allocated": len(paging_sim.frames),
            "total_frames": paging_sim.total_frames,
            "page_faults": paging_sim.page_faults,
            "page_fault_rate": fault_rate,
            "is_thrashing": paging_sim.is_thrashing()
        }
        return gantt_chart, states_summary, memory_summary
