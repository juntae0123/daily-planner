"""일해라 김준태 - 로컬 서버.

역할: data/data.json 의 단일 소유자. 프론트와 (나중에) MCP 서버가
전부 이 파일을 보게 하기 위해 저장을 앱 밖(JSON 파일)으로 뺐다.
쓰기는 원자적(temp -> replace): 동시 접근 시 반파일 방지.
실행: bash run.sh
"""
from __future__ import annotations

import json
import os
import tempfile
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
DATA_FILE = DATA_DIR / "data.json"
STATIC_DIR = ROOT / "app" / "static"

app = FastAPI(title="ilhaera-kimjuntae")


# ---------------------------------------------------------- storage
def _empty() -> dict:
    return {"version": 2, "events": {}}


def load_db() -> dict:
    if not DATA_FILE.exists():
        return _empty()
    try:
        return json.loads(DATA_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        # 깨진 파일은 덮지 않고 보존한다
        DATA_FILE.replace(DATA_FILE.with_suffix(".broken.json"))
        return _empty()


def save_db(db: dict) -> None:
    """temp 에 쓰고 rename - 도중 크래시에도 반파일 없음."""
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


# ---------------------------------------------------------- models
class EventIn(BaseModel):
    title: str
    start: str          # "HH:MM"
    end: str
    category: str
    date: str           # "YYYY-MM-DD"


class EventPatch(BaseModel):
    title: str | None = None
    start: str | None = None
    end: str | None = None
    category: str | None = None
    done: bool | None = None
    date: str | None = None    # 날짜 이동(미루기)용


# ---------------------------------------------------------- api
@app.get("/api/events")
def get_events():
    return load_db()


@app.post("/api/events", status_code=201)
def create_event(ev: EventIn):
    db = load_db()
    item = {
        "id": f"{int(time.time() * 1000):x}",
        "title": ev.title, "start": ev.start, "end": ev.end,
        "category": ev.category, "done": False,
        "notified": False, "postponedFrom": None, "postponeCount": 0,
    }
    db["events"].setdefault(ev.date, []).append(item)
    save_db(db)
    return item


@app.patch("/api/events/{date}/{event_id}")
def update_event(date: str, event_id: str, patch: EventPatch):
    db = load_db()
    day = db["events"].get(date, [])
    target = next((e for e in day if e["id"] == event_id), None)
    if target is None:
        raise HTTPException(404, "event not found")

    p = patch.model_dump(exclude_none=True)
    new_date = p.pop("date", None)
    target.update(p)

    if new_date and new_date != date:            # 날짜 이동 = 미루기
        day.remove(target)
        target["postponedFrom"] = target.get("postponedFrom") or date
        target["postponeCount"] = target.get("postponeCount", 0) + 1
        db["events"].setdefault(new_date, []).append(target)
        if not db["events"][date]:
            del db["events"][date]
    save_db(db)
    return target


@app.delete("/api/events/{date}/{event_id}", status_code=204)
def delete_event(date: str, event_id: str):
    db = load_db()
    day = db["events"].get(date, [])
    before = len(day)
    db["events"][date] = [e for e in day if e["id"] != event_id]
    if len(db["events"][date]) == before:
        raise HTTPException(404, "event not found")
    if not db["events"][date]:
        del db["events"][date]
    save_db(db)


# 정적 파일은 맨 마지막 (api 라우트 우선)
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
