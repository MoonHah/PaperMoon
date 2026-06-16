"""一次性清理停滞文档（删除 DB 行 + storage 文件 + 幂等清向量）。

停滞 = 非终态（仍在 UPLOADED/PARSING/... 中）且 updated_at 超过阈值，通常是 worker 被
硬杀（容器重建 / OOM）遗留、永远落不到终态的记录。默认 dry-run，仅打印；--apply 才执行删除。

用法（建议在容器内跑，DB/Qdrant 地址已就绪）：
    docker compose exec api python scripts/cleanup_documents.py            # dry-run
    docker compose exec api python scripts/cleanup_documents.py --apply    # 执行删除
    docker compose exec api python scripts/cleanup_documents.py --max-age 600

也可从宿主机跑（需 .env 的 DATABASE_URL / QDRANT_URL 指向可达地址）。
"""

import argparse
import os
import sys
from pathlib import Path

# 绕过本地地址的系统代理（macOS Clash 等会把 localhost 也转发给代理 → 连接超时）。
os.environ.setdefault("NO_PROXY", "localhost,127.0.0.1")

# 让脚本能 import app.*（从项目根目录运行时生效）
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.config import settings
from app.core.database import SessionLocal
from app.services.document_reconcile import find_stuck_documents
from app.services.vector_store import get_vector_store


def main() -> None:
    parser = argparse.ArgumentParser(description="清理停滞（非终态超时）文档")
    parser.add_argument(
        "--apply", action="store_true", help="真正执行删除（默认 dry-run，只打印）"
    )
    parser.add_argument(
        "--max-age",
        type=int,
        default=settings.stuck_document_timeout,
        help=f"停滞阈值秒数（默认 {settings.stuck_document_timeout}，读 settings.stuck_document_timeout）",
    )
    args = parser.parse_args()

    db = SessionLocal()
    try:
        stuck = find_stuck_documents(db, args.max_age)
        if not stuck:
            print(f"没有停滞超过 {args.max_age}s 的文档，无需清理。")
            return

        print(f"发现 {len(stuck)} 条停滞文档（非终态且停滞 > {args.max_age}s）：")
        for d in stuck:
            print(
                f"  {d.document_id[:8]}  {d.status:<9} {d.filename}"
                f"  (updated_at={d.updated_at})"
            )

        if not args.apply:
            print("\n[dry-run] 未做任何删除。确认无误后加 --apply 执行。")
            return

        vector_store = get_vector_store(settings)
        storage_dir = Path(settings.storage_path)
        for d in stuck:
            # 幂等清向量（未到 INDEXING 的本就没有向量，删了也无妨）
            try:
                vector_store.delete_by_document_id(d.document_id)
            except Exception as e:
                print(f"  warn: 清向量失败 {d.document_id[:8]}: {e}")
            # 删 storage 文件
            (storage_dir / f"{d.document_id}{d.file_type}").unlink(missing_ok=True)
            # 删 DB 行
            db.delete(d)
        db.commit()
        print(f"\n已删除 {len(stuck)} 条停滞文档（DB 行 + storage 文件 + 向量）。")
    finally:
        db.close()


if __name__ == "__main__":
    main()
