from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

class SourceUploadRequest(BaseModel):
    title: Optional[str] = Field(None, description="Optional title or topic name")
    raw_text: Optional[str] = Field(None, description="Raw text notes or document markdown")
    focus_topic: Optional[str] = Field(None, description="Target concept or focus sub-topic")

class ExtractedSection(BaseModel):
    heading: str
    content: str
    level: int = 1
    subsections: List[str] = Field(default_factory=list)

class DiagramResponse(BaseModel):
    mermaid_syntax: str = Field(..., description="Valid Mermaid.js diagram definition")
    summary: str = Field(..., description="Summary of the diagram workflow")
    nodes_breakdown: List[str] = Field(default_factory=list, description="Key steps or node explanations")
    diagram_type: str = Field("flowchart", description="Mermaid diagram type (flowchart, sequence, state, class)")

class VideoReference(BaseModel):
    title: str = Field(..., description="Suggested or verified video tutorial title")
    topic: str = Field(..., description="Key concept or topic name")
    channel: Optional[str] = Field(None, description="Authoritative channel or creator recommendation")
    url: Optional[str] = Field(None, description="Direct YouTube watch or search URL")
    embed_url: Optional[str] = Field(None, description="Embeddable YouTube preview URL")
    search_query: str = Field(..., description="High-signal search query for discovery")
    description: str = Field(..., description="Description of concepts covered in the video")
    timestamp_notes: Optional[str] = Field(None, description="Key conceptual timestamp guide")

class MaterialAnalysisResponse(BaseModel):
    title: str
    summary: str
    key_concepts: List[str] = Field(default_factory=list)
    processes: List[str] = Field(default_factory=list)
    diagram: DiagramResponse
    video_references: List[VideoReference] = Field(default_factory=list)
    extracted_sections: List[ExtractedSection] = Field(default_factory=list)
