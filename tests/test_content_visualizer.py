import io
import pytest
from fastapi.testclient import TestClient
from pypdf import PdfWriter
from pypdf.generic import NameObject, create_string_object
from app.main import app
from app.services.document_parser import DocumentParserService
from app.services.diagram_service import DiagramService
from app.schemas.content_schemas import (
    SourceUploadRequest,
    DiagramResponse,
    VideoReference,
    MaterialAnalysisResponse
)

client = TestClient(app)

def create_sample_pdf_bytes(text: str = "Operating Systems Virtual Memory and Paging", title: str = "Virtual Memory Lecture") -> bytes:
    """Generates an in-memory test PDF using pypdf."""
    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    # Write some annotations/text in PDF
    # In pypdf, we can add text via annotation or metadata
    writer.add_metadata({
        NameObject("/Title"): create_string_object(title),
        NameObject("/Author"): create_string_object("Prof. Test")
    })
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


# ----------------------------------------------------
# 1. Document Parser Tests
# ----------------------------------------------------
def test_document_parser_raw_text():
    sample_text = """# Operating Systems: CPU Scheduling
1. First, process enters the Ready Queue.
2. Next, scheduler allocates CPU time quantum.
3. If quantum expires, context switch triggers preemption.
4. Finally, process terminates or blocks on I/O.

### Core Concepts
Round Robin, Priority Scheduling, Context Switch, Turnaround Time.
"""
    result = DocumentParserService.parse_document(raw_text=sample_text)
    assert result["title"] == "Operating Systems: CPU Scheduling"
    assert len(result["extracted_sections"]) >= 1
    assert "Round Robin" in result["key_concepts"] or "CPU Scheduling" in result["key_concepts"]
    assert len(result["processes"]) >= 2
    assert "CPU Scheduling" in result["summary"]


def test_document_parser_markdown_and_sections():
    md_content = """# Database Systems: B+ Tree Indexing
B+ Trees provide logarithmic lookup efficiency for relational databases.

## 1. Internal Nodes
Internal nodes route search queries using pivot keys.

## 2. Leaf Nodes
Leaf nodes store actual record pointers (RID) and are linked sequentially.
"""
    result = DocumentParserService.parse_document(
        file_bytes=md_content.encode("utf-8"),
        filename="btree_notes.md"
    )
    assert result["title"] == "Database Systems: B+ Tree Indexing"
    assert len(result["extracted_sections"]) >= 2
    assert any("Internal Nodes" in s.heading for s in result["extracted_sections"])
    assert any("B+ Tree" in c or "Indexing" in c for c in result["key_concepts"])


def test_document_parser_pdf_parsing():
    pdf_bytes = create_sample_pdf_bytes(title="Virtual Memory and TLB Architectures")
    result = DocumentParserService.parse_document(file_bytes=pdf_bytes, filename="vm_lecture.pdf")
    assert result is not None
    assert "title" in result
    assert len(result["key_concepts"]) > 0


def test_document_parser_empty_error():
    with pytest.raises(ValueError):
        DocumentParserService.parse_document(raw_text="")

    with pytest.raises(ValueError):
        DocumentParserService.parse_document(file_bytes=b"")


# ----------------------------------------------------
# 2. Diagram & Video Service Tests
# ----------------------------------------------------
def test_diagram_service_flowchart_generation():
    result = DiagramService.analyze_and_generate(
        raw_text="""
        Virtual memory enables demand paging. When a process references a page not in RAM,
        a Page Fault trap is generated. The OS executes the LRU page replacement algorithm.
        If the fault rate is too high, system thrashing occurs.
        """,
        title="Virtual Memory & Thrashing Study"
    )
    
    assert isinstance(result, MaterialAnalysisResponse)
    assert result.title == "Virtual Memory & Thrashing Study"
    assert "flowchart TD" in result.diagram.mermaid_syntax
    assert len(result.diagram.nodes_breakdown) > 0
    assert len(result.video_references) >= 1
    
    # Check video reference fields
    first_video = result.video_references[0]
    assert first_video.title
    assert first_video.search_query
    assert first_video.url.startswith("https://www.youtube.com")
    assert first_video.embed_url.startswith("https://www.youtube.com/embed")


def test_diagram_service_dbms_indexing():
    result = DiagramService.analyze_and_generate(
        raw_text="""
        Database B+ Tree indexing minimizes disk seek overhead compared to full table scans.
        Buffer pool caching stores frequently accessed root and internal node pages in memory.
        """,
        title="B+ Tree Index Traversal"
    )
    assert "B+ Tree" in result.diagram.mermaid_syntax or "BufferPool" in result.diagram.mermaid_syntax or "Buffer Pool" in result.diagram.mermaid_syntax
    assert any("B+ Tree" in v.topic or "Database" in v.topic or "Index" in v.topic for v in result.video_references)


def test_mermaid_syntax_sanitization():
    raw_syntax = """```mermaid
    flowchart TD
    A[Process (PID 1)] --> B{Valid Bit Set?}
    B -->|Yes| C[(Physical RAM Frame)]
    ```"""
    cleaned = DiagramService.sanitize_mermaid_syntax(raw_syntax)
    assert "```" not in cleaned
    assert "flowchart TD" in cleaned
    assert 'A["Process (PID 1)"]' in cleaned or 'A["Process' in cleaned


# ----------------------------------------------------
# 3. Endpoint Integration Tests
# ----------------------------------------------------
def test_extract_visuals_endpoint_raw_text():
    response = client.post(
        "/api/v1/content/extract-visuals",
        data={
            "title": "Operating System Scheduling",
            "raw_text": "Round Robin uses a time quantum. Preemption forces context switches. Shortest Job First optimizes average waiting time.",
            "focus_topic": "Round Robin"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Operating System Scheduling"
    assert "diagram" in data
    assert "mermaid_syntax" in data["diagram"]
    assert len(data["video_references"]) > 0


def test_extract_visuals_endpoint_file_upload():
    txt_content = b"Two-Phase Locking (2PL) guarantees serializability. Deadlock cycles in the Wait-For Graph are resolved by aborting a victim transaction."
    files = {"file": ("concurrency.txt", txt_content, "text/plain")}
    response = client.post(
        "/api/v1/content/extract-visuals",
        files=files,
        data={"title": "Concurrency Control"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "diagram" in data
    assert len(data["video_references"]) > 0
    assert any("Lock" in v["topic"] or "Concurrency" in v["topic"] or "Deadlock" in v["topic"] for v in data["video_references"])


def test_extract_visuals_endpoint_invalid_file_type():
    files = {"file": ("malicious.exe", b"binary content", "application/octet-stream")}
    response = client.post(
        "/api/v1/content/extract-visuals",
        files=files
    )
    assert response.status_code == 400
    assert "Unsupported file format" in response.json()["detail"]


def test_extract_visuals_endpoint_empty_payload():
    response = client.post(
        "/api/v1/content/extract-visuals",
        data={}
    )
    assert response.status_code == 400
