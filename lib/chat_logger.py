"""チャットログ記録（JSONL形式）"""

import json
from datetime import datetime, timezone
from pathlib import Path


LOG_DIR = Path("/tmp/chat_logs")
LOG_FILE = LOG_DIR / "chat_log.jsonl"


def log_chat(question: str, answer: str, sources: list[dict]) -> None:
    """チャットのQ&Aを1行JSONとして記録する。"""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "question": question,
        "answer": answer,
        "sources": [s.get("page_title", "") for s in sources],
    }
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def read_logs() -> list[dict]:
    """ログファイルを読み込み、エントリのリストを返す。"""
    if not LOG_FILE.exists():
        return []
    entries = []
    with open(LOG_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return entries


def get_log_stats() -> dict:
    """ログの統計情報を返す。"""
    entries = read_logs()
    if not entries:
        return {"total": 0, "oldest": None, "newest": None}
    return {
        "total": len(entries),
        "oldest": entries[0].get("timestamp"),
        "newest": entries[-1].get("timestamp"),
    }
