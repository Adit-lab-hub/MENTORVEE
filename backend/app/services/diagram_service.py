import re
import httpx
import urllib.parse
from typing import Dict, List, Any, Optional
from app.core.config import settings
from app.schemas.content_schemas import DiagramResponse, VideoReference, MaterialAnalysisResponse, ExtractedSection
from app.services.document_parser import DocumentParserService

class DiagramService:
    @classmethod
    def analyze_and_generate(
        cls,
        file_bytes: Optional[bytes] = None,
        raw_text: Optional[str] = None,
        filename: str = "",
        title: Optional[str] = None,
        focus_topic: Optional[str] = None
    ) -> MaterialAnalysisResponse:
        """Complete pipeline: Parses document, generates flowchart, and curates video references."""
        # 1. Parse Document
        parsed = DocumentParserService.parse_document(file_bytes=file_bytes, raw_text=raw_text, filename=filename)
        
        doc_title = title or parsed.get("title", "Concept Architecture")
        key_concepts = parsed.get("key_concepts", [])
        processes = parsed.get("processes", [])
        sections = parsed.get("extracted_sections", [])
        summary = parsed.get("summary", "")
        raw_content = parsed.get("raw_text", "")

        if focus_topic and focus_topic not in ["none", "all", ""]:
            if focus_topic not in key_concepts:
                key_concepts.insert(0, focus_topic)

        # 2. Generate Mermaid Flowchart Diagram
        diagram_res = cls.generate_diagram(
            title=doc_title,
            summary=summary,
            key_concepts=key_concepts,
            processes=processes,
            sections=sections,
            raw_text=raw_content,
            focus_topic=focus_topic
        )

        # 3. Curate Video References
        video_refs = cls.curate_video_references(
            title=doc_title,
            key_concepts=key_concepts,
            processes=processes,
            sections=sections,
            focus_topic=focus_topic
        )

        return MaterialAnalysisResponse(
            title=doc_title,
            summary=summary,
            key_concepts=key_concepts,
            processes=processes,
            diagram=diagram_res,
            video_references=video_refs,
            extracted_sections=sections
        )

    @classmethod
    def generate_diagram(
        cls,
        title: str,
        summary: str,
        key_concepts: List[str],
        processes: List[str],
        sections: List[ExtractedSection],
        raw_text: str,
        focus_topic: Optional[str] = None
    ) -> DiagramResponse:
        """Generates Mermaid.js flowchart via LLM or deterministic engine."""
        # Attempt LLM Generation if API key is present
        if settings.GEMINI_API_KEY or settings.OPENAI_API_KEY:
            llm_diagram = cls._generate_diagram_llm(title, summary, key_concepts, processes, raw_text, focus_topic)
            if llm_diagram and llm_diagram.mermaid_syntax:
                return llm_diagram

        # Deterministic / Heuristic Generation
        return cls._generate_diagram_deterministic(title, summary, key_concepts, processes, sections, focus_topic)

    @classmethod
    def _generate_diagram_llm(
        cls,
        title: str,
        summary: str,
        key_concepts: List[str],
        processes: List[str],
        raw_text: str,
        focus_topic: Optional[str] = None
    ) -> Optional[DiagramResponse]:
        """Calls Gemini or OpenAI to create high-fidelity Mermaid.js flowchart."""
        # Truncate text for prompt context window
        truncated_text = raw_text[: settings.MAX_CONTENT_ANALYSIS_CHARS]
        
        prompt = f"""
        You are an expert Systems Architect and Visual Educator.
        Convert the following educational material into a valid Mermaid.js flowchart diagram:

        Document Title: {title}
        Focus Topic: {focus_topic or 'General Concept Hierarchy & Workflow'}
        Key Concepts: {', '.join(key_concepts[:8])}
        
        Source Text Summary:
        {summary}

        Detailed Content Extract:
        {truncated_text}

        Requirements for Mermaid Output:
        1. Start with `flowchart TD` or `graph TD`.
        2. Use structured subgraphs for logical components (e.g. `subgraph MemoryManagement["Memory Management Engine"]`).
        3. Use appropriate node shapes:
           - Rectangles `[Process Name]`
           - Decision diamonds `{{Condition or Check?}}`
           - Cylinders `[(Storage/Database/RAM)]`
           - Rounded rectangles `([Start/End Event])`
        4. Escape or quote special characters in node labels: e.g. `node1["Virtual Page (VPN: 0x4)"]`.
        5. Include decision paths with edge labels (e.g. `-->|Page Hit|` and `-->|Page Fault|`).
        6. Output ONLY the raw Mermaid code inside triple backticks (```mermaid ... ```) followed by a brief 2-3 sentence breakdown.
        """

        if settings.GEMINI_API_KEY:
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={settings.GEMINI_API_KEY}"
                payload = {
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {"temperature": 0.2, "maxOutputTokens": 2048}
                }
                resp = httpx.post(url, json=payload, timeout=15.0)
                if resp.status_code == 200:
                    text_resp = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
                    return cls._parse_llm_mermaid_response(text_resp, key_concepts)
            except Exception:
                pass

        if settings.OPENAI_API_KEY:
            try:
                url = "https://api.openai.com/v1/chat/completions"
                headers = {"Authorization": f"Bearer {settings.OPENAI_API_KEY}"}
                payload = {
                    "model": "gpt-4o-mini",
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.2
                }
                resp = httpx.post(url, json=payload, headers=headers, timeout=15.0)
                if resp.status_code == 200:
                    text_resp = resp.json()["choices"][0]["message"]["content"]
                    return cls._parse_llm_mermaid_response(text_resp, key_concepts)
            except Exception:
                pass

        return None

    @classmethod
    def _parse_llm_mermaid_response(cls, response_text: str, key_concepts: List[str]) -> Optional[DiagramResponse]:
        """Parses and sanitizes LLM response text into DiagramResponse."""
        mermaid_match = re.search(r"```(?:mermaid)?\s*([\s\S]*?)```", response_text)
        if mermaid_match:
            syntax = mermaid_match.group(1).strip()
        else:
            # Check if entire text looks like mermaid syntax
            if "graph " in response_text or "flowchart " in response_text:
                syntax = response_text.strip()
            else:
                return None

        sanitized_syntax = cls.sanitize_mermaid_syntax(syntax)
        
        # Extract breakdown points
        breakdown_text = re.sub(r"```[\s\S]*?```", "", response_text).strip()
        nodes_breakdown = [line.strip("-*• 0123456789.") for line in breakdown_text.split("\n") if len(line.strip()) > 10][:6]
        if not nodes_breakdown:
            nodes_breakdown = [f"Step {i+1}: {c}" for i, c in enumerate(key_concepts[:5])]

        return DiagramResponse(
            mermaid_syntax=sanitized_syntax,
            summary="Interactive concept flowchart generated from source material.",
            nodes_breakdown=nodes_breakdown,
            diagram_type="flowchart"
        )

    @classmethod
    def _generate_diagram_deterministic(
        cls,
        title: str,
        summary: str,
        key_concepts: List[str],
        processes: List[str],
        sections: List[ExtractedSection],
        focus_topic: Optional[str] = None
    ) -> DiagramResponse:
        """Produces a clean, structurally sound, and contextually rich Mermaid flowchart deterministically."""
        text_corpus = (title + " " + summary + " " + " ".join(key_concepts) + " " + (focus_topic or "")).lower()

        # 1. Virtual Memory / Paging / Thrashing Archetype
        if any(w in text_corpus for w in ["paging", "page fault", "thrashing", "tlb", "virtual memory", "frame", "ram"]):
            syntax = """flowchart TD
    classDef startEnd fill:#0ea5e9,stroke:#0284c7,stroke-width:2px,color:#fff;
    classDef decision fill:#f59e0b,stroke:#d97706,stroke-width:2px,color:#fff;
    classDef storage fill:#8b5cf6,stroke:#7c3aed,stroke-width:2px,color:#fff;
    classDef process fill:#1e293b,stroke:#38bdf8,stroke-width:1.5px,color:#f8fafc;
    classDef danger fill:#ef4444,stroke:#b91c1c,stroke-width:2px,color:#fff;

    Start([CPU Emits Virtual Address]) --> ParseAddr[Split into Virtual Page Number VPN & Offset]
    ParseAddr --> CheckTLB{TLB Lookup: Cached in Hardware?}

    subgraph FastPath ["Fast Path (Hardware MMU)"]
        CheckTLB -->|TLB Hit: Latency < 1ns| PhysLookup[Compute Physical Frame Address PFN]
        PhysLookup --> ReadRAM[(Physical RAM Frame Access)]
    end

    subgraph PageTableLookup ["Page Table Resolution"]
        CheckTLB -->|TLB Miss| InspectPTE[Read Process Page Table Entry]
        InspectPTE --> ValidBitCheck{Valid/Present Bit Set?}
        ValidBitCheck -->|Yes: In Memory| UpdateTLB[Update TLB & Cache Mapping]
        UpdateTLB --> PhysLookup
    end

    subgraph PageFaultHandler ["Page Fault Interrupt (OS Kernel)"]
        ValidBitCheck -->|No: Page Fault Trap| TrapOS[Context Switch to OS Fault Handler]
        TrapOS --> CheckFrameAvail{Free RAM Frame Available?}
        
        CheckFrameAvail -->|No: Memory Full| EvictPolicy[Execute Page Replacement: LRU / FIFO]
        EvictPolicy --> CheckDirty{Victim Frame Dirty?}
        CheckDirty -->|Yes| WriteDisk[(Write Modified Page to Swap Disk)]
        CheckDirty -->|No| FreeSlot[Discard Clean Frame]
        WriteDisk --> FreeSlot
        
        FreeSlot --> FetchDisk[(Read Target Page from Disk Storage)]
        CheckFrameAvail -->|Yes| FetchDisk
        FetchDisk --> LoadFrame[Load Page into Physical Frame]
        LoadFrame --> UpdatePTE[Update Page Table Valid Bit = 1]
        UpdatePTE --> ResumeProc([Restart Trapped Instruction])
    end

    ResumeProc --> CheckThrash{Fault Frequency > Thrashing Threshold?}
    CheckThrash -->|Yes: High Page I/O| ThrashWarning[Warning: System Thrashing Detected]:::danger
    CheckThrash -->|No: Stable| Complete([Instruction Complete]):::startEnd

    class Start,ResumeProc,Complete startEnd;
    class CheckTLB,ValidBitCheck,CheckFrameAvail,CheckDirty,CheckThrash decision;
    class ReadRAM,WriteDisk,FetchDisk storage;
    class ParseAddr,InspectPTE,UpdateTLB,PhysLookup,TrapOS,EvictPolicy,FreeSlot,LoadFrame,UpdatePTE process;"""
            
            nodes_breakdown = [
                "CPU address generation and hardware MMU translation.",
                "TLB fast-path hit vs. miss handling.",
                "Page table valid bit inspection and page fault trap trigger.",
                "Page replacement policy execution (LRU/FIFO) and dirty frame swap write-back.",
                "Disk page retrieval into allocated RAM frame and instruction restart."
            ]

        # 2. B-Tree / DBMS Index Traversal Archetype
        elif any(w in text_corpus for w in ["btree", "b-tree", "b+ tree", "index", "disk seek", "linear scan", "dbms", "buffer pool", "cost model"]):
            syntax = """flowchart TD
    classDef startEnd fill:#0ea5e9,stroke:#0284c7,stroke-width:2px,color:#fff;
    classDef decision fill:#f59e0b,stroke:#d97706,stroke-width:2px,color:#fff;
    classDef storage fill:#8b5cf6,stroke:#7c3aed,stroke-width:2px,color:#fff;
    classDef process fill:#1e293b,stroke:#38bdf8,stroke-width:1.5px,color:#f8fafc;
    classDef highlight fill:#10b981,stroke:#059669,stroke-width:2px,color:#fff;

    QueryStart([Execute SQL Point / Range Query]) --> Optimizer[Query Optimizer: Evaluate Cost Model]
    Optimizer --> PlanCheck{Index Available on Target Key?}

    subgraph BTreePath ["B+ Tree Index Scan (O log N)"]
        PlanCheck -->|Yes: Indexed Search| RootNode[Load Root B+ Tree Page]
        RootNode --> CheckBufferPool{Page in Buffer Pool Cache?}
        
        CheckBufferPool -->|Cache Hit: 0.05ms| BinarySearchRoot[In-Memory Binary Search for Child Pointer]
        CheckBufferPool -->|Cache Miss| DiskFetchRoot[(Disk Page Seek: 8.0ms)]
        DiskFetchRoot --> BufferInsert[Cache Page in Buffer Pool]
        BufferInsert --> BinarySearchRoot
        
        BinarySearchRoot --> TraverseInternal[Traverse Internal Node Levels 1..H]
        TraverseInternal --> LeafNode[Reach Leaf Node with Record Pointers]
        LeafNode --> FetchRecord[(Fetch Data Record via Tuple RID)]:::highlight
    end

    subgraph FullScanPath ["Sequential Full Table Scan (O N)"]
        PlanCheck -->|No: Unindexed Column| ScanStart[Initialize Full Table Iterator]
        ScanStart --> ReadBlock[(Read Disk Block sequentially)]
        ReadBlock --> FilterTuples[Filter Tuple Predicates in CPU]
        FilterTuples --> MoreBlocks{End of Table Reached?}
        MoreBlocks -->|No| ReadBlock
        MoreBlocks -->|Yes| OutputTuples[Accumulate Matching Tuples]
    end

    FetchRecord --> QueryResult([Return Result Set]):::startEnd
    OutputTuples --> QueryResult

    class QueryStart,QueryResult startEnd;
    class PlanCheck,CheckBufferPool,MoreBlocks decision;
    class RootNode,BufferInsert,BinarySearchRoot,TraverseInternal,LeafNode,ScanStart,FilterTuples,Optimizer,OutputTuples process;
    class DiskFetchRoot,FetchRecord,ReadBlock storage;"""

            nodes_breakdown = [
                "Query optimizer plan selection (Index Search vs Full Table Scan).",
                "Buffer Pool cache hit check vs. disk page read penalty.",
                "B+ Tree logarithmic traversal across root, internal, and leaf levels.",
                "Sequential full-table scan baseline comparison.",
                "Tuple RID pointer resolution and result set return."
            ]

        # 3. Concurrency / 2PL / Deadlock Archetype
        elif any(w in text_corpus for w in ["lock", "deadlock", "2pl", "two-phase locking", "acid", "transaction", "concurrency", "wait-for"]):
            syntax = """flowchart TD
    classDef startEnd fill:#0ea5e9,stroke:#0284c7,stroke-width:2px,color:#fff;
    classDef decision fill:#f59e0b,stroke:#d97706,stroke-width:2px,color:#fff;
    classDef storage fill:#8b5cf6,stroke:#7c3aed,stroke-width:2px,color:#fff;
    classDef process fill:#1e293b,stroke:#38bdf8,stroke-width:1.5px,color:#f8fafc;
    classDef danger fill:#ef4444,stroke:#b91c1c,stroke-width:2px,color:#fff;

    TxStart([Begin Transaction Tx]) --> LockRequest[Request Lock on Resource: Shared S or Exclusive X]
    LockRequest --> CheckLockTable{Resource Currently Locked?}

    subgraph LockManager ["Lock Manager Engine (Two-Phase Locking 2PL)"]
        CheckLockTable -->|No: Unlocked| GrantLock[Grant Lock & Register in Lock Table]
        CheckLockTable -->|Yes: Compatible S & S| GrantLock
        
        CheckLockTable -->|Conflict: X-lock Contention| EnqueueWait[Enqueue Tx in Resource Wait Queue]
        EnqueueWait --> BuildWFG[Update Wait-For Graph WFG Dependency Edge]
        BuildWFG --> RunCycleCheck{Cycle Detected in WFG?}
        
        RunCycleCheck -->|Yes: Deadlock Cycle| DeadlockVictim[Select Victim Transaction to Abort]:::danger
        DeadlockVictim --> RollbackTx[Rollback & Release All Locks Held]
        RollbackTx --> RestartTx([Retry Transaction with Exponential Backoff])
        
        RunCycleCheck -->|No Deadlock| BlockTx[Block Tx Thread until Resource Released]
    end

    subgraph ExecutionPhase ["Growing & Shrinking Phases"]
        GrantLock --> ExecOperation[Execute Read / Write on Data Buffer]
        BlockTx -->|Resource Freed| GrantLock
        ExecOperation --> HasMoreOps{More Operations in Tx?}
        HasMoreOps -->|Yes| LockRequest
        HasMoreOps -->|No: Commit| WriteWAL[(Write-Ahead Log WAL Commit Record)]
        WriteWAL --> ReleaseLocks[Shrinking Phase: Release All Held Locks]
        ReleaseLocks --> WakeupQueue[Wake up Next Waiting Transaction]
    end

    WakeupQueue --> TxEnd([Transaction Committed]):::startEnd

    class TxStart,TxEnd,RestartTx startEnd;
    class CheckLockTable,RunCycleCheck,HasMoreOps decision;
    class GrantLock,EnqueueWait,BuildWFG,BlockTx,ExecOperation,ReleaseLocks,WakeupQueue,LockRequest,RollbackTx process;
    class WriteWAL storage;"""

            nodes_breakdown = [
                "Transaction lock acquisition request (Shared vs Exclusive).",
                "Lock Manager contention evaluation and 2PL protocol compliance.",
                "Wait-For Graph (WFG) maintenance and real-time cycle detection.",
                "Deadlock victim selection, rollback, and backoff retry.",
                "Write-Ahead Log commit and lock release shrinking phase."
            ]

        # 4. CPU Scheduling / MLFQ / Round Robin Archetype
        elif any(w in text_corpus for w in ["scheduling", "round robin", "fcfs", "quantum", "mlfq", "process control block", "context switch"]):
            syntax = """flowchart TD
    classDef startEnd fill:#0ea5e9,stroke:#0284c7,stroke-width:2px,color:#fff;
    classDef decision fill:#f59e0b,stroke:#d97706,stroke-width:2px,color:#fff;
    classDef process fill:#1e293b,stroke:#38bdf8,stroke-width:1.5px,color:#f8fafc;
    classDef storage fill:#8b5cf6,stroke:#7c3aed,stroke-width:2px,color:#fff;

    NewProcess([Process Created in Ready State]) --> InsertQueue[Insert PCB into Ready Queue]
    InsertQueue --> SchedulerPick[Scheduler Selects Highest Priority / Head PCB]

    subgraph CPUExecution ["CPU Execution & Quantum Tracker"]
        SchedulerPick --> ContextSwitch[Save Old PCB & Restore New PCB Registers]
        ContextSwitch --> ExecCPU[Execute Instructions on CPU Core]
        ExecCPU --> CheckEvent{Execution Interrupt Event?}
        
        CheckEvent -->|Time Quantum Expired| PreemptProc[Preempt Process & Lower Priority Queue]
        PreemptProc --> InsertQueue
        
        CheckEvent -->|I/O or System Call| BlockIO[Move PCB to Blocked / Wait Queue]
        BlockIO --> WaitDevice[(Wait for Device / Storage I/O Completion)]
        WaitDevice --> IODone[I/O Interrupt Fired: Return to Ready Queue]
        IODone --> InsertQueue
        
        CheckEvent -->|Process Terminated| Terminate[Free Memory & Release PID]
    end

    Terminate --> Complete([Process Completed]):::startEnd

    class NewProcess,Complete startEnd;
    class CheckEvent decision;
    class InsertQueue,SchedulerPick,ContextSwitch,ExecCPU,PreemptProc,BlockIO,IODone,Terminate process;
    class WaitDevice storage;"""

            nodes_breakdown = [
                "Process creation and placement into the Ready Queue.",
                "Scheduler dispatch and hardware context-switch overhead.",
                "Time quantum evaluation and preemption.",
                "I/O blocking and interrupt-driven wake up.",
                "Process termination and resource reclamation."
            ]

        # 5. Generic Structured Systems Workflow (Built dynamically from parsed sections/processes)
        else:
            safe_title = re.sub(r'[^a-zA-Z0-9 ]', '', title)[:40] or "System Architecture"
            node_lines = []
            breakdown_lines = []
            
            node_lines.append("flowchart TD")
            node_lines.append("    classDef startEnd fill:#0ea5e9,stroke:#0284c7,stroke-width:2px,color:#fff;")
            node_lines.append("    classDef decision fill:#f59e0b,stroke:#d97706,stroke-width:2px,color:#fff;")
            node_lines.append("    classDef process fill:#1e293b,stroke:#38bdf8,stroke-width:1.5px,color:#f8fafc;")
            node_lines.append("    classDef storage fill:#8b5cf6,stroke:#7c3aed,stroke-width:2px,color:#fff;")
            node_lines.append("")
            node_lines.append(f'    Start(["Start: {safe_title}"]) --> Step1["Initialize Core Context"]')
            
            steps = processes if processes else key_concepts[:6]
            if not steps:
                steps = ["Analyze Inputs", "Validate Constraints", "Process Workflow", "Evaluate Output", "Finalize State"]

            prev_node = "Step1"
            for i, step in enumerate(steps[:6]):
                node_id = f"Node_{i+1}"
                clean_label = re.sub(r'["\(\)\[\]\{\}]', '', step)[:45]
                if not clean_label:
                    clean_label = f"Stage {i+1}"
                    
                if i % 2 == 1 and i < len(steps) - 1:
                    decision_id = f"Check_{i+1}"
                    node_lines.append(f'    {prev_node} --> {decision_id}{{"Validate {clean_label}?"}}:::decision')
                    node_lines.append(f'    {decision_id} -->|Passed| {node_id}["Execute {clean_label}"]:::process')
                    node_lines.append(f'    {decision_id} -->|Fallback / Exception| HandleError_{i}["Handle Fault & Recovery"]:::process')
                    node_lines.append(f'    HandleError_{i} --> {node_id}')
                    breakdown_lines.append(f"Validation checkpoint for {clean_label} with failure handling.")
                else:
                    node_lines.append(f'    {prev_node} --> {node_id}["{clean_label}"]:::process')
                    breakdown_lines.append(f"Step {i+1}: Execution of {clean_label}.")
                prev_node = node_id

            node_lines.append(f'    {prev_node} --> Complete(["Workflow Complete: {safe_title}"]):::startEnd')
            node_lines.append("    class Start,Complete startEnd;")
            
            syntax = "\n".join(node_lines)
            nodes_breakdown = breakdown_lines or ["Step-by-step structural process flow."]

        sanitized = cls.sanitize_mermaid_syntax(syntax)
        return DiagramResponse(
            mermaid_syntax=sanitized,
            summary=f"Automated concept flowchart for {title}.",
            nodes_breakdown=nodes_breakdown,
            diagram_type="flowchart"
        )

    @classmethod
    def sanitize_mermaid_syntax(cls, syntax: str) -> str:
        """Cleans, formats, and fixes syntax errors in Mermaid string."""
        if not syntax:
            return "flowchart TD\n    A[Start] --> B[End]"
            
        # Strip markdown code blocks
        clean = re.sub(r"^```(?:mermaid)?\s*", "", syntax.strip(), flags=re.IGNORECASE)
        clean = re.sub(r"\s*```$", "", clean.strip())

        # Ensure valid header
        first_line = clean.split("\n")[0].strip()
        valid_headers = ["flowchart", "graph", "sequenceDiagram", "classDiagram", "stateDiagram"]
        if not any(first_line.startswith(vh) for vh in valid_headers):
            clean = "flowchart TD\n" + clean

        # Sanitize unquoted parenthesis inside node brackets like [Text (Detail)] -> ["Text (Detail)"]
        def sanitize_brackets(match):
            node_id = match.group(1)
            inner = match.group(2)
            # If inner is cylinder [( ... )]
            if inner.startswith("(") and inner.endswith(")"):
                content = inner[1:-1].strip()
                if not (content.startswith('"') and content.endswith('"')):
                    clean_content = content.replace('"', "'")
                    content = f'"{clean_content}"'
                return f"{node_id}[({content})]"
            # If inner is already quoted
            if inner.startswith('"') and inner.endswith('"'):
                return f"{node_id}[{inner}]"
            # If inner has parentheses or special symbols
            if any(char in inner for char in "():,;/{}[]"):
                safe = inner.replace('"', "'")
                return f'{node_id}["{safe}"]'
            return f"{node_id}[{inner}]"

        clean = re.sub(r'([A-Za-z0-9_]+)\[([^\]\n]+)\]', sanitize_brackets, clean)

        return clean

    @classmethod
    def curate_video_references(
        cls,
        title: str,
        key_concepts: List[str],
        processes: List[str],
        sections: List[ExtractedSection],
        focus_topic: Optional[str] = None
    ) -> List[VideoReference]:
        """Discovers high-quality video tutorials mapped to core concepts and authoritative channels."""
        # Concept to authoritative channel & query mapping dictionary
        curated_library = [
            {
                "keywords": ["paging", "virtual memory", "page table", "page fault", "thrashing", "tlb", "mmu"],
                "topic": "Virtual Memory, Paging & Page Replacement",
                "channel": "MIT OpenCourseWare / Neso Academy",
                "title": "Virtual Memory: Paging, Address Translation & Page Faults",
                "search_query": "virtual memory paging page table page faults operating systems MIT OpenCourseWare",
                "description": "Comprehensive explanation of Virtual Memory architecture, Page Tables, TLB lookup paths, and LRU/FIFO page replacement under memory pressure.",
                "timestamp_notes": "00:00 Address Space Overview | 05:30 Virtual to Physical Translation | 14:20 Handling Page Faults & Thrashing"
            },
            {
                "keywords": ["btree", "b-tree", "b+ tree", "index", "indexing", "binary search", "database index"],
                "topic": "B+ Tree Indexing & Disk Cost Models",
                "channel": "CMU Database Group (Andy Pavlo) / Computerphile",
                "title": "B+ Tree Database Indexing: Insertion, Traversal & IO Cost",
                "search_query": "B+ Tree indexing database internals CMU Database Group Andy Pavlo",
                "description": "Deep dive into B+ Tree data structures in relational databases, logarithmic node search, disk block I/O efficiency, and buffer cache hits.",
                "timestamp_notes": "00:00 Why Tree Indexes? | 04:15 Internal vs Leaf Nodes | 12:00 Range Queries & IO Analysis"
            },
            {
                "keywords": ["lock", "deadlock", "2pl", "two phase locking", "acid", "concurrency", "transaction"],
                "topic": "Concurrency Control, 2PL & Deadlock Detection",
                "channel": "freeCodeCamp.org / Gate Smashers",
                "title": "Two-Phase Locking (2PL), Concurrency & Deadlock Prevention",
                "search_query": "two phase locking 2PL deadlock detection wait for graph databases",
                "description": "Explores Strict Two-Phase Locking (2PL), Serializability, Resource Contention, Wait-For Graph cycle detection, and deadlock recovery algorithms.",
                "timestamp_notes": "00:00 ACID Isolation | 03:40 Growing & Shrinking Phases | 10:15 Wait-For Graph Cycles"
            },
            {
                "keywords": ["scheduling", "round robin", "cpu", "fcfs", "mlfq", "context switch", "preemptive"],
                "topic": "CPU Scheduling Algorithms & Context Switches",
                "channel": "Neso Academy / MIT OpenCourseWare",
                "title": "CPU Scheduling: Round Robin, FCFS, Priority & Multi-Level Feedback Queues",
                "search_query": "CPU scheduling algorithms Round Robin MLFQ context switch operating systems",
                "description": "Detailed breakdown of scheduling metrics (Turnaround Time, Waiting Time, Response Time), Preemption overhead, and time quantum tuning.",
                "timestamp_notes": "00:00 CPU Burst Basics | 04:30 Round Robin Quantum Tradeoffs | 11:45 MLFQ Scheduling"
            },
            {
                "keywords": ["semaphore", "mutex", "critical section", "dining philosophers", "race condition", "ipc"],
                "topic": "Process Synchronization & Critical Sections",
                "channel": "Computerphile / Abdul Bari",
                "title": "Semaphores, Mutexes & Classical Synchronization Problems",
                "search_query": "semaphores mutex race conditions critical section operating systems Abdul Bari",
                "description": "Understanding atomic test-and-set operations, counting vs binary semaphores, avoiding race conditions, and starvation prevention.",
                "timestamp_notes": "00:00 Race Condition Demo | 06:10 Semaphore Wait & Signal | 15:30 Dining Philosophers Problem"
            },
            {
                "keywords": ["buffer pool", "cache", "lru", "disk seek", "iops", "storage engine"],
                "topic": "Database Buffer Pool & Storage Engines",
                "channel": "Hussein Nasser / CMU Database Group",
                "title": "Database Storage Engine Architecture: Buffer Pools & Disk Pages",
                "search_query": "database buffer pool disk page management storage engine Hussein Nasser",
                "description": "How modern database management systems manage memory frames, handle dirty page writebacks with WAL, and optimize disk IOPS.",
                "timestamp_notes": "00:00 Disk vs Memory Hierarchy | 07:00 Buffer Frame Table | 14:00 WAL Synchronization"
            }
        ]

        text_corpus = (title + " " + " ".join(key_concepts) + " " + (focus_topic or "")).lower()
        matched_references: List[VideoReference] = []

        # Find best matches from curated library
        for item in curated_library:
            match_score = sum(1 for kw in item["keywords"] if kw in text_corpus)
            if match_score > 0:
                query_encoded = urllib.parse.quote_plus(item["search_query"])
                watch_url = f"https://www.youtube.com/results?search_query={query_encoded}"
                # Embed search playlist / query preview
                embed_url = f"https://www.youtube.com/embed?listType=search&list={query_encoded}"
                
                matched_references.append(VideoReference(
                    title=item["title"],
                    topic=item["topic"],
                    channel=item["channel"],
                    url=watch_url,
                    embed_url=embed_url,
                    search_query=item["search_query"],
                    description=item["description"],
                    timestamp_notes=item["timestamp_notes"]
                ))

        # Dynamic fallback video references for any concepts not in the static dictionary
        if len(matched_references) < 3:
            top_concepts = [c for c in key_concepts if not any(c.lower() in ref.topic.lower() for ref in matched_references)]
            for concept in top_concepts[: 4 - len(matched_references)]:
                query = f"{concept} tutorial computer science educational lecture"
                query_encoded = urllib.parse.quote_plus(query)
                matched_references.append(VideoReference(
                    title=f"Mastering {concept}: Comprehensive Computer Science Tutorial",
                    topic=concept,
                    channel="freeCodeCamp.org / MIT OCW / Computerphile",
                    url=f"https://www.youtube.com/results?search_query={query_encoded}",
                    embed_url=f"https://www.youtube.com/embed?listType=search&list={query_encoded}",
                    search_query=query,
                    description=f"In-depth educational lecture exploring {concept} principles, system architecture implications, and real-world implementations.",
                    timestamp_notes="00:00 Core Definition | 05:00 Conceptual Breakdown | 12:00 Implementation Patterns"
                ))

        return matched_references[:6]
