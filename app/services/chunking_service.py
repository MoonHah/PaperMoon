

def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    if not text.strip():
        return []   #  None和空字符串返回[]
    
    start = 0
    end = 0
    chunk_list = []

    while start < len(text):
        end = min(start + chunk_size, len(text))  # 防止越界
        chunk = text[start: end].strip()  # 只会输出字符串, 空文本时返回""
        if chunk:
            chunk_list.append(chunk)
        if end >= len(text):
            break
        start = end - overlap
    
    return chunk_list
