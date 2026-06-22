"""PDF 解析：/gidNNN 字形乱码检测 + 超阈值回退强制 OCR 的编排逻辑。

真实 OCR 不在单测里跑（慢、依赖位图模型）；这里 mock 掉 docling 转换，
只验证「检测 → 是否回退」的决策与产物选择是否正确。
"""

from pathlib import Path

import pytest

from app.core.config import settings
from app.services import document_parser


# ── 检测函数（纯函数，确定性）─────────────────────────────────────────────

def test_gid_ratio_empty():
    assert document_parser._gid_garbage_ratio("") == 0.0


def test_gid_ratio_clean_text():
    assert document_parser._gid_garbage_ratio("Rerank RAG retrieve generation") == 0.0


def test_gid_ratio_counts_glyph_chars():
    # "/gid396" = 7 字符；总长 14 → 比例 0.5
    text = "ab/gid396/gid0"  # 'ab' + '/gid396'(7) + '/gid0'(5) = 14 chars, gid=12
    ratio = document_parser._gid_garbage_ratio(text)
    assert abs(ratio - 12 / 14) < 1e-9


# ── parse_document 回退编排（mock docling）────────────────────────────────

def _mk_pdf(tmp_path: Path) -> Path:
    pdf = tmp_path / "x.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")  # 内容无关，_convert_pdf 已被 mock
    return pdf


def test_falls_back_to_ocr_when_gid_exceeds_threshold(tmp_path, monkeypatch):
    pdf = _mk_pdf(tmp_path)
    default_conv, ocr_conv = object(), object()
    monkeypatch.setattr(document_parser, "_get_converter", lambda: default_conv)
    monkeypatch.setattr(document_parser, "_get_ocr_converter", lambda: ocr_conv)
    monkeypatch.setattr(settings, "parse_ocr_gid_threshold", 0.02)

    def fake_convert(_path, converter):
        # 默认转换器吐字形乱码（高占比），OCR 转换器吐干净文本
        return "/gid1" * 100 if converter is default_conv else "重排 RAG 检索 生成"

    monkeypatch.setattr(document_parser, "_convert_pdf", fake_convert)

    assert document_parser.parse_document(pdf) == "重排 RAG 检索 生成"


def test_no_ocr_when_text_layer_clean(tmp_path, monkeypatch):
    pdf = _mk_pdf(tmp_path)
    monkeypatch.setattr(document_parser, "_get_converter", lambda: object())
    monkeypatch.setattr(settings, "parse_ocr_gid_threshold", 0.02)

    def _boom():
        raise AssertionError("文本层干净时不应触发 OCR 回退")

    monkeypatch.setattr(document_parser, "_get_ocr_converter", _boom)
    monkeypatch.setattr(
        document_parser, "_convert_pdf", lambda _p, _c: "clean english text only"
    )

    assert document_parser.parse_document(pdf) == "clean english text only"


def test_threshold_zero_disables_fallback(tmp_path, monkeypatch):
    # 阈值设 0 表示禁用回退：即便满是乱码也不 OCR（用于应急关闭）。
    pdf = _mk_pdf(tmp_path)
    monkeypatch.setattr(document_parser, "_get_converter", lambda: object())
    monkeypatch.setattr(settings, "parse_ocr_gid_threshold", 0.0)

    def _boom():
        raise AssertionError("阈值为 0 时不应触发 OCR 回退")

    monkeypatch.setattr(document_parser, "_get_ocr_converter", _boom)
    monkeypatch.setattr(document_parser, "_convert_pdf", lambda _p, _c: "/gid9" * 50)

    assert document_parser.parse_document(pdf) == "/gid9" * 50
