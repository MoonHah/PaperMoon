import logging
import re
from pathlib import Path

from app.core.config import settings

logger = logging.getLogger(__name__)

# 两个转换器分别懒加载缓存：默认（快，信任文本层）与强制全页 OCR（慢，绕过坏文本层）。
_converter = None
_ocr_converter = None

# docling 抽 PDF 文本层时，内嵌字体子集缺 ToUnicode 映射会退化成字形索引 /gidNNN。
# 典型表现：英文正常、中文（或特殊连字）变成一串 /gidNNN。这类坏文本层无法靠
# 换抽取器还原，唯一可靠修法是强制全页 OCR。
_GID_PATTERN = re.compile(r"/gid\d+")


def _build_pipeline_options(force_ocr: bool):
    from docling.datamodel.pipeline_options import PdfPipelineOptions, RapidOcrOptions

    opts = PdfPipelineOptions()
    # 关 TableFormer：省一份 HF 表格模型依赖（与既有 Docker 配置保持一致）。
    opts.do_table_structure = False
    if force_ocr:
        # 强制对每页位图 OCR，彻底忽略坏文本层。RapidOCR 用随 wheel 打包的
        # ch_PP-OCRv4（中英文通吃）ONNX 模型，离线可用、无需额外下载。
        opts.do_ocr = True
        opts.ocr_options = RapidOcrOptions(force_full_page_ocr=True)
    return opts


def _make_converter(force_ocr: bool):
    from docling.datamodel.base_models import InputFormat
    from docling.document_converter import DocumentConverter, PdfFormatOption

    return DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(
                pipeline_options=_build_pipeline_options(force_ocr)
            )
        }
    )


def _get_converter():
    global _converter
    if _converter is None:
        _converter = _make_converter(force_ocr=False)
    return _converter


def _get_ocr_converter():
    global _ocr_converter
    if _ocr_converter is None:
        _ocr_converter = _make_converter(force_ocr=True)
    return _ocr_converter


def _gid_garbage_ratio(text: str) -> float:
    """文本中 /gidNNN 字形索引占字符总数的比例（0~1）。0 表示无字形乱码。"""
    if not text:
        return 0.0
    gid_chars = sum(len(m) for m in _GID_PATTERN.findall(text))
    return gid_chars / len(text)


def _convert_pdf(file_path: Path, converter) -> str:
    return converter.convert(file_path).document.export_to_markdown()


def parse_document(file_path: Path) -> str:
    suffix = file_path.suffix
    if suffix in {".txt", ".md"}:
        return file_path.read_text(encoding="utf-8")

    if suffix != ".pdf":
        raise ValueError(f"Unsupported file type: {file_path.suffix}")

    try:
        text = _convert_pdf(file_path, _get_converter())
    except Exception as e:
        raise ValueError(f"Failed to parse PDF: {e}")

    # 文本层字形乱码超阈值 → 回退强制全页 OCR 重解析（慢，但能还原真实字符）。
    ratio = _gid_garbage_ratio(text)
    if settings.parse_ocr_gid_threshold > 0 and ratio > settings.parse_ocr_gid_threshold:
        logger.warning(
            "pdf 文本层字形乱码占比 %.1f%% 超阈值 %.1f%%，回退强制全页 OCR 重解析：%s",
            ratio * 100,
            settings.parse_ocr_gid_threshold * 100,
            file_path.name,
        )
        try:
            text = _convert_pdf(file_path, _get_ocr_converter())
        except Exception as e:
            raise ValueError(f"Failed to OCR-parse PDF: {e}")

    if not text.strip():
        raise ValueError("PDF has no extractable text (possibly scanned without OCR)")
    return text
