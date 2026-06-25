from langchain_text_splitters import RecursiveCharacterTextSplitter

# 递归分隔符（按序尝试，尽量在自然边界处切，切不开才退到下一级，最后才按字符兜底）：
# 段落 → 行 → 中文句末 → 英文句末 → 空格 → 字符。
# 关键：中文无空格，朴素定长切会从句子/词中间断开；显式加入中文句末标点 。！？；让中文也按句切。
_SEPARATORS = ["\n\n", "\n", "。", "！", "？", "；", ". ", "! ", "? ", "; ", " ", ""]


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    """把正文切成带重叠的块，尽量在自然边界（段落/句子）处切，避免切断句子或表格行。

    签名保持不变（text, chunk_size, overlap）：worker 索引与「分块」检查页确定性复用同一函数，
    二者切出的块完全一致。chunk_size/overlap 仍按字符计（length_function=len）。
    """
    if not text.strip():
        return []   # None / 空字符串 / 纯空白 → []
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=overlap,
        separators=_SEPARATORS,
        length_function=len,
        keep_separator="end",   # 分隔符留在前一块末尾（句末标点跟着句子，不漂到下一块开头）
    )
    return [c for c in (s.strip() for s in splitter.split_text(text)) if c]
