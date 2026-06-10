from pathlib import Path

_converter = None


def _get_converter():
    global _converter
    if _converter is None:
        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.pipeline_options import PdfPipelineOptions
        from docling.document_converter import DocumentConverter, PdfFormatOption

        pipeline_options = PdfPipelineOptions()
        pipeline_options.do_table_structure = False  # avoids cv2/libGL system deps in Docker

        _converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
            }
        )
    return _converter


def parse_document(file_path: Path) -> str:
    suffix = file_path.suffix
    if suffix in {".txt", ".md"}:
        return file_path.read_text(encoding="utf-8")

    elif suffix == ".pdf":
        try:
            converter = _get_converter()
            result = converter.convert(file_path)
            text = result.document.export_to_markdown()
        except Exception as e:
            raise ValueError(f"Failed to parse PDF: {e}")
        if not text.strip():
            raise ValueError("PDF has no extractable text (possibly scanned without OCR)")
        return text

    else:
        raise ValueError(f"Unsupported file type: {file_path.suffix}")