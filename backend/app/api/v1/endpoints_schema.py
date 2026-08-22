from fastapi import APIRouter, HTTPException
from app.schemas.module_schema import FacultyModule, LabSubmission
from app.services.schema_validator import SchemaValidatorService
from typing import Dict, List

router = APIRouter()
modules_db: Dict[str, FacultyModule] = {}

@router.post("/", response_model=FacultyModule)
def create_module(module: FacultyModule):
    modules_db[module.module_id] = module
    return module
    
@router.get("/{module_id}", response_model=FacultyModule)
def get_module(module_id: str):
    if module_id not in modules_db:
          raise HTTPException(status_code=404, detail="Lab Module not found")
    return modules_db[module_id]
      
@router.get("/", response_model=List[FacultyModule])
def list_modules():
    return list(modules_db.values())
      
@router.post("/submit")
def submit_lab(submission: LabSubmission):
    if submission.module_id not in modules_db:
        raise HTTPException(status_code=404, detail="Lab Module not found")
    module = modules_db[submission.module_id]
    validation_result = SchemaValidatorService.execute_module_validation(
        module=module,
        student_config=submission.student_config
    )
    return validation_result
