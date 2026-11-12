"""football-data.org から試合データを取って raw/ に保存する。
usage: python3 scripts/fetch.py daily   … 前後の日程（7日前〜30日先）・今季の結果・順位表
       python3 scripts/fetch.py season  … 今シーズンの全日程（対戦相手が決まっている試合のみ）
環境変数 FOOTBALL_DATA_TOKEN が必要。
"""
import json, os, re, sys, time
import urllib.error, urllib.request
from datetime import datetime, timedelta, timezone

API = "https://api.football-data.org/v4"
COMPS = ["PL", "PD", "SA", "BL1", "FL1", "CL"]
DAYS_BACK, DAYS_AHEAD, SLEEP, TRIES = 7, 30, 7, 4
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "raw")
os.makedirs(RAW, exist_ok=True)

TOKEN = os.environ.get("FOOTBALL_DATA_TOKEN", "").strip()
if not TOKEN:
    sys.exit("FOOTBALL_DATA_TOKEN が未設定です（リポジトリの Settings → Secrets and variables → Actions で登録）")
mode = sys.argv[1] if len(sys.argv) > 1 else "daily"

def get(path):
    """429 のときは API が指示した秒数だけ待って再試行する。"""
    for attempt in range(TRIES):
        req = urllib.request.Request(API + path, headers={"X-Auth-Token": TOKEN, "User-Agent": "match-cards/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read().decode("utf-8")), None
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace")
            if e.code == 429 and attempt < TRIES - 1:
                m = re.search(r"Wait (\d+) second", body)
                time.sleep((int(m.group(1)) + 3) if m else 61)
                continue
            return None, "HTTP %s: %s" % (e.code, body[:200])
        except Exception as e:
            if attempt < TRIES - 1:
                time.sleep(5)
                continue
            return None, "%s: %s" % (type(e).__name__, e)
    return None, "再試行を使い切りました"

def team(t):
    t = t or {}
    return {"id": t.get("id"), "name": t.get("name"), "shortName": t.get("shortName")}

def slim(m):
    s = m.get("score") or {}
    ft = s.get("fullTime") or {}
    return {"id": m.get("id"), "utcDate": m.get("utcDate"), "status": m.get("status"),
            "matchday": m.get("matchday"), "stage": m.get("stage"),
            "home": team(m.get("homeTeam")), "away": team(m.get("awayTeam")),
            "score": {"home": ft.get("home"), "away": ft.get("away")}}

def save(name, obj):
    with open(os.path.join(RAW, name), "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1, sort_keys=True)

def matches(path):
    data, err = get(path)
    if err:
        return None, err
    ms = sorted((slim(m) for m in data.get("matches", [])), key=lambda m: m["utcDate"] or "")
    return ms, None

errors, calls = [], 0
def wait():
    global calls
    if calls:
        time.sleep(SLEEP)
    calls += 1

today = datetime.now(timezone.utc).date()
for code in COMPS:
    if mode == "season":
        wait()
        ms, err = matches("/competitions/%s/matches" % code)
        if err:
            errors.append("season %s: %s" % (code, err)); print("[NG] season", code, err); continue
        ms = [m for m in ms if m["home"]["id"] and m["away"]["id"]]   # 対戦相手が未定の枠は除く
        save("season_%s.json" % code, {"count": len(ms), "matches": ms})
        print("[ok] season %s: %d" % (code, len(ms)))
        continue

    d_from = (today - timedelta(days=DAYS_BACK)).isoformat()
    d_to = (today + timedelta(days=DAYS_AHEAD)).isoformat()
    wait()
    ms, err = matches("/competitions/%s/matches?dateFrom=%s&dateTo=%s" % (code, d_from, d_to))
    if err:
        errors.append("matches %s: %s" % (code, err)); print("[NG] matches", code, err)
    else:
        save("matches_%s.json" % code, {"window": {"from": d_from, "to": d_to}, "matches": ms})
        print("[ok] matches %s: %d" % (code, len(ms)))

    wait()
    ms, err = matches("/competitions/%s/matches?status=FINISHED" % code)
    if err:
        errors.append("results %s: %s" % (code, err)); print("[NG] results", code, err)
    else:
        save("results_%s.json" % code, {"matches": ms})
        print("[ok] results %s: %d" % (code, len(ms)))

    wait()
    data, err = get("/competitions/%s/standings" % code)
    if err:
        errors.append("standings %s: %s" % (code, err)); print("[NG] standings", code, err)
    else:
        tables = [{"group": t.get("group"), "rows": [
            {"rank": r.get("position"), "team": team(r.get("team")), "played": r.get("playedGames"),
             "won": r.get("won"), "draw": r.get("draw"), "lost": r.get("lost"),
             "points": r.get("points"), "gd": r.get("goalDifference")} for r in t.get("table", [])]}
            for t in data.get("standings", []) if t.get("type") == "TOTAL"]
        save("standings_%s.json" % code, {"tables": tables})
        print("[ok] standings %s" % code)

if mode == "daily":
    save("meta.json", {"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                       "source": "football-data.org", "errors": errors})
if calls and len(errors) == calls:
    sys.exit("すべて失敗しました")
