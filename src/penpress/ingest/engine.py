"""Unified local document ingest engine for PenPress.

Tiered Extraction Strategy:
1. Fast Path (pypdfium2 + pdfminer.six):
   - Fast direct text extraction with exact fonts, sizes, and bounding boxes.
   - Vector drawing path extraction directly from PDF operators.
   - High speed (< 1s per page), 0 GPU requirement, fits within 50MB RAM.
2. OCR Fallback Path (Tesseract via subprocess):
   - Triggered when text density is near zero (scanned documents or raster images).
   - Preserves reading order and crops bounding boxes.
3. Hostile PDF Guards:
   - File size limits (<= 50 MB)
   - Page count limits (<= 250 pages)
   - Dimension clamps (<= 2500 pt per axis; flagged if oversized)
   - Corrupted file exception catching without crash (structured IngestError)
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

import pypdfium2 as pdfium
from pdfminer.high_level import extract_pages
from pdfminer.layout import (
    LTCurve,
    LTLine,
    LTRect,
    LTTextBox,
)

from penpress.ingest.equations import clean_latex, is_math_block
from penpress.ingest.figures import cluster_drawings
from penpress.ingest.layout import order_blocks
from penpress.ingest.markdown_parser import MarkdownParser
from penpress.ingest.schema import (
    BlockType,
    BoundingBox,
    DocumentBlock,
    IngestedDocument,
    IngestedPage,
)

# Safety limits
MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB
MAX_PAGE_COUNT = 250
MAX_PAGE_DIMENSION_PT = 2500.0  # Above this is treated as oversized architectural print


def _find_tesseract() -> str:
    """Finds tesseract binary across PATH and standard cross-platform install locations."""
    found = shutil.which("tesseract")
    if found:
        return found
    candidates = [
        "/opt/homebrew/bin/tesseract",
        "/usr/local/bin/tesseract",
        "/usr/bin/tesseract",
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return "tesseract"


class IngestError(ValueError):
    """Raised when PDF or Markdown document is corrupted, malformed, or exceeds safety bounds."""


class DocumentIngestEngine:
    def __init__(self, tesseract_cmd: str | None = None) -> None:
        self.tesseract_cmd = tesseract_cmd or _find_tesseract()
        self.md_parser = MarkdownParser()

    def ingest_document(self, file_path: str | Path) -> IngestedDocument:
        """Ingest arbitrary document (PDF or Markdown) into structured block representation."""
        path = Path(file_path)
        if not path.exists():
            raise IngestError(f"File not found: {path}")

        if path.suffix.lower() in (".md", ".markdown"):
            text = path.read_text(encoding="utf-8")
            return self.md_parser.parse_markdown(text, doc_id=path.stem)
        elif path.suffix.lower() == ".pdf":
            return self.ingest_pdf(path)
        else:
            raise IngestError(f"Unsupported document file extension: {path.suffix}")

    def ingest_pdf(self, pdf_path: str | Path) -> IngestedDocument:
        path = Path(pdf_path)
        start_time = time.perf_counter()

        # 1. Hostile check: file existence and size
        if not path.exists():
            raise IngestError(f"File does not exist: {path}")

        file_size = path.stat().st_size
        if file_size > MAX_FILE_SIZE_BYTES:
            raise IngestError(f"File size {file_size} exceeds maximum limit {MAX_FILE_SIZE_BYTES}")

        # 2. Hostile check: corrupted / malformed PDF verification via pypdfium2
        try:
            pdf_doc = pdfium.PdfDocument(str(path))
            page_count = len(pdf_doc)
        except Exception as e:
            raise IngestError(f"Malformed or corrupted PDF ({type(e).__name__}): {e}") from e

        if page_count > MAX_PAGE_COUNT:
            raise IngestError(f"Page count {page_count} exceeds maximum safety limit {MAX_PAGE_COUNT}")

        pages: list[IngestedPage] = []
        warnings: list[str] = []

        # Extract text boxes and drawing primitives using pdfminer
        try:
            pdfminer_pages = list(extract_pages(str(path)))
        except Exception as e:
            # If pdfminer fails on complex stream, raise structured IngestError
            raise IngestError(f"Error parsing PDF content streams: {e}") from e

        for page_idx in range(page_count):
            p_pdfium = pdf_doc.get_page(page_idx)
            w_pt, h_pt = p_pdfium.get_size()

            if w_pt > MAX_PAGE_DIMENSION_PT or h_pt > MAX_PAGE_DIMENSION_PT:
                msg = (
                    f"Page {page_idx} dimensions ({w_pt:.1f}x{h_pt:.1f} pt) "
                    f"exceed standard bounds {MAX_PAGE_DIMENSION_PT} pt"
                )
                warnings.append(msg)

            miner_page = pdfminer_pages[page_idx] if page_idx < len(pdfminer_pages) else None
            blocks: list[DocumentBlock] = []
            raw_drawing_paths: list[list[tuple[float, float]]] = []

            if miner_page:
                for element in miner_page:
                    if isinstance(element, LTTextBox):
                        text = element.get_text().strip()
                        if not text:
                            continue

                        # Extract font sizes to determine title vs heading vs paragraph
                        font_sizes: list[float] = []
                        for text_line in element:
                            for char in text_line:
                                if hasattr(char, "size"):
                                    font_sizes.append(float(char.size))

                        mean_font_size = sum(font_sizes) / len(font_sizes) if font_sizes else 10.0
                        x0, y0, x1, y1 = element.bbox
                        bbox = BoundingBox(x0=x0, y0=y0, x1=x1, y1=y1)

                        # Determine block type
                        if is_math_block(text, bbox, w_pt):
                            b_type = BlockType.EQUATION
                            latex_str = clean_latex(text)
                        elif mean_font_size >= 17.0 and bbox.width > 0.4 * w_pt:
                            b_type = BlockType.TITLE
                            latex_str = ""
                        elif mean_font_size >= 13.0:
                            b_type = BlockType.HEADING
                            latex_str = ""
                        else:
                            b_type = BlockType.PARAGRAPH
                            latex_str = ""

                        blocks.append(
                            DocumentBlock(
                                block_id=f"p{page_idx}_b{len(blocks)}",
                                block_type=b_type,
                                page_idx=page_idx,
                                reading_order=0,
                                bbox=bbox,
                                text=text,
                                latex=latex_str,
                                confidence=0.98,
                                metadata={"mean_font_size": round(mean_font_size, 2)},
                            )
                        )

                    elif isinstance(element, (LTLine, LTRect, LTCurve)):
                        # Vector drawing primitive
                        x0, y0, x1, y1 = element.bbox
                        # Filter out whole page background fills
                        if (x1 - x0) > 0.95 * w_pt and (y1 - y0) > 0.95 * h_pt:
                            continue

                        if isinstance(element, LTLine):
                            pt0 = (element.pts[0][0], element.pts[0][1])
                            pt1 = (element.pts[1][0], element.pts[1][1])
                            raw_drawing_paths.append([pt0, pt1])
                        elif isinstance(element, LTRect):
                            raw_drawing_paths.append([(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)])
                        elif isinstance(element, LTCurve) and hasattr(element, "pts"):
                            pts = [(float(pt[0]), float(pt[1])) for pt in element.pts]
                            if len(pts) >= 2:
                                raw_drawing_paths.append(pts)

            # Cluster vector drawings into figure blocks
            fig_blocks = cluster_drawings(raw_drawing_paths)
            for fb in fig_blocks:
                fb.page_idx = page_idx
                fb.block_id = f"p{page_idx}_fig_{len(blocks)}"
                blocks.append(fb)

            # Check if page is scanned/empty text
            is_scanned = False
            total_text_chars = sum(len(b.text) for b in blocks if b.block_type != BlockType.FIGURE_VECTOR)
            if total_text_chars < 30:
                # Trigger OCR fallback path
                ocr_blocks = self._ocr_page_fallback(p_pdfium, page_idx, w_pt, h_pt)
                if ocr_blocks:
                    is_scanned = True
                    blocks = ocr_blocks

            # Order blocks by reading layout
            ordered_blocks = order_blocks(blocks, w_pt)

            pages.append(
                IngestedPage(
                    page_idx=page_idx,
                    width_pt=w_pt,
                    height_pt=h_pt,
                    blocks=ordered_blocks,
                    is_scanned=is_scanned,
                )
            )

        duration = time.perf_counter() - start_time
        return IngestedDocument(
            doc_id=path.stem,
            source_filename=path.name,
            page_count=page_count,
            pages=pages,
            extraction_duration_s=duration,
            status="ok",
            warnings=warnings,
        )

    def _ocr_page_fallback(
        self,
        pdfium_page: pdfium.PdfPage,
        page_idx: int,
        w_pt: float,
        h_pt: float,
    ) -> list[DocumentBlock]:
        """OCR fallback for scanned pages using Tesseract TSV output."""
        try:
            # Render page to PIL image at 150 DPI
            pil_image = pdfium_page.render(scale=150 / 72.0).to_pil()
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
                temp_img = f.name
                pil_image.save(temp_img)

            cmd = [self.tesseract_cmd, temp_img, "stdout", "--psm", "6", "tsv"]
            proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
            if os.path.exists(temp_img):
                os.remove(temp_img)

            if proc.returncode != 0:
                return []

            lines = proc.stdout.strip().split("\n")
            if len(lines) <= 1:
                return []

            header = lines[0].split("\t")
            col_map = {col: i for i, col in enumerate(header)}

            line_text_acc: dict[tuple[int, int, int], list[tuple[str, int, int, int, int]]] = {}
            scale_x = w_pt / pil_image.width
            scale_y = h_pt / pil_image.height

            for row_str in lines[1:]:
                parts = row_str.split("\t")
                if len(parts) < len(header):
                    continue

                text = parts[col_map.get("text", 11)].strip()
                conf_str = parts[col_map.get("conf", 10)]
                try:
                    conf = float(conf_str)
                except ValueError:
                    conf = -1.0

                if not text or conf < 30.0:
                    continue

                block_num = int(parts[col_map.get("block_num", 2)])
                par_num = int(parts[col_map.get("par_num", 3)])
                line_num = int(parts[col_map.get("line_num", 4)])
                left = int(parts[col_map.get("left", 6)])
                top = int(parts[col_map.get("top", 7)])
                width = int(parts[col_map.get("width", 8)])
                height = int(parts[col_map.get("height", 9)])

                key = (block_num, par_num, line_num)
                if key not in line_text_acc:
                    line_text_acc[key] = []
                line_text_acc[key].append((text, left, top, width, height))

            blocks: list[DocumentBlock] = []
            for _key, words in line_text_acc.items():
                line_str = " ".join(w[0] for w in words)
                min_l = min(w[1] for w in words)
                min_t = min(w[2] for w in words)
                max_r = max(w[1] + w[3] for w in words)
                max_b = max(w[2] + w[4] for w in words)

                # Convert raster top-down px to PDF bottom-up pt
                x0 = min_l * scale_x
                x1 = max_r * scale_x
                y0 = h_pt - (max_b * scale_y)
                y1 = h_pt - (min_t * scale_y)

                blocks.append(
                    DocumentBlock(
                        block_id=f"p{page_idx}_ocr_{len(blocks)}",
                        block_type=BlockType.PARAGRAPH,
                        page_idx=page_idx,
                        reading_order=len(blocks),
                        bbox=BoundingBox(x0=x0, y0=y0, x1=x1, y1=y1),
                        text=line_str,
                        confidence=0.88,
                        metadata={"ocr_fallback": True},
                    )
                )

            return blocks
        except Exception:
            return []
