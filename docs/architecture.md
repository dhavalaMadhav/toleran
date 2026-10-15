# Engineering Drawing Intelligence & Design Compliance Copilot Architecture

## System Overview

The **Engineering Drawing Intelligence & Design Compliance Copilot** is a specialized decision-support platform designed for mechanical engineers, quality assurance managers, and CAD drafters. It automates the extraction, normalization, geometric association, and technical compliance validation of engineering drawings against contractual engineering specifications.

---

## End-to-End Data Flow Architecture (Mermaid)

```mermaid
flowchart TD
    subgraph Ingestion["1. Document Ingestion & Storage"]
        Upload[User Upload: PDF / DXF / PNG / JPEG]
        SHA256[Compute SHA-256 Checksum & Safe Path]
        Storage[Deduplicated Local File Storage]
        DocRecord[(Document & Job DB Records)]
        Upload --> SHA256 --> Storage --> DocRecord
    end

    subgraph Preprocessing["2. Preprocessing & Rendering"]
        Classify{PDF / CAD / Raster?}
        DocRecord --> Classify
        Classify -->|Vector PDF| PDFService[PyMuPDF: Extract Native Text & Vector Paths]
        Classify -->|DXF CAD| CADService[ezdxf: Extract LINE, CIRCLE, ARC, TEXT]
        Classify -->|Raster Image| Preproc[OpenCV: Grayscale, CLAHE, Deskew]
        PDFService --> HighDPIRender[High-DPI Raster Page Render]
        Preproc --> HighDPIRender
    end

    subgraph Extraction["3. Computer Vision & OCR Extraction"]
        HighDPIRender --> RapidOCR[RapidOCR: ONNX PaddleOCR Text Detection]
        HighDPIRender --> Geometry[DrawingGeometryService: Hough Circles & Lines]
        RapidOCR --> RawBoxes[Text Boxes with Normalized BBoxes]
        Geometry --> Features[Geometric Feature Records: Circles, Lines, Slots]
    end

    subgraph Parsing["4. Dimension Parsing & Normalization"]
        RawBoxes --> DimParser[DimensionParser: Deterministic Decimal Engine]
        DimParser --> NormalizedDims[Normalized Dimensions: Nominal, Deviations, [Min, Max], Type]
        NormalizedDims --> AmbiguityCheck{Ambiguous / Low Confidence?}
        AmbiguityCheck -->|Yes & VLM Enabled| VLM[Vision-Language Model: Targeted Crop Inspection]
        AmbiguityCheck -->|Yes & Local| RouteReview[Flag: Pending Human Review]
        AmbiguityCheck -->|No| AutoAccept[Verification Status: Auto-Accepted]
        VLM --> NormalizedDims
    end

    subgraph Association["5. Feature Association"]
        NormalizedDims & Features --> FeatureAssoc[FeatureAssociationService: Proximity, Type Affinity, Direction]
        FeatureAssoc --> Associations[Annotation-Feature Links & Ambiguity Detection]
    end

    subgraph Compliance["6. Specification Retrieval & Compliance Engine"]
        SpecUpload[Technical Specification PDF / Text] --> SpecParser[SpecificationService: Clause & Tolerance Limits]
        SpecParser --> SpecReqs[(Specification Requirements)]
        NormalizedDims & SpecReqs --> Retrieval[RetrievalService: Hybrid Structured & Semantic Retrieval]
        Retrieval --> ComplianceEngine[ComplianceEngine: Deterministic Interval Containment]
        ComplianceEngine --> Findings[(Compliance Findings: Pass / Fail / Needs Review)]
    end

    subgraph HumanReview["7. Human Verification & Audit"]
        RouteReview & Findings --> ReviewQueue[Review Queue: Approve / Correct / Waive]
        ReviewQueue --> ReviewDecisions[(Audit Log: Review Decisions & Timestamps)]
    end

    subgraph Presentation["8. Presentation & Delivery"]
        Viewer[Two-Panel Interactive Drawing Viewer: SVG/Canvas Overlays & Zoom/Pan]
        Copilot[Engineering Copilot: Grounded RAG with Document Citations]
        Reports[ReportService: Formal PDF & CSV Exports]
        
        NormalizedDims & Associations --> Viewer
        Findings --> Viewer
        SpecReqs & Findings & NormalizedDims --> Copilot
        Findings & NormalizedDims --> Reports
    end
```

---

## Architectural Principles & Separation of Responsibilities

1. **Deterministic Rule Authority**:
   - The LLM / VLM is **never** the final authority for numeric tolerance decisions.
   - All tolerance comparisons and interval containment calculations are performed in pure Python using `Decimal` arithmetic to guarantee zero floating-point precision loss.

2. **Grounded AI Copilot**:
   - The Copilot operates strictly on retrieved database records (annotations, findings, requirements, and decisions).
   - If an assertion cannot be cited with an exact page number and bounding box coordinates, it explicitly reports that the evidence is unavailable in the uploaded documents.

3. **Coordinate System Unification**:
   - Coordinates are maintained in a canonical normalized format `[0.0, 1.0]` relative to page dimensions `(x0, y0, x1, y1)`.
   - The interactive viewer maps normalized coordinates to viewport scale/pan dynamically via SVG elements.

4. **Human-in-the-Loop Safeguards**:
   - Ambiguous callouts or multiple candidate feature associations are never presented with false certainty; they are marked `needs_review` and routed to the engineer's review queue.
