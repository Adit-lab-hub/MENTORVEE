import json
import re
import httpx
from typing import Dict, List, Any, Optional, Tuple
from app.core.config import settings
from app.schemas.module_schema import (
    FacultyModuleSchema,
    Assertion,
    GenerateSimulationRequest,
    GenerateSimulationResponse,
    OSSimulationScenario,
    DBMSSimulationScenario
)

class AISimulationGeneratorService:
    @classmethod
    def generate_from_prompt(cls, request: GenerateSimulationRequest) -> GenerateSimulationResponse:
        """Main entry point: generates a structured simulation schema from faculty natural text."""
        prompt = request.prompt.strip()
        target_sys = request.target_system or "auto"
        difficulty = request.difficulty or "intermediate"

        if not prompt:
            raise ValueError("Prompt text cannot be empty. Please provide instructions or requirements for the simulation.")

        # 1. Attempt LLM generation if API keys are available
        if settings.GEMINI_API_KEY or settings.OPENAI_API_KEY:
            llm_result = cls._generate_llm(prompt, target_sys, difficulty)
            if llm_result:
                return llm_result

        # 2. Deterministic / NLP Heuristics Fallback Engine
        return cls._generate_deterministic(prompt, target_sys, difficulty)

    @classmethod
    def _generate_llm(cls, prompt: str, target_sys: str, difficulty: str) -> Optional[GenerateSimulationResponse]:
        """Calls Gemini or OpenAI to transform faculty natural language into simulation JSON schema."""
        system_instruction = f"""
        You are an expert Computer Science Professor and Simulation Engineer for MENTORVEE.
        Convert the following faculty prompt into a strictly valid JSON Simulation Schema.

        Target System Constraint: {target_sys}
        Difficulty Level: {difficulty}

        Schema Specifications:
        For OS Simulations:
        - "system_type": "OS"
        - "title": Concise educational title
        - "description": Instructions and objective for students
        - "concept_focus": Specific concept (e.g. "LRU Page Replacement & Thrashing", "Round Robin Quantum Optimization")
        - "configuration": {{"ram_size_mb": 4 to 128, "page_replacement_policy": "LRU" or "FIFO", "algorithm": "Round Robin", "FCFS", "Priority", or "MLFQ", "quantum": float >= 0.5, "context_switch_overhead": float >= 0.0, "page_size_kb": 4}}
        - "scenarios": List of process objects [{{"process_id": "P1", "burst_time": float > 0, "arrival_time": float >= 0, "priority": int >= 1, "memory_pages": list of int [1,2,3...]}}]
        - "assertions": List of grading assertion rules [{{"metric": "page_fault_rate"|"is_thrashing"|"average_waiting_time"|"average_turnaround_time", "operator": "<="|">="|"=="|"<"|">", "value": number or bool, "description": "Human readable rule"}}]
        - "explanation": Brief AI reasoning of design decisions

        For DBMS Simulations:
        - "system_type": "DBMS"
        - "title": Concise educational title
        - "description": Instructions and objective for students
        - "concept_focus": Specific concept (e.g. "B+ Tree Indexing vs Linear Scan", "Buffer Pool IOPS Optimization")
        - "configuration": {{"storage_type": "SSD" or "HDD", "block_size_bytes": 4096, "buffer_pool_size": 10 to 500, "pool_size": 5 to 50, "index_type": "B-Tree" or "Linear Scan"}}
        - "scenarios": List of query objects [{{"query_type": "point"|"range"|"scan", "num_records": int 1000 to 1000000, "range_fraction": float 0.01 to 0.5, "concurrent_requests": int >= 1}}]
        - "assertions": List of grading assertion rules [{{"metric": "estimated_latency_ms"|"disk_iops"|"cache_hit_ratio"|"cpu_utilization"|"btree_height"|"node_hops", "operator": "<="|">="|"=="|"<"|">", "value": number, "description": "Human readable rule"}}]
        - "explanation": Brief AI reasoning of design decisions

        Faculty Prompt:
        {prompt}

        Return ONLY a JSON object matching this schema. No markdown code blocks, no other text.
        """

        if settings.GEMINI_API_KEY:
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={settings.GEMINI_API_KEY}"
                payload = {
                    "contents": [{"parts": [{"text": system_instruction}]}],
                    "generationConfig": {"temperature": 0.2, "responseMimeType": "application/json"}
                }
                resp = httpx.post(url, json=payload, timeout=15.0)
                if resp.status_code == 200:
                    text_resp = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
                    return cls._parse_and_validate_json_response(text_resp, prompt)
            except Exception:
                pass

        if settings.OPENAI_API_KEY:
            try:
                url = "https://api.openai.com/v1/chat/completions"
                headers = {"Authorization": f"Bearer {settings.OPENAI_API_KEY}"}
                payload = {
                    "model": "gpt-4o-mini",
                    "messages": [{"role": "user", "content": system_instruction}],
                    "temperature": 0.2,
                    "response_format": {"type": "json_object"}
                }
                resp = httpx.post(url, json=payload, headers=headers, timeout=15.0)
                if resp.status_code == 200:
                    text_resp = resp.json()["choices"][0]["message"]["content"]
                    return cls._parse_and_validate_json_response(text_resp, prompt)
            except Exception:
                pass

        return None

    @classmethod
    def _parse_and_validate_json_response(cls, json_text: str, original_prompt: str) -> Optional[GenerateSimulationResponse]:
        """Parses and sanitizes LLM JSON output into a validated GenerateSimulationResponse."""
        clean_text = json_text.strip()
        if clean_text.startswith("```json"):
            clean_text = clean_text[7:]
        if clean_text.startswith("```"):
            clean_text = clean_text[3:]
        if clean_text.endswith("```"):
            clean_text = clean_text[:-3]
        clean_text = clean_text.strip()

        try:
            data = json.loads(clean_text)
            
            # Normalize assertions
            assertions = []
            for a in data.get("assertions", []):
                assertions.append(Assertion(
                    metric=str(a.get("metric")),
                    operator=str(a.get("operator", "<=")),
                    value=a.get("value"),
                    description=a.get("description", "")
                ))

            module_schema = FacultyModuleSchema(
                system_type=data.get("system_type", "OS").upper(),
                title=data.get("title", "AI Generated Simulation Lab"),
                description=data.get("description", original_prompt),
                concept_focus=data.get("concept_focus", "Systems Simulation"),
                configuration=data.get("configuration", {}),
                scenarios=data.get("scenarios", []),
                assertions=assertions,
                explanation=data.get("explanation", "Simulation schema generated from prompt requirements.")
            )

            raw_pretty = json.dumps(module_schema.model_dump(), indent=2)
            summary = f"Generated {module_schema.system_type} lab schema '{module_schema.title}' with {len(module_schema.scenarios)} scenario items and {len(module_schema.assertions)} grading assertions."

            return GenerateSimulationResponse(
                success=True,
                simulation_schema=module_schema,
                raw_json=raw_pretty,
                summary=summary,
                validation_status="valid",
                recommended_assertions_explanation=module_schema.explanation
            )
        except Exception:
            return None

    @classmethod
    def _generate_deterministic(cls, prompt: str, target_sys: str, difficulty: str) -> GenerateSimulationResponse:
        """Robust NLP heuristics engine converting faculty text into valid simulation schemas."""
        p_lower = prompt.lower()
        
        # 1. Determine System Type
        if target_sys.upper() in ["OS", "DBMS"]:
            sys_type = target_sys.upper()
        else:
            dbms_score = sum(1 for w in ["dbms", "database", "sql", "btree", "b-tree", "b+ tree", "index", "buffer pool", "seek", "table scan", "disk i/o", "record", "ssd", "hdd", "query"] if w in p_lower)
            os_score = sum(1 for w in ["os", "operating system", "process", "cpu", "scheduling", "round robin", "quantum", "fcfs", "priority", "mlfq", "context switch", "paging", "page fault", "thrashing", "ram", "lru", "fifo"] if w in p_lower)
            sys_type = "DBMS" if dbms_score > os_score else "OS"

        # 2. Extract numeric parameters with regex
        ram_match = re.search(r'(\d+)\s*(?:mb|megabytes?)\s*(?:ram|memory)?', p_lower)
        ram_size = int(ram_match.group(1)) if ram_match else (8 if "thrashing" in p_lower else 16)
        ram_size = max(4, min(128, ram_size))

        quantum_match = re.search(r'(?:quantum|time slice|q)\s*(?:of|=|:)?\s*(\d+(?:\.\d+)?)\s*(?:ms)?', p_lower)
        quantum = float(quantum_match.group(1)) if quantum_match else 2.0

        records_match = re.search(r'(\d+[\d,]*)\s*(?:records?|rows?|tuples?)', p_lower)
        if records_match:
            records_count = int(records_match.group(1).replace(",", ""))
        elif "100k" in p_lower or "100,000" in p_lower:
            records_count = 100000
        elif "500k" in p_lower or "500,000" in p_lower:
            records_count = 500000
        elif "1m" in p_lower or "1,000,000" in p_lower:
            records_count = 1000000
        else:
            records_count = 150000

        # Policy & Algorithm extraction
        policy = "FIFO" if "fifo" in p_lower else "LRU"
        if "priority" in p_lower and "non-preemptive" in p_lower or "priority" in p_lower and "round robin" not in p_lower:
            algo = "Priority"
        elif "fcfs" in p_lower or "first-come" in p_lower:
            algo = "FCFS"
        elif "mlfq" in p_lower or "multilevel" in p_lower or "multi-level" in p_lower:
            algo = "MLFQ"
        else:
            algo = "Round Robin"

        storage_type = "HDD" if "hdd" in p_lower or "hard disk" in p_lower else "SSD"
        index_type = "Linear Scan" if "linear scan" in p_lower or "full table scan" in p_lower else "B-Tree"

        # 3. Build Module Schema for OS or DBMS
        if sys_type == "OS":
            # Determine scenario subtype
            if any(w in p_lower for w in ["thrash", "page fault", "memory pressure", "working set", "swap"]):
                title = "Virtual Memory Thrashing & Working Set Investigation"
                concept = "Page Replacement Policies & Memory Saturation"
                desc = (
                    f"Analyze memory page pressure under {policy} replacement with {ram_size}MB RAM allocation. "
                    "Configure process memory access sequences to evaluate page fault rates and trigger or mitigate thrashing."
                )
                config = {
                    "ram_size_mb": ram_size,
                    "page_replacement_policy": policy,
                    "algorithm": algo,
                    "quantum": quantum,
                    "context_switch_overhead": 0.1,
                    "page_size_kb": 4
                }
                scenarios = [
                    {"process_id": "P1", "burst_time": 8.0, "arrival_time": 0.0, "priority": 1, "memory_pages": [1, 2, 3, 4, 5, 6, 7, 8]},
                    {"process_id": "P2", "burst_time": 6.0, "arrival_time": 1.0, "priority": 2, "memory_pages": [2, 3, 4, 5, 6, 7, 8, 9]},
                    {"process_id": "P3", "burst_time": 5.0, "arrival_time": 2.0, "priority": 1, "memory_pages": [1, 3, 5, 7, 9, 10]}
                ]
                assertions = [
                    Assertion(metric="page_fault_rate", operator=">=", value=0.6, description="Memory pressure must induce high page fault rate (>= 60%)"),
                    Assertion(metric="is_thrashing", operator="==", value=True, description="System must demonstrate memory thrashing saturation")
                ]
                explanation = f"Configured {len(scenarios)} concurrent processes with overlapping virtual page references exceeding the {ram_size}MB frame capacity to demonstrate {policy} page replacement and thrashing."

            elif any(w in p_lower for w in ["quantum", "overhead", "context switch", "round robin"]):
                title = f"Round Robin Quantum & Context Switch Overhead Study (Q = {quantum}ms)"
                concept = "CPU Scheduling & Preemption Overheads"
                desc = (
                    f"Evaluate average turnaround and waiting times under Round Robin scheduling with a time quantum of {quantum}ms. "
                    "Optimize process priorities and burst allocations."
                )
                config = {
                    "ram_size_mb": 16,
                    "page_replacement_policy": "LRU",
                    "algorithm": "Round Robin",
                    "quantum": quantum,
                    "context_switch_overhead": 0.15,
                    "page_size_kb": 4
                }
                scenarios = [
                    {"process_id": "P1", "burst_time": 5.0, "arrival_time": 0.0, "priority": 2, "memory_pages": [1, 2]},
                    {"process_id": "P2", "burst_time": 3.0, "arrival_time": 0.5, "priority": 1, "memory_pages": [2, 3]},
                    {"process_id": "P3", "burst_time": 7.0, "arrival_time": 1.0, "priority": 3, "memory_pages": [1, 4]},
                    {"process_id": "P4", "burst_time": 2.0, "arrival_time": 1.5, "priority": 1, "memory_pages": [3, 4]}
                ]
                assertions = [
                    Assertion(metric="average_waiting_time", operator="<=", value=15.0, description="Average process wait time must remain under 15ms"),
                    Assertion(metric="average_turnaround_time", operator="<=", value=22.0, description="Average turnaround time must be optimized under 22ms")
                ]
                explanation = f"Generated a multi-process workload to study CPU time quantum preemption effects and context switch latency in Round Robin."

            else:
                title = f"Multi-Process {algo} CPU Execution & Memory Paging"
                concept = f"{algo} Scheduling & Resource Allocation"
                desc = f"Configure and evaluate process scheduling metrics under {algo} with {ram_size}MB physical RAM."
                config = {
                    "ram_size_mb": ram_size,
                    "page_replacement_policy": policy,
                    "algorithm": algo,
                    "quantum": quantum,
                    "context_switch_overhead": 0.1,
                    "page_size_kb": 4
                }
                scenarios = [
                    {"process_id": "P1", "burst_time": 4.0, "arrival_time": 0.0, "priority": 1, "memory_pages": [1, 2, 3]},
                    {"process_id": "P2", "burst_time": 3.5, "arrival_time": 1.0, "priority": 2, "memory_pages": [2, 3, 4]},
                    {"process_id": "P3", "burst_time": 6.0, "arrival_time": 2.0, "priority": 1, "memory_pages": [1, 4, 5]}
                ]
                assertions = [
                    Assertion(metric="average_waiting_time", operator="<=", value=12.0, description="Average waiting time must be <= 12ms"),
                    Assertion(metric="page_fault_rate", operator="<=", value=0.35, description="Page fault rate must remain stable (<= 35%)")
                ]
                explanation = f"Built an interactive {algo} scheduling simulation testing process execution states and memory paging."

        else: # DBMS
            if any(w in p_lower for w in ["btree", "b-tree", "b+ tree", "index", "point lookup"]):
                title = f"B+ Tree Index Access vs Disk IOPS ({records_count:,} Records)"
                concept = "Logarithmic B+ Tree Index Traversal"
                desc = (
                    f"Evaluate point and range query execution across a {records_count:,} row dataset on {storage_type} storage. "
                    "Analyze node traversal hops and buffer pool cache hit ratios."
                )
                config = {
                    "storage_type": storage_type,
                    "block_size_bytes": 4096,
                    "buffer_pool_size": 120,
                    "pool_size": 15,
                    "index_type": "B-Tree"
                }
                scenarios = [
                    {"query_type": "point", "num_records": records_count, "range_fraction": 0.05, "concurrent_requests": 4}
                ]
                assertions = [
                    Assertion(metric="estimated_latency_ms", operator="<=", value=6.0, description="Point lookup latency must be under 6ms with B+ Tree index"),
                    Assertion(metric="cache_hit_ratio", operator=">=", value=0.5, description="Buffer pool cache hit ratio must exceed 50%")
                ]
                explanation = f"Structured a B+ Tree index workload on {records_count:,} records demonstrating logarithmic lookup speed."

            elif any(w in p_lower for w in ["range", "scan", "linear", "full table"]):
                title = f"Database Range Query & Full Table Scan Cost Model ({records_count:,} Rows)"
                concept = "Sequential Scan vs Index Range Selectivity"
                desc = (
                    f"Analyze sequential block reading overhead and disk seek penalties on {storage_type} storage with {records_count:,} rows."
                )
                config = {
                    "storage_type": storage_type,
                    "block_size_bytes": 4096,
                    "buffer_pool_size": 80,
                    "pool_size": 10,
                    "index_type": index_type
                }
                scenarios = [
                    {"query_type": "range", "num_records": records_count, "range_fraction": 0.15, "concurrent_requests": 2}
                ]
                assertions = [
                    Assertion(metric="estimated_latency_ms", operator="<=", value=25.0, description="Range query cost must remain within 25ms threshold"),
                    Assertion(metric="disk_iops", operator=">=", value=100.0, description="Must show disk I/O throughput for range block reads")
                ]
                explanation = f"Configured range query load on {records_count:,} records comparing block reads against cache capacity."

            else:
                title = f"Relational Database Load & Connection Pool Simulator ({records_count:,} Records)"
                concept = "Database Concurrency & Buffer Cache Tuning"
                desc = f"Simulate database query execution and connection pool capacity on {storage_type} storage."
                config = {
                    "storage_type": storage_type,
                    "block_size_bytes": 4096,
                    "buffer_pool_size": 100,
                    "pool_size": 10,
                    "index_type": "B-Tree"
                }
                scenarios = [
                    {"query_type": "point", "num_records": records_count, "range_fraction": 0.1, "concurrent_requests": 5}
                ]
                assertions = [
                    Assertion(metric="estimated_latency_ms", operator="<=", value=10.0, description="Latency must be under 10ms"),
                    Assertion(metric="cache_hit_ratio", operator=">=", value=0.4, description="Cache hit ratio must be at least 40%")
                ]
                explanation = f"Generated a balanced DBMS load test with {records_count:,} records and concurrent connection queries."

        module_schema = FacultyModuleSchema(
            system_type=sys_type,
            title=title,
            description=desc,
            concept_focus=concept,
            configuration=config,
            scenarios=scenarios,
            assertions=assertions,
            explanation=explanation
        )

        raw_pretty = json.dumps(module_schema.model_dump(), indent=2)
        summary = f"Generated {module_schema.system_type} simulation schema '{module_schema.title}' with {len(module_schema.scenarios)} scenario items and {len(module_schema.assertions)} grading assertions."

        return GenerateSimulationResponse(
            success=True,
            simulation_schema=module_schema,
            raw_json=raw_pretty,
            summary=summary,
            validation_status="valid",
            recommended_assertions_explanation=explanation
        )

    @classmethod
    def validate_schema_json(cls, raw_json_str: str) -> Tuple[bool, Optional[FacultyModuleSchema], str]:
        """Validates a raw JSON string against the FacultyModuleSchema specifications."""
        try:
            data = json.loads(raw_json_str)
            schema = FacultyModuleSchema(**data)
            
            # System specific semantic checks
            if schema.system_type not in ["OS", "DBMS"]:
                return False, None, "system_type must be either 'OS' or 'DBMS'"

            if not schema.title.strip():
                return False, None, "Lab title cannot be empty"

            if not schema.scenarios:
                return False, None, "At least one simulation scenario (process workload or query profile) is required"

            for idx, a in enumerate(schema.assertions):
                if a.operator not in ["<=", ">=", "==", "<", ">"]:
                    return False, None, f"Assertion #{idx+1} has invalid operator '{a.operator}'"

            return True, schema, "Schema is valid and ready for simulation."
        except Exception as e:
            return False, None, f"JSON Schema Validation Error: {str(e)}"
