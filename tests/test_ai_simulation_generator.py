import json
from unittest.mock import MagicMock
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.config import settings
from app.schemas.module_schema import (
    GenerateSimulationRequest,
    FacultyModuleSchema,
    Assertion,
    LabValidationSubmission
)
from app.services.simulation_generator import AISimulationGeneratorService

client = TestClient(app)

# ----------------------------------------------------
# 1. Deterministic NLP Engine Tests
# ----------------------------------------------------
def test_generate_os_thrashing_simulation_deterministic(monkeypatch):
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "")
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "")

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


def test_generate_os_scheduling_simulation_deterministic(monkeypatch):
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "")
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "")

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


def test_generate_dbms_btree_simulation_deterministic(monkeypatch):
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "")
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "")

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

    with pytest.raises(ValueError):
        AISimulationGeneratorService.generate_from_prompt(GenerateSimulationRequest(faculty_prompt=""))


def test_faculty_prompt_and_domain_aliases():
    req = GenerateSimulationRequest(
        faculty_prompt="Design a Round Robin CPU scheduling lab with quantum of 2.0ms",
        domain="OS",
        difficulty="advanced"
    )
    assert req.prompt == "Design a Round Robin CPU scheduling lab with quantum of 2.0ms"
    assert req.target_system == "OS"
    assert req.difficulty == "advanced"


# ----------------------------------------------------
# 2. Google Gemini SDK Mock Tests
# ----------------------------------------------------
def test_gemini_sdk_structured_generation_mocked(monkeypatch):
    """Verifies that the Google GenAI SDK is called and the structured response is parsed."""
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "test-gemini-key-12345")
    monkeypatch.setattr(settings, "GEMINI_MODEL", "gemini-2.5-flash")

    mock_gemini_json = {
        "system_type": "OS",
        "title": "Gemini Generated MLFQ Priority Lab",
        "description": "Evaluate multi-level feedback queue scheduling priorities and preemption delays.",
        "concept_focus": "Multi-Level Feedback Queue (MLFQ)",
        "configuration": {
            "ram_size_mb": 32,
            "algorithm": "MLFQ",
            "quantum": 2.5,
            "page_replacement_policy": "LRU",
            "context_switch_overhead": 0.1,
            "page_size_kb": 4
        },
        "scenarios": [
            {"process_id": "P1", "burst_time": 6.0, "arrival_time": 0.0, "priority": 1, "memory_pages": [1, 2, 3]},
            {"process_id": "P2", "burst_time": 8.0, "arrival_time": 1.0, "priority": 2, "memory_pages": [2, 3, 4]}
        ],
        "assertions": [
            {"metric": "average_waiting_time", "operator": "<=", "value": 10.0, "description": "Average wait <= 10ms"},
            {"metric": "page_fault_rate", "operator": "<=", "value": 0.4, "description": "Fault rate <= 40%"}
        ],
        "explanation": "Synthesized 2-process workload to test MLFQ priority demotions and LRU paging."
    }

    mock_response = MagicMock()
    mock_response.text = json.dumps(mock_gemini_json)

    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = mock_response

    import google.genai
    monkeypatch.setattr(google.genai, "Client", lambda api_key: mock_client)

    req = GenerateSimulationRequest(
        faculty_prompt="Create an MLFQ scheduling simulation with 2 processes and LRU paging",
        domain="OS"
    )
    res = AISimulationGeneratorService.generate_from_prompt(req)

    assert res.success is True
    assert res.simulation_schema.system_type == "OS"
    assert res.simulation_schema.title == "Gemini Generated MLFQ Priority Lab"
    assert res.simulation_schema.configuration.get("algorithm") == "MLFQ"
    assert len(res.simulation_schema.scenarios) == 2
    assert len(res.simulation_schema.assertions) == 2
    assert mock_client.models.generate_content.called


def test_gemini_sdk_error_fallback_to_deterministic(monkeypatch):
    """Verifies that when Gemini SDK raises an exception, the service falls back gracefully to deterministic engine."""
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "test-gemini-key-invalid")
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "")

    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = RuntimeError("API Quota Exceeded or Network Failure")

    import google.genai
    monkeypatch.setattr(google.genai, "Client", lambda api_key: mock_client)

    req = GenerateSimulationRequest(
        prompt="Create an OS memory lab with 3 processes demonstrating LRU page thrashing with 8MB RAM",
        target_system="OS"
    )
    res = AISimulationGeneratorService.generate_from_prompt(req)

    # Must succeed via deterministic fallback
    assert res.success is True
    assert res.simulation_schema.system_type == "OS"
    assert res.simulation_schema.configuration.get("ram_size_mb") == 8
    assert len(res.simulation_schema.scenarios) >= 2


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
# 3. Schema & Simulation API Endpoints Tests
# ----------------------------------------------------
def test_api_simulation_generate_endpoint():
    """Tests POST /api/v1/simulation/generate with faculty_prompt and domain."""
    response = client.post(
        "/api/v1/simulation/generate",
        json={
            "faculty_prompt": "Create an OS simulation testing MLFQ multi-level feedback queue scheduling with 3 processes",
            "domain": "OS"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["simulation_schema"]["system_type"] == "OS"
    assert len(data["simulation_schema"]["scenarios"]) >= 2


def test_api_schema_generate_ai_simulation_endpoint():
    """Tests POST /api/v1/schema/generate-ai-simulation for compatibility."""
    response = client.post(
        "/api/v1/schema/generate-ai-simulation",
        json={
            "prompt": "Create an OS simulation testing Round Robin scheduling with quantum 2.0ms",
            "target_system": "OS"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["simulation_schema"]["system_type"] == "OS"


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
        "/api/v1/simulation/validate",
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
        "/api/v1/simulation/validate-submission",
        json=submission_payload
    )
    assert response.status_code == 200
    res_data = response.json()
    assert res_data["passed"] is True
    assert len(res_data["assertions_results"]) == 2


def test_api_validate_submission_dbms():
    submission_payload = {
        "system_type": "DBMS",
        "student_config": {
            "storage_type": "SSD",
            "index_type": "B-Tree",
            "buffer_pool_size": 120,
            "num_records": 100000,
            "query_type": "point",
            "range_fraction": 0.05,
            "concurrent_requests": 2
        },
        "assertions": [
            {"metric": "estimated_latency_ms", "operator": "<=", "value": 15.0, "description": "Point lookup latency <= 15ms"}
        ]
    }
    response = client.post(
        "/api/v1/simulation/validate-submission",
        json=submission_payload
    )
    assert response.status_code == 200
    res_data = response.json()
    assert res_data["passed"] is True
