import json
from fastapi import APIRouter, Depends, HTTPException, status, Form, Body
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import get_current_user, get_current_active_user, RoleChecker
from app.models.models import User, Content, ClassSubject
from app.schemas.module_schema import (
    GenerateSimulationRequest,
    GenerateSimulationResponse,
    FacultyModuleSchema,
    LabValidationSubmission,
    LabValidationResult
)
from app.services.simulation_generator import AISimulationGeneratorService
from app.engines.os_engine.scheduler import OSSchedulerSimulator
from app.engines.os_engine.process_state import PCB
from app.engines.os_engine.memory_paging import MemoryPagingSimulator
from app.engines.dbms_engine.btree_simulator import BTreeSimulator
from app.engines.dbms_engine.cost_model import DBMSSimulationCostModel

router = APIRouter()

@router.post("/generate", response_model=GenerateSimulationResponse)
@router.post("/generate-ai-simulation", response_model=GenerateSimulationResponse)
def generate_ai_simulation(
    request: GenerateSimulationRequest
):
    """Converts faculty natural language prompt text into an executable Simulation JSON Schema."""
    try:
        response = AISimulationGeneratorService.generate_from_prompt(request)
        return response
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI Simulation Generation Failed: {str(e)}")


@router.post("/validate")
def validate_simulation_schema(payload: dict = Body(...)):
    """Validates raw JSON simulation schema against MENTORVEE engine specifications."""
    raw_json_str = payload.get("raw_json", "")
    if isinstance(raw_json_str, dict):
        raw_json_str = json.dumps(raw_json_str)

    if not raw_json_str.strip():
        raise HTTPException(status_code=400, detail="Empty raw_json provided for validation")

    is_valid, schema, msg = AISimulationGeneratorService.validate_schema_json(raw_json_str)
    return {
        "valid": is_valid,
        "message": msg,
        "schema": schema.model_dump() if schema else None
    }

