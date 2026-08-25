"""일해라 김준태 - MCP 서버.

Claude Desktop 이 이 서버를 통해 플래너의 data.json 을 직접 읽고 쓴다.
FastAPI 서버와 같은 파일을 공유하되, 쓰기는 동일한 원자적 방식(temp->replace).
실행: Claude Desktop 설정에 등록 (stdio)
"""
from __future__ import annotations

import datetime
import json
import os
import tempfile
import time
from pathlib import Path

from mcp.server.fastmcp import FastMCP

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
DATA_FILE = DATA_DIR / "data.json"

mcp = FastMCP("ilhaera-kimjuntae")

CATS = ["업무", "공부", "개인", "운동"]


# ---------------------------------------------------------- storage
def load_db() -> dict:
    if not DATA_FILE.exists():
        return {"version": 2, "events": {}}
    return json.loads(DATA_FILE.read_text(encoding="utf-8"))


def save_db(db: dict) -> None:
    DATA_DIR.mkdir(exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=DATA_DIR, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(db, f, ensure_ascii=False, indent=2)
        os.replace(tmp, DATA_FILE)
    except OSError:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def _today() -> str:
    return datetime.date.today().strftime("%Y-%m-%d")


# ---------------------------------------------------------- tools
@mcp.tool()
def list_events(date: str = "") -> str:
    """특정 날짜의 일정 목록. date 비우면 오늘. 형식 YYYY-MM-DD."""
    d = date or _today()
    day = load_db()["events"].get(d, [])
    if not day:
        return f"{d}: 일정 없음. 일해라 김준태."
    lines = [f"{d} 일정 {len(day)}건:"]
    for ev in sorted(day, key=lambda e: e["start"]):
        mark = "[완료]" if ev["done"] else "[미완]"
        post = f" ({ev['postponeCount']}회 밀림)" if ev.get("postponeCount") else ""
        lines.append(
            f"- {mark} {ev['start']}~{ev['end']} [{ev['category']}] "
            f"{ev['title']} (id={ev['id']}){post}"
        )
    return "\n".join(lines)


@mcp.tool()
def add_event(title: str, start: str, end: str,
              category: str = "업무", date: str = "") -> str:
    """일정 추가. start/end 는 HH:MM, date 비우면 오늘.
    category: 업무/공부/개인/운동 중 하나."""
    if category not in CATS:
        return f"category 는 {CATS} 중 하나여야 한다."
    if end <= start:
        return "종료 시각이 시작 시각보다 빨라요."
    d = date or _today()
    db = load_db()
    item = {
        "id": f"{int(time.time() * 1000):x}",
        "title": title, "start": start, "end": end,
        "category": category, "done": False,
        "notified": False, "postponedFrom": None, "postponeCount": 0,
    }
    db["events"].setdefault(d, []).append(item)
    save_db(db)
    return f"추가됨: {d} {start}~{end} [{category}] {title} (id={item['id']})"


@mcp.tool()
def complete_event(event_id: str, date: str = "") -> str:
    """일정 완료 처리. date 비우면 오늘에서 찾는다."""
    d = date or _today()
    db = load_db()
    for ev in db["events"].get(d, []):
        if ev["id"] == event_id:
            ev["done"] = True
            save_db(db)
            return f"완료: {ev['title']}. 잘했다 김준태."
    return f"{d} 에서 id={event_id} 못 찾음. list_events 로 확인해라."


@mcp.tool()
def postpone_event(event_id: str, from_date: str, to_date: str = "") -> str:
    """일정을 다른 날로 미룬다. to_date 비우면 오늘로."""
    to = to_date or _today()
    db = load_db()
    day = db["events"].get(from_date, [])
    target = next((e for e in day if e["id"] == event_id), None)
    if target is None:
        return f"{from_date} 에서 id={event_id} 못 찾음."
    day.remove(target)
    target["postponedFrom"] = target.get("postponedFrom") or from_date
    target["postponeCount"] = target.get("postponeCount", 0) + 1
    target["notified"] = False          # 새 날짜에서 다시 알림 대상
    db["events"].setdefault(to, []).append(target)
    if not db["events"][from_date]:
        del db["events"][from_date]
    save_db(db)
    return (f"미룸: {target['title']} -> {to} "
            f"(누적 {target['postponeCount']}회. 이번엔 해라.)")


@mcp.tool()
def delete_event(event_id: str, date: str) -> str:
    """일정 삭제."""
    db = load_db()
    day = db["events"].get(date, [])
    before = len(day)
    db["events"][date] = [e for e in day if e["id"] != event_id]
    if len(db["events"][date]) == before:
        return f"{date} 에서 id={event_id} 못 찾음."
    if not db["events"][date]:
        del db["events"][date]
    save_db(db)
    return "삭제됨."


@mcp.tool()
def backlog() -> str:
    """오늘 이전의 미완 일정(밀린 일) 전체 목록."""
    today = _today()
    db = load_db()
    out = []
    for d in sorted(db["events"].keys()):
        if d >= today:
            continue
        for ev in db["events"][d]:
            if not ev["done"]:
                out.append(f"- {d} {ev['start']} [{ev['category']}] "
                           f"{ev['title']} (id={ev['id']})")
    if not out:
        return "밀린 일 없음. 깨끗하다."
    return f"밀린 일 {len(out)}건:\n" + "\n".join(out)


@mcp.tool()
def now() -> str:
    """현재 날짜/시각/요일. '내일', '지금부터' 같은 상대 시간을 계산하기 전에 반드시 먼저 호출할 것."""
    n = datetime.datetime.now()
    weekdays = ["월", "화", "수", "목", "금", "토", "일"]
    return f"지금은 {n.strftime('%Y-%m-%d %H:%M')} ({weekdays[n.weekday()]}요일)"


if __name__ == "__main__":
    mcp.run()
