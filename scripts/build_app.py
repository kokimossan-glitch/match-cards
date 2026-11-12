"""raw/*.json（football-data.org から取ったもの）を、アプリが読む data/app.json にまとめる。
usage: python3 scripts/build_app.py
- 日程：毎日の前後日程（matches_*） > 今季の結果（results_*） > 年1回の全日程（season_*）の順に優先して合流
- 順位表：standings_*
"""
import json, os
from datetime import datetime, timezone

CODES = ["PL", "PD", "SA", "BL1", "FL1", "CL"]
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW, OUT = os.path.join(ROOT, "raw"), os.path.join(ROOT, "data")
os.makedirs(OUT, exist_ok=True)

def load(name):
    p = os.path.join(RAW, name)
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else None

def team(t):
    t = t or {}
    return {"id": t.get("id"), "n": t.get("shortName") or t.get("name") or "未定"}

fixtures, standings = {}, {}
for c in CODES:
    seen, items = set(), []
    for name in (f"matches_{c}.json", f"results_{c}.json", f"season_{c}.json"):
        d = load(name)
        for x in (d or {}).get("matches", []):
            if x["id"] in seen:
                continue
            seen.add(x["id"])
            s = x.get("score") or {}
            items.append({"id": x["id"], "ts": x["utcDate"], "st": x["status"], "md": x.get("matchday"),
                          "h": team(x.get("home")), "a": team(x.get("away")),
                          "sc": [s.get("home"), s.get("away")]})
    items.sort(key=lambda i: i["ts"] or "")
    fixtures[c] = {"items": items}

    st = load(f"standings_{c}.json")
    if st:
        standings[c] = {"tables": [{"group": tb.get("group"), "rows": [
            {"rank": r["rank"], "team": team(r["team"]), "played": r["played"], "pts": r["points"],
             "gd": r["gd"], "w": r["won"], "d": r["draw"], "l": r["lost"]}
            for r in tb.get("rows", [])]} for tb in st.get("tables", [])]}

meta = load("meta.json") or {}
out = {"meta": {"last_sync_at": meta.get("generated_at") or datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "errors": meta.get("errors", [])},
       "fixtures": fixtures, "standings": standings}
json.dump(out, open(os.path.join(OUT, "app.json"), "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
print("app.json:", {c: len(fixtures[c]["items"]) for c in CODES})