@router.post("/publish-lab")
def publish_lab_module(
    payload: dict = Body(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Publishes a validated AI or custom simulation schema directly as a class lab."""
    if current_user.role not in ["teacher", "admin"]:
        raise HTTPException(status_code=403, detail="Only teachers and administrators can publish simulation labs.")

    class_id = payload.get("class_id")
    if not class_id:
        raise HTTPException(status_code=400, detail="Target class_id is required")

    cls = db.query(ClassSubject).filter(ClassSubject.id == class_id).first()
    if not cls:
        raise HTTPException(status_code=400, detail="Target class not found")

    schema_data = payload.get("schema")
    if not schema_data:
        raw_json = payload.get("raw_json")
        if raw_json:
            try:
                schema_data = json.loads(raw_json) if isinstance(raw_json, str) else raw_json
            except Exception:
                raise HTTPException(status_code=400, detail="Invalid JSON schema provided")
        else:
            raise HTTPException(status_code=400, detail="Simulation schema payload is required")

    is_valid, schema, msg = AISimulationGeneratorService.validate_schema_json(
        json.dumps(schema_data) if isinstance(schema_data, dict) else schema_data
    )
    if not is_valid or not schema:
        raise HTTPException(status_code=400, detail=f"Schema validation failed: {msg}")

    # Create new Content record
    new_lab = Content(
        title=schema.title,
        description=schema.description,
        type="lab",
        payload=json.dumps(schema.model_dump()),
        uploaded_by=current_user.id,
        class_id=class_id
    )
    db.add(new_lab)
    db.commit()
    db.refresh(new_lab)

    return {
        "message": f"Lab '{schema.title}' published successfully to {cls.name}!",
        "content_id": new_lab.id,
        "system_type": schema.system_type
    }

@router.post("/validate-submission", response_model=LabValidationResult)
def validate_student_submission(submission: LabValidationSubmission):
    """Executes the simulation engine against student configurations and evaluates assertion rules."""
    sys_type = submission.system_type.upper()
    results = []
    all_passed = True
    metrics = {}

    try:
        if sys_type == "OS":
            # Run OS engine
            cfg = submission.student_config
            ram = int(cfg.get("ram_size_mb", 16))
            policy = cfg.get("page_replacement_policy", "LRU")
            algo = cfg.get("algorithm", "Round Robin")
            quantum = float(cfg.get("quantum", 2.0))
            overhead = float(cfg.get("context_switch_overhead", 0.1))
            
            scenarios = cfg.get("scenarios", [])
            if not scenarios:
                scenarios = [
                    {"process_id": "P1", "burst_time": 4.0, "arrival_time": 0.0, "priority": 1, "memory_pages": [1, 2, 3, 4, 5, 6, 7, 8]}
                ]

            processes = [
                PCB(
                    process_id=s.get("process_id", f"P{i+1}"),
                    burst_time=float(s.get("burst_time", 4.0)),
                    arrival_time=float(s.get("arrival_time", 0.0)),
                    priority=int(s.get("priority", 1)),
                    memory_pages=s.get("memory_pages", [])
                )
                for i, s in enumerate(scenarios)
            ]

            scheduler = OSSchedulerSimulator(algorithm=algo, quantum=quantum, context_switch_overhead=overhead)
            paging_sim = MemoryPagingSimulator(ram_size_mb=ram, page_size_kb=4, policy=policy)
            gantt, states, mem_summary = scheduler.run_simulation(processes, paging_sim)

            total_waiting = sum(p["waiting_time"] for p in states)
            total_turnaround = sum(p["turnaround_time"] for p in states)
            avg_waiting = total_waiting / len(states) if states else 0.0
            avg_turnaround = total_turnaround / len(states) if states else 0.0

            metrics = {
                "page_fault_rate": mem_summary.get("page_fault_rate", 0.0),
                "is_thrashing": mem_summary.get("is_thrashing", False),
                "page_faults": mem_summary.get("page_faults", 0),
                "average_waiting_time": avg_waiting,
                "average_turnaround_time": avg_turnaround
            }

        else: # DBMS
            cfg = submission.student_config
            storage_type = cfg.get("storage_type", "SSD")
            index_type = cfg.get("index_type", "B-Tree")
            buffer_pool_size = int(cfg.get("buffer_pool_size", 100))
            num_records = int(cfg.get("num_records", 100000))
            query_type = cfg.get("query_type", "point")
            range_fraction = float(cfg.get("range_fraction", 0.1))
            concurrent_requests = int(cfg.get("concurrent_requests", 1))

            btree_sim = BTreeSimulator(block_size_bytes=4096, record_size_bytes=128)
            btree_metrics = btree_sim.calculate_metrics(num_records, range_fraction)
            cost_model = DBMSSimulationCostModel(
                disk_seek_ms=0.1 if storage_type == "SSD" else 8.0,
                disk_transfer_mbps=100.0,
                cpu_latency_ms=0.05
            )
            is_seq = (query_type != "point")
            if index_type == "B-Tree":
                hops = btree_metrics["btree_point_hops"] if query_type == "point" else btree_metrics["btree_range_hops"]
                bytes_read = btree_metrics["btree_point_bytes_read"] if query_type == "point" else btree_metrics["btree_range_bytes_read"]
            else:
                hops = btree_metrics["linear_scan_point_hops"] if query_type == "point" else btree_metrics["linear_scan_range_hops"]
                bytes_read = btree_metrics["linear_scan_point_bytes_read"] if query_type == "point" else btree_metrics["linear_scan_range_bytes_read"]
                is_seq = True

            cost = cost_model.calculate_cost(
                hops=hops,
                bytes_read=bytes_read,
                is_sequential=is_seq,
                cache_hit_ratio=float(buffer_pool_size / 200.0),
                concurrent_requests=concurrent_requests,
                pool_size=10
            )

            metrics = {
                "estimated_latency_ms": cost["estimated_latency_ms"],
                "disk_iops": cost["disk_iops"],
                "cache_hit_ratio": min(1.0, float(buffer_pool_size / 200.0)),
                "cpu_utilization": cost["cpu_utilization"],
                "btree_height": btree_metrics["btree_height"],
                "node_hops": hops
            }

        # Evaluate Assertions
        for a in submission.assertions:
            actual_val = metrics.get(a.metric)
            if actual_val is None:
                passed = False
                reason = f"Metric '{a.metric}' not measured"
            else:
                if a.operator == "<=":
                    passed = float(actual_val) <= float(a.value)
                elif a.operator == ">=":
                    passed = float(actual_val) >= float(a.value)
                elif a.operator == "==":
                    passed = (actual_val == a.value or str(actual_val).lower() == str(a.value).lower())
                elif a.operator == "<":
                    passed = float(actual_val) < float(a.value)
                elif a.operator == ">":
                    passed = float(actual_val) > float(a.value)
                else:
                    passed = False

                reason = f"Actual {actual_val} {a.operator} Target {a.value}"

            if not passed:
                all_passed = False

            results.append({
                "metric": a.metric,
                "operator": a.operator,
                "target_value": a.value,
                "actual_value": actual_val,
                "passed": passed,
                "description": a.description or reason
            })

        feedback = "🎉 All grading assertions PASSED! Simulation criteria successfully met." if all_passed else "❌ One or more grading assertions failed. Review the assertion breakdown and adjust simulation parameters."

        return LabValidationResult(
            passed=all_passed,
            assertions_results=results,
            metrics=metrics,
            feedback=feedback
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Simulation validation error: {str(e)}")
