import json
import os
import sys
from datetime import datetime, timedelta


def find_events(obj):
    if isinstance(obj, list):
        if obj and isinstance(obj[0], dict) and ("startDate" in obj[0] or "eventType" in obj[0]):
            return obj
    if isinstance(obj, dict):
        for key in ("events", "data", "items", "plan", "records"):
            if key in obj:
                res = find_events(obj[key])
                if res is not None:
                    return res
        for val in obj.values():
            if isinstance(val, (dict, list)):
                res = find_events(val)
                if res is not None:
                    return res
    return None


def parse_dt(date_str, time_str):
    h, m = map(int, (time_str or "08:00").split(":")[:2])
    d = datetime.strptime(date_str, "%Y-%m-%d")
    return d.replace(hour=h, minute=m)


def expand_item(it):
    start_date_str = it.get("startDate")
    if not start_date_str:
        return []

    end_date_str = it.get("endDate") or start_date_str
    start_d = datetime.strptime(start_date_str, "%Y-%m-%d").date()
    end_d = datetime.strptime(end_date_str, "%Y-%m-%d").date()
    interval = int(it.get("intervalWeeks") or 1)
    excluded = set(it.get("excludedDates") or [])
    overrides = it.get("overrides") or {}

    dates = set()
    cur = start_d
    while cur <= end_d:
        dates.add(cur.strftime("%Y-%m-%d"))
        if interval <= 0:
            break
        cur += timedelta(weeks=interval)

    for ov_date, ov in overrides.items():
        if isinstance(ov, dict) and ov.get("_add"):
            dates.add(ov_date)

    terminy = []
    for d_str in sorted(dates):
        if d_str in excluded:
            continue
        ov = overrides.get(d_str) if isinstance(overrides.get(d_str), dict) else {}
        if ov.get("cancelled"):
            continue

        t_str = ov.get("startTime") or it.get("startTime") or "08:00"
        dur = int(ov.get("durationMin") or it.get("durationMin") or 90)
        start_dt = parse_dt(d_str, t_str)
        end_dt = start_dt + timedelta(minutes=dur)

        terminy.append({
            "start": start_dt.strftime("%Y-%m-%dT%H:%M:%S"),
            "end": end_dt.strftime("%Y-%m-%dT%H:%M:%S"),
            "eventType": ov.get("eventType") or it.get("eventType") or it.get("title") or "",
            "group": ov.get("group") if "group" in ov else (it.get("group") or ""),
            "instructor": ov.get("instructor") if "instructor" in ov else (it.get("instructor") or ""),
            "room": ov.get("room") if "room" in ov else (it.get("room") or ""),
        })

    return terminy


def main():
    with open("raw.json", "r", encoding="utf-8") as f:
        raw = json.load(f)

    events = find_events(raw)
    if events is None:
        print("Nie znaleziono listy zajęć w raw.json", file=sys.stderr)
        sys.exit(1)

    codes_env = os.environ.get("KIERUNKI", "").strip()
    codes = [c.strip() for c in codes_env.split(",") if c.strip()]

    out_data = []
    for it in events:
        fac_str = it.get("faculty") or ""
        facs = [x.strip() for x in fac_str.split(",") if x.strip()]
        if codes and not any(c in facs for c in codes):
            continue

        terminy = expand_item(it)
        if not terminy:
            continue

        out_data.append({
            "faculty": fac_str,
            "eventType": it.get("eventType") or it.get("title") or "",
            "instructor": it.get("instructor") or "",
            "terminy": terminy,
        })

    result = {
        "codes": codes,
        "updatedAt": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "data": out_data,
    }

    with open("plan.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, separators=(",", ":"))

    print(f"Zapisano plan.json ({len(out_data)} przedmiotów dla {codes})")


if __name__ == "__main__":
    main()
