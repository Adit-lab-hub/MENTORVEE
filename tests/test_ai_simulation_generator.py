import json
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.schemas.module_schema import (
    GenerateSimulationRequest,
    FacultyModuleSchema,
    Assertion,
    LabValidationSubmission
)
from app.services.simulation_generator import AISimulationGeneratorService

client = TestClient(app)

# ----------------------------------------------------
# 1. AI Simulation Generator Service Tests
# ----------------------------------------------------
def test_generate_os_thrashing_simulation():
    req = GenerateSimulationRequest(
        prompt="Create an OS memory lab with 3 processes demonstrating thrashing when RAM is 8MB and replacement policy is FIFO.",
        target_system="OS"
    )
    res = AISimulationGeneratorService.generate_from_prompt(req)
    
    assert res.success is True
    assert res.simulation_schema.system_type == "OS"
    assert res.simulation_schema.configuration.get("ram_size_mb") == 8
    assert res.simulation_schema.configuration.get("page_replacement_policy") == "FIFO"
    assert len(res.simulation_schema.scenarios) >= 2
    assert any(a.metric in ["page_fault_rate", "is_thrashing"] for a in res.simulation_schema.assertions)
    assert res.raw_json
    assert "OS" in res.summary


def test_generate_os_scheduling_simulation():
    req = GenerateSimulationRequest(
        prompt="Create a Round Robin CPU scheduling lab with 4 processes and quantum 1.5ms to evaluate average turnaround time.",
        target_system="OS"
    )
    res = AISimulationGeneratorService.generate_from_prompt(req)
    
    assert res.success is True
    assert res.simulation_schema.system_type == "OS"
    assert res.simulation_schema.configuration.get("algorithm") == "Round Robin"
    assert res.simulation_schema.configuration.get("quantum") == 1.5
    assert len(res.simulation_schema.scenarios) >= 3
    assert any(a.metric in ["average_waiting_time", "average_turnaround_time"] for a in res.simulation_schema.assertions)


def test_generate_dbms_btree_simulation():
    req = GenerateSimulationRequest(
        prompt="Design a relational database index lab to benchmark B+ Tree point lookups with 200,000 records on SSD storage vs full scan.",
        target_system="DBMS"
    )
    res = AISimulationGeneratorService.generate_from_prompt(req)
    
    assert res.success is True
    assert res.simulation_schema.system_type == "DBMS"
    assert res.simulation_schema.configuration.get("storage_type") == "SSD"
    assert res.simulation_schema.configuration.get("index_type") == "B-Tree"
    assert res.simulation_schema.scenarios[0].get("num_records") == 200000
    assert any(a.metric in ["estimated_latency_ms", "cache_hit_ratio", "disk_iops"] for a in res.simulation_schema.assertions)


def test_empty_prompt_validation():
    with pytest.raises(ValueError):
        AISimulationGeneratorService.generate_from_prompt(GenerateSimulationRequest(prompt="   "))


def test_validate_schema_json():
    valid_schema = {
        "system_type": "OS",
        "title": "Custom Unit Lab",
        "description": "Test instructions",
        "configuration": {"ram_size_mb": 16, "algorithm": "Round Robin"},
        "scenarios": [{"process_id": "P1", "burst_time": 4.0}],
        "assertions": [{"metric": "page_fault_rate", "operator": "<=", "value": 0.5}]
    }
    is_valid, schema, msg = AISimulationGeneratorService.validate_schema_json(json.dumps(valid_schema))
    assert is_valid is True
    assert schema is not None

    invalid_schema = {
        "system_type": "UNKNOWN_SYS",
        "title": "",
        "scenarios": []
    }
    is_valid, schema, msg = AISimulationGeneratorService.validate_schema_json(json.dumps(invalid_schema))
    assert is_valid is False
    assert schema is None


# ----------------------------------------------------
# 2. Schema API Endpoints Tests
# ----------------------------------------------------
def test_api_generate_ai_simulation():
    response = client.post(
        "/api/v1/schema/generate-ai-simulation",
        json={
            "prompt": "Create an OS simulation testing MLFQ multi-level feedback queue scheduling with 3 processes",
            "target_system": "auto"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["simulation_schema"]["system_type"] == "OS"
    assert len(data["simulation_schema"]["scenarios"]) >= 2


def test_api_validate_schema():
    valid_schema = {
        "system_type": "DBMS",
        "title": "B-Tree Indexing Lab",
        "description": "Test B-Tree hops",
        "configuration": {"index_type": "B-Tree", "storage_type": "SSD"},
        "scenarios": [{"query_type": "point", "num_records": 50000}],
        "assertions": [{"metric": "estimated_latency_ms", "operator": "<=", "value": 5.0}]
    }
    response = client.post(
        "/api/v1/schema/validate",
        json={"raw_json": json.dumps(valid_schema)}
    )
    assert response.status_code == 200
    assert response.json()["valid"] is True


def test_api_validate_submission_os():
    submission_payload = {
        "system_type": "OS",
        "student_config": {
            "ram_size_mb": 16,
            "page_replacement_policy": "LRU",
            "algorithm": "Round Robin",
            "quantum": 2.0,
            "context_switch_overhead": 0.1,
            "scenarios": [
                {"process_id": "P1", "burst_time": 4.0, "arrival_time": 0.0, "memory_pages": [1, 2]}
            ]
        },
        "assertions": [
            {"metric": "page_fault_rate", "operator": "<=", "value": 0.8, "description": "Fault rate <= 80%"},
            {"metric": "is_thrashing", "operator": "==", "value": False, "description": "No thrashing"}
        ]
    }
    response = client.post(
        "/api/v1/schema/validate-submission",
        json=submission_payload
    )
    assert response.status_code == 200
    res_data = response.json()
    assert res_data["passed"] is True
    assert len(res_data["assertions_results"]) == 2
