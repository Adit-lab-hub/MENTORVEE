from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.schemas.module_schema import FacultyModule, LabSubmission, Assertion
from app.services.schema_validator import SchemaValidatorService
from app.models.models import Content
from typing import Dict, List
import json

router = APIRouter()
modules_db: Dict[str, FacultyModule] = {}

# System presets default configurations if not present in DB
SYSTEM_PRESETS = {
    "thrashing_lab": {
        "module_id": "thrashing_lab",
        "title": "Lab 1: Memory Thrashing Investigation",
        "system_type": "OS",
        "description": "Trigger a thrashing condition by allocating high memory page streams with limited physical frame sizes.",
        "configuration": {
            "algorithm": "Round Robin",
            "quantum": 2.0,
            "context_switch_overhead": 0.1,
            "ram_size_mb": 4,
            "page_size_kb": 4,
            "page_replacement_policy": "LRU"
        },
        "scenarios": [
            {
                "process_id": "P1",
                "burst_time": 10.0,
                "arrival_time": 0.0,
                "priority": 1,
                "memory_pages": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
            }
        ],
        "assertions": [
            {"metric": "is_thrashing", "operator": "==", "value": True},
            {"metric": "page_fault_rate", "operator": ">=", "value": 80.0}
        ]
    },
    "scheduling_overhead_lab": {
        "module_id": "scheduling_overhead_lab",
        "title": "Lab 2: CPU Quantum Overhead Optimization",
        "system_type": "OS",
        "description": "Examine context switch cost impact. Configure processes to run with minimal quantum and measure overall CPU overhead penalty.",
        "configuration": {
            "algorithm": "Round Robin",
            "quantum": 0.5,
            "context_switch_overhead": 1.0,
            "ram_size_mb": 16,
            "page_size_kb": 4,
            "page_replacement_policy": "LRU"
        },
        "scenarios": [
            {"process_id": "P1", "burst_time": 3.0, "arrival_time": 0.0, "priority": 1},
            {"process_id": "P2", "burst_time": 2.0, "arrival_time": 0.5, "priority": 2},
            {"process_id": "P3", "burst_time": 4.0, "arrival_time": 1.0, "priority": 1}
        ],
        "assertions": [
            {"metric": "average_turnaround_time", "operator": ">=", "value": 8.0}
        ]
    },
    "deadlock_lab": {
        "module_id": "deadlock_lab",
        "title": "Lab 3: Transaction Deadlock Cycles",
        "system_type": "DBMS",
        "description": "Verify transaction schedules. Acquire locks in a circular wait condition to verify automated deadlock resolution graphs.",
        "configuration": {
            "index_type": "B-Tree",
            "storage_type": "HDD",
            "buffer_pool_size": 100,
            "pool_size": 10
        },
        "scenarios": [],
        "assertions": [
            {"metric": "deadlocks", "operator": "==", "value": True}
        ]
    }
}

def get_lab_module(module_id: str, db: Session) -> FacultyModule:
    # 1. Check memory database
    if module_id in modules_db:
        return modules_db[module_id]
        
    # 2. Check system presets
    if module_id in SYSTEM_PRESETS:
        p = SYSTEM_PRESETS[module_id]
        return FacultyModule(
            module_id=p["module_id"],
            title=p["title"],
            system_type=p["system_type"],
            description=p["description"],
            configuration=p["configuration"],
            scenarios=p["scenarios"],
            assertions=[Assertion(**a) for a in p["assertions"]]
        )
        
    # 3. Check database (content uploaded by teachers)
    # Check if module_id can be parsed as integer (database ID)
    db_id = None
    try:
        db_id = int(module_id)
    except ValueError:
        pass
        
    content_record = None
    if db_id is not None:
        content_record = db.query(Content).filter(Content.id == db_id, Content.type == "lab").first()
    else:
        # Fallback query using payload comparison or title match if needed
        pass
        
    if content_record and content_record.payload:
        try:
            p = json.loads(content_record.payload)
            return FacultyModule(
                module_id=str(content_record.id),
                title=content_record.title,
                system_type=p.get("system_type", "OS"),
                description=content_record.description,
                configuration=p.get("configuration", {}),
                scenarios=p.get("scenarios", []),
                assertions=[Assertion(**a) for a in p.get("assertions", [])]
            )
        except Exception:
            raise HTTPException(status_code=500, detail="Error parsing lab module payload from database")
            
    raise HTTPException(status_code=404, detail="Lab Module not found")

@router.post("/", response_model=FacultyModule)
def create_module(module: FacultyModule):
    modules_db[module.module_id] = module
    return module
    
@router.get("/{module_id}", response_model=FacultyModule)
def get_module(module_id: str, db: Session = Depends(get_db)):
    return get_lab_module(module_id, db)
      
@router.get("/", response_model=List[FacultyModule])
def list_modules(db: Session = Depends(get_db)):
    # Combine memory modules, system presets, and database custom labs
    combined = list(modules_db.values())
    
    # Add system presets
    for k, p in SYSTEM_PRESETS.items():
        if k not in modules_db:
            combined.append(FacultyModule(
                module_id=p["module_id"],
                title=p["title"],
                system_type=p["system_type"],
                description=p["description"],
                configuration=p["configuration"],
                scenarios=p["scenarios"],
                assertions=[Assertion(**a) for a in p["assertions"]]
            ))
            
    # Add db labs
    db_labs = db.query(Content).filter(Content.type == "lab").all()
    for dl in db_labs:
        try:
            p = json.loads(dl.payload)
            combined.append(FacultyModule(
                module_id=str(dl.id),
                title=dl.title,
                system_type=p.get("system_type", "OS"),
                description=dl.description,
                configuration=p.get("configuration", {}),
                scenarios=p.get("scenarios", []),
                assertions=[Assertion(**a) for a in p.get("assertions", [])]
            ))
        except Exception:
            continue
            
    return combined
      
@router.post("/submit")
def submit_lab(submission: LabSubmission, db: Session = Depends(get_db)):
    module = get_lab_module(submission.module_id, db)
    validation_result = SchemaValidatorService.execute_module_validation(
        module=module,
        student_config=submission.student_config
    )
    return validation_result
