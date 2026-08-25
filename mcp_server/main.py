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


# ---------------------------------------------------------- routines
import uuid as _uuid

_DAYMAP = {"월": 0, "화": 1, "수": 2, "목": 3, "금": 4, "토": 5, "일": 6}


def _materialize_routines(db):
    routines = db.get("routines", [])
    if not routines:
        return False
    changed = False
    today = datetime.date.today()
    for off in range(-7, 31):
        d = today + datetime.timedelta(days=off)
        ds = d.isoformat()
        existing = {e.get("routineId") for e in db["events"].get(ds, [])}
        for r in routines:
            if ds < r.get("created", "9999-12-31"):
                continue
            if d.weekday() in r.get("days", []) and r["id"] not in existing:
                db["events"].setdefault(ds, []).append({
                    "id": _uuid.uuid4().hex[:12],
                    "title": r["title"], "start": r["start"], "end": r["end"],
                    "category": r.get("category", "개인"),
                    "done": False, "notified": False,
                    "postponedFrom": None, "postponeCount": 0,
                    "routineId": r["id"],
                })
                changed = True
    return changed


_orig_load_db = load_db


def load_db():
    db = _orig_load_db()
    if _materialize_routines(db):
        save_db(db)
    return db


@mcp.tool()
def add_routine(title: str, start: str, end: str, days: str,
                category: str = "개인") -> str:
    """고정 루틴 등록. 매주 같은 요일/시간에 일정이 자동 생성된다.
    days: "평일" / "주말" / "매일" 또는 쉼표 요일 "월,수,금". 시각은 HH:MM."""
    if category not in CATS:
        return f"category 는 {CATS} 중 하나여야 한다."
    if end <= start:
        return "종료가 시작보다 빨라요."
    days = days.strip()
    if days == "매일":
        nums = [0, 1, 2, 3, 4, 5, 6]
    elif days == "평일":
        nums = [0, 1, 2, 3, 4]
    elif days == "주말":
        nums = [5, 6]
    else:
        try:
            nums = sorted({_DAYMAP[x.strip()] for x in days.split(",")})
        except KeyError:
            return "요일은 월~일 한 글자 쉼표 구분. 예: 월,수,금"
    db = load_db()
    r = {"id": _uuid.uuid4().hex[:12], "title": title, "start": start,
         "end": end, "category": category, "days": nums,
         "created": datetime.date.today().isoformat()}
    db.setdefault("routines", []).append(r)
    _materialize_routines(db)
    save_db(db)
    names = "".join(k for k, v in sorted(_DAYMAP.items(), key=lambda kv: kv[1]) if v in nums)
    return f"루틴 등록: [{category}] {title} {start}~{end} ({names}). 앞으로 자동 생성된다. id={r['id']}"


@mcp.tool()
def list_routines() -> str:
    """등록된 고정 루틴 목록."""
    rs = load_db().get("routines", [])
    if not rs:
        return "루틴 없음."
    lines = [f"루틴 {len(rs)}건:"]
    for r in rs:
        names = "".join(k for k, v in sorted(_DAYMAP.items(), key=lambda kv: kv[1]) if v in r["days"])
        lines.append(f"- [{r['category']}] {r['title']} {r['start']}~{r['end']} ({names}) id={r['id']}")
    return "\n".join(lines)


@mcp.tool()
def delete_routine(routine_id: str) -> str:
    """루틴 삭제. 오늘 이후 미완 인스턴스도 제거, 과거 기록은 보존."""
    db = load_db()
    before = len(db.get("routines", []))
    db["routines"] = [r for r in db.get("routines", []) if r["id"] != routine_id]
    if len(db["routines"]) == before:
        return f"id={routine_id} 루틴 못 찾음. list_routines 로 확인."
    today = _today()
    for ds in list(db["events"].keys()):
        if ds >= today:
            db["events"][ds] = [e for e in db["events"][ds]
                                if not (e.get("routineId") == routine_id and not e["done"])]
            if not db["events"][ds]:
                del db["events"][ds]
    save_db(db)
    return "루틴 삭제됨. 과거 기록은 보존."


if __name__ == "__main__":
    mcp.run()
