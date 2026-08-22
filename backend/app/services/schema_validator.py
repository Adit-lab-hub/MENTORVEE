from typing import Dict, Any, List
from app.schemas.module_schema import FacultyModule, Assertion
from app.engines.os_engine.scheduler import OSSchedulerSimulator
from app.engines.os_engine.process_state import PCB
from app.engines.os_engine.memory_paging import MemoryPagingSimulator
from app.engines.dbms_engine.btree_simulator import BTreeSimulator
from app.engines.dbms_engine.cost_model import DBMSSimulationCostModel

class SchemaValidatorService:
    @staticmethod
    def execute_module_validation(module: FacultyModule, student_config: Dict[str, Any]) -> Dict[str, Any]:
        config = {**module.configuration, **student_config}
        results = {}
        passed = True
        failed_assertions = []
        
        if module.system_type.upper() == "OS":
            processes = []
            for sc in module.scenarios:
                pcb = PCB(
                    process_id=sc["process_id"],
                    burst_time=float(sc["burst_time"]),
                    arrival_time=float(sc.get("arrival_time", 0.0)),
                    priority=int(sc.get("priority", 1)),
                    memory_pages=sc.get("memory_pages", [])
                )
                processes.append(pcb)
            scheduler = OSSchedulerSimulator(
                algorithm=config.get("algorithm", "Round Robin"),
                quantum=float(config.get("quantum", 2.0)),
                context_switch_overhead=float(config.get("context_switch_overhead", 0.1))
            )
            paging_sim = MemoryPagingSimulator(
                ram_size_mb=int(config.get("ram_size_mb", 16)),
                page_size_kb=int(config.get("page_size_kb", 4)),
                policy=config.get("page_replacement_policy", "LRU")
            )
            gantt, process_states, memory_summary = scheduler.run_simulation(processes, paging_sim)
            total_waiting = sum(p["waiting_time"] for p in process_states)
            total_turnaround = sum(p["turnaround_time"] for p in process_states)
            avg_waiting = total_waiting / len(process_states) if process_states else 0.0
            avg_turnaround = total_turnaround / len(process_states) if process_states else 0.0
            
            results = {
                "gantt": gantt,
                "processes": process_states,
                "memory": memory_summary,
                "average_waiting_time": avg_waiting,
                "average_turnaround_time": avg_turnaround
            }
            
        elif module.system_type.upper() == "DBMS":
            btree_sim = BTreeSimulator(
                block_size_bytes=int(config.get("block_size_bytes", 4096)),
                key_size_bytes=int(config.get("key_size_bytes", 16)),
                pointer_size_bytes=int(config.get("pointer_size_bytes", 8)),
                record_size_bytes=int(config.get("record_size_bytes", 128))
            )
            query_runs = []
            total_latency = 0.0
            total_iops = 0.0
            total_cpu = 0.0
            
            cost_model = DBMSSimulationCostModel(
                disk_seek_ms=float(config.get("disk_seek_ms", 8.0)),
                disk_transfer_mbps=float(config.get("disk_transfer_mbps", 100.0)),
                cpu_latency_ms=float(config.get("cpu_latency_ms", 0.05))
            )
            for sc in module.scenarios:
                num_records = int(sc.get("num_records", 100000))
                range_fraction = float(sc.get("range_fraction", 0.1))
                q_type = sc.get("query_type", "point").lower()
                concurrent = int(sc.get("concurrent_requests", 1))
                metrics = btree_sim.calculate_metrics(num_records, range_fraction)
                
                if q_type == "point":
                    hops = metrics["btree_point_hops"] if config.get("index_type", "B-Tree") == "B-Tree" else metrics["linear_scan_point_hops"]
                    bytes_read = metrics["btree_point_bytes_read"] if config.get("index_type", "B-Tree") == "B-Tree" else metrics["linear_scan_point_bytes_read"]
                    is_seq = False
                else:
                    hops = metrics["btree_range_hops"] if config.get("index_type", "B-Tree") == "B-Tree" else metrics["linear_scan_range_hops"]
                    bytes_read = metrics["btree_range_bytes_read"] if config.get("index_type", "B-Tree") == "B-Tree" else metrics["linear_scan_range_bytes_read"]
                    is_seq = (q_type == "scan" or config.get("index_type", "B-Tree") == "Linear Scan")
                    
                cost = cost_model.calculate_cost(
                    hops=hops,
                    bytes_read=bytes_read,
                    is_sequential=is_seq,
                    cache_hit_ratio=float(config.get("cache_hit_ratio", 0.0)),
                    concurrent_requests=concurrent,
                    pool_size=int(config.get("pool_size", 10))
                )
                query_runs.append({
                    "scenario": sc,
                    "metrics": metrics,
                    "cost": cost
                })
                total_latency += cost["estimated_latency_ms"]
                total_iops += cost["disk_iops"]
                total_cpu += cost["cpu_utilization"]
                
            avg_latency = total_latency / len(module.scenarios) if module.scenarios else 0.0
            avg_iops = total_iops / len(module.scenarios) if module.scenarios else 0.0
            avg_cpu = total_cpu / len(module.scenarios) if module.scenarios else 0.0
            
            results = {
                "query_runs": query_runs,
                "average_latency_ms": avg_latency,
                "average_iops": avg_iops,
                "average_cpu_utilization": avg_cpu,
                "btree_height": query_runs[0]["metrics"]["btree_height"] if query_runs else 0
            }
            
        for assertion in module.assertions:
            val = results.get(assertion.metric)
            if val is None:
                if assertion.metric == "page_fault_rate" and module.system_type == "OS":
                    val = results["memory"]["page_fault_rate"]
                elif assertion.metric == "is_thrashing" and module.system_type == "OS":
                    val = results["memory"]["is_thrashing"]
                    
            op = assertion.operator
            expected = assertion.value
            expr_passed = False
            try:
                if op == "<=":
                    expr_passed = val <= expected
                elif op == "<":
                    expr_passed = val < expected
                elif op == ">=":
                    expr_passed = val >= expected
                elif op == ">":
                    expr_passed = val > expected
                elif op == "==":
                    expr_passed = val == expected
                elif op == "!=":
                    expr_passed = val != expected
            except Exception:
                expr_passed = False
            if not expr_passed:
                passed = False
                failed_assertions.append({
                    "metric": assertion.metric,
                    "operator": op,
                    "expected": expected,
                    "actual": val
                })
        return {
            "passed": passed,
            "results": results,
            "failed_assertions": failed_assertions
        }
