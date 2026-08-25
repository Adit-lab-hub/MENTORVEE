import io
import re
from typing import Dict, List, Any, Optional
from pypdf import PdfReader
from app.schemas.content_schemas import ExtractedSection

class DocumentParserService:
    @staticmethod
    def extract_text_from_pdf(file_bytes: bytes) -> Dict[str, Any]:
        """Extracts text, page count, and metadata from PDF bytes."""
        if not file_bytes:
            raise ValueError("Empty PDF file payload provided.")
            
        try:
            reader = PdfReader(io.BytesIO(file_bytes))
        except Exception as e:
            raise ValueError(f"Corrupted or invalid PDF format: {str(e)}")

        if reader.is_encrypted:
            try:
                reader.decrypt("")
            except Exception:
                raise ValueError("PDF is encrypted and password protected.")

        total_pages = len(reader.pages)
        pages_text = []
        for idx, page in enumerate(reader.pages):
            try:
                text = page.extract_text() or ""
                if text.strip():
                    pages_text.append(text.strip())
            except Exception as pe:
                pages_text.append(f"[Page {idx+1} could not be extracted: {str(pe)}]")

        full_text = "\n\n".join(pages_text)
        
        # Check if text is virtually empty (e.g. scanned image PDF)
        is_scanned = len(full_text.strip()) < 20 and total_pages > 0
        
        metadata = {}
        if reader.metadata:
            try:
                if reader.metadata.title:
                    metadata["title"] = str(reader.metadata.title)
                if reader.metadata.author:
                    metadata["author"] = str(reader.metadata.author)
                if reader.metadata.subject:
                    metadata["subject"] = str(reader.metadata.subject)
            except Exception:
                pass

        return {
            "text": full_text,
            "total_pages": total_pages,
            "is_scanned": is_scanned,
            "metadata": metadata
        }

    @staticmethod
    def extract_text_from_bytes(file_bytes: bytes, filename: str = "") -> Dict[str, Any]:
        """Decodes raw file bytes (UTF-8, Latin-1, ASCII) into text string."""
        if not file_bytes:
            return {"text": "", "encoding": "none"}
            
        encodings = ["utf-8", "utf-8-sig", "latin-1", "cp1252", "ascii"]
        for enc in encodings:
            try:
                decoded = file_bytes.decode(enc)
                return {"text": decoded, "encoding": enc}
            except (UnicodeDecodeError, UnicodeError):
                continue
                
        # Last resort replacement
        return {"text": file_bytes.decode("utf-8", errors="replace"), "encoding": "utf-8-replace"}

    @classmethod
    def parse_document(cls, file_bytes: Optional[bytes] = None, raw_text: Optional[str] = None, filename: str = "") -> Dict[str, Any]:
        """Unified document parser accepting file bytes or raw text string."""
        filename_lower = filename.lower()
        
        if file_bytes is not None:
            if filename_lower.endswith(".pdf"):
                pdf_res = cls.extract_text_from_pdf(file_bytes)
                extracted_text = pdf_res["text"]
                doc_title = pdf_res["metadata"].get("title", "")
                if not doc_title and filename:
                    doc_title = filename.rsplit(".", 1)[0].replace("_", " ").replace("-", " ").title()
                is_scanned = pdf_res.get("is_scanned", False)
                if is_scanned and not extracted_text.strip():
                    extracted_text = f"Document: {filename}\nNote: Scanned/image-based PDF with {pdf_res.get('total_pages', 1)} pages."
            else:
                txt_res = cls.extract_text_from_bytes(file_bytes, filename)
                extracted_text = txt_res["text"]
                doc_title = filename.rsplit(".", 1)[0].replace("_", " ").replace("-", " ").title() if filename else ""
        elif raw_text is not None:
            extracted_text = raw_text.strip()
            doc_title = ""
        else:
            raise ValueError("Either file_bytes or raw_text must be provided.")

        if not extracted_text.strip():
            raise ValueError("No readable text content found in the provided source material.")

        # Extract structured representations
        structured = cls.structure_content(extracted_text, fallback_title=doc_title)
        return structured

    @classmethod
    def structure_content(cls, text: str, fallback_title: str = "") -> Dict[str, Any]:
        """Analyzes text to extract sections, key concepts, process steps, and summary."""
        lines = [line.strip() for line in text.split("\n")]
        non_empty_lines = [l for l in lines if l]

        # Determine Title
        title = ""
        if non_empty_lines:
            first_line = non_empty_lines[0]
            if first_line.startswith("#"):
                title = first_line.lstrip("#").strip()
        if not title:
            title = fallback_title
        if not title and non_empty_lines:
            first_line = non_empty_lines[0]
            if len(first_line) < 80 and not first_line.endswith("."):
                title = first_line
            else:
                title = "Educational Concept Analysis"

        # Extract Sections
        sections: List[ExtractedSection] = []
        current_heading = "Overview"
        current_level = 1
        current_lines: List[str] = []
        subsections: List[str] = []

        for line in lines:
            if not line:
                continue
            
            # Check for Markdown Header or Capitalized Header
            is_md_header = line.startswith("#")
            is_cap_header = (len(line) < 60 and line.isupper() and len(line.split()) <= 6)
            is_numbered_sec = bool(re.match(r"^(?:Section\s+\d+|Chapter\s+\d+|\d+\.\d*)\s*[:\-]?\s+[A-Z]", line, re.IGNORECASE))
            
            if is_md_header or is_cap_header or is_numbered_sec:
                if current_lines:
                    sections.append(ExtractedSection(
                        heading=current_heading,
                        content="\n".join(current_lines),
                        level=current_level,
                        subsections=subsections
                    ))
                    current_lines = []
                    subsections = []
                
                if is_md_header:
                    hashes = len(line) - len(line.lstrip("#"))
                    current_level = min(hashes, 4)
                    current_heading = line.lstrip("#").strip()
                else:
                    current_level = 2
                    current_heading = line.strip()
            else:
                current_lines.append(line)
                if line.startswith(("- ", "* ", "1.", "2.", "3.", "4.", "5.", "• ")):
                    subsections.append(line.lstrip("-*• 0123456789.").strip())

        if current_lines:
            sections.append(ExtractedSection(
                heading=current_heading,
                content="\n".join(current_lines),
                level=current_level,
                subsections=subsections
            ))

        # Extract Process Steps
        process_steps = []
        for line in lines:
            # Match numbered steps or arrow sequences
            if re.match(r"^(?:Step\s+\d+|[0-9]+[\.\)])\s+", line, re.IGNORECASE):
                step_text = re.sub(r"^(?:Step\s+\d+|[0-9]+[\.\)])\s*[:\-]?\s*", "", line, flags=re.IGNORECASE).strip()
                if step_text and len(step_text) > 3:
                    process_steps.append(step_text)
            elif "->" in line or "→" in line or "==>" in line:
                tokens = re.split(r"\s*(?:->|→|==>)\s*", line)
                if len(tokens) >= 2:
                    for t in tokens:
                        if t.strip() and t.strip() not in process_steps:
                            process_steps.append(t.strip())

        # Extract Key Concepts
        key_concepts = cls._extract_key_concepts(text)

        # Generate Executive Summary
        summary = cls._generate_summary(text, title, key_concepts, sections)

        return {
            "title": title or "Concept Architecture",
            "summary": summary,
            "key_concepts": key_concepts,
            "processes": process_steps[:12],
            "extracted_sections": sections,
            "raw_text": text
        }

    @staticmethod
    def _extract_key_concepts(text: str) -> List[str]:
        """Extracts domain-specific computer science and engineering concepts."""
        known_concepts = [
            # OS Concepts
            "Virtual Memory", "Paging", "Page Table", "Page Fault", "Thrashing",
            "TLB", "Translation Lookaside Buffer", "Demand Paging", "Working Set Model",
            "Round Robin", "CPU Scheduling", "First-Come First-Served", "Shortest Job First",
            "Multilevel Feedback Queue", "Context Switch", "Process Control Block",
            "Deadlock", "Banker's Algorithm", "Resource Allocation Graph", "Mutual Exclusion",
            "Semaphore", "Mutex", "Race Condition", "Critical Section", "Dining Philosophers",
            "Inter-Process Communication", "Shared Memory", "Message Passing",
            # DBMS Concepts
            "B-Tree", "B+ Tree", "Indexing", "Binary Search", "Linear Scan", "Full Table Scan",
            "Buffer Pool", "Disk Page", "Disk I/O", "Block Size", "IOPS", "Cache Hit Ratio",
            "Two-Phase Locking", "2PL", "ACID Properties", "Atomicity", "Consistency", "Isolation", "Durability",
            "Write-Ahead Logging", "WAL", "Transaction Isolation", "Serializable", "Dirty Read",
            "Query Optimization", "Cost Model", "Hash Join", "Nested Loop Join", "Foreign Key",
            "Normalization", "First Normal Form", "BNCF", "Denormalization",
            # Distributed & Architecture Concepts
            "Client-Server", "Microservices", "Load Balancer", "Reverse Proxy", "Rate Limiting",
            "Message Queue", "Kafka", "Redis", "Pub/Sub", "CAP Theorem", "Consistent Hashing",
            "REST API", "WebSocket", "Telemetry", "Event-Driven Architecture", "State Machine"
        ]

        found = []
        text_lower = text.lower()
        
        # Check known dictionary first
        for concept in known_concepts:
            if re.search(r'\b' + re.escape(concept.lower()) + r'\b', text_lower):
                if concept not in found:
                    found.append(concept)

        # Extract capitalized multi-word technical terms
        cap_terms = re.findall(r'\b[A-Z][a-zA-Z0-9]+(?:\s+[A-Z][a-zA-Z0-9]+)+\b', text)
        for term in cap_terms:
            if len(term) > 3 and term not in found and len(found) < 15:
                if not any(skip in term.lower() for skip in ["chapter", "section", "figure", "table", "university", "author"]):
                    found.append(term)

        # Extract acronyms (2-6 capital letters)
        acronyms = re.findall(r'\b[A-Z]{2,6}\b', text)
        for acr in acronyms:
            if acr not in found and acr not in ["AND", "THE", "FOR", "NOT", "URL", "PDF", "HTTP"] and len(found) < 18:
                found.append(acr)

        return found[:12] if found else ["System Architecture", "Process Execution", "Resource Management"]

    @staticmethod
    def _generate_summary(text: str, title: str, concepts: List[str], sections: List[ExtractedSection]) -> str:
        """Generates a concise synthesized summary of the source material."""
        if not text:
            return "No content available."
            
        first_para = ""
        for s in sections:
            clean_content = s.content.strip()
            if len(clean_content) > 40:
                first_para = clean_content.split("\n\n")[0].replace("\n", " ").strip()
                break
                
        if len(first_para) > 280:
            first_para = first_para[:277] + "..."
            
        concept_str = ", ".join(concepts[:5]) if concepts else "core system workflows"
        if first_para:
            return f"Structured study on {title}. Explores {concept_str}. {first_para}"
        else:
            return f"Comprehensive technical breakdown of {title} focusing on {concept_str} and related procedural workflows."
