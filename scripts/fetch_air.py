"""
Fetch live air-quality readings from CPCB (via data.gov.in) and save a small
summary file the website reads: data/air.json

Needs one secret: DATA_GOV_API_KEY (free key from data.gov.in).
Run locally:  DATA_GOV_API_KEY=yourkey python scripts/fetch_air.py
"""
import json, os, sys, time, datetime as dt
from collections import defaultdict
import requests

RESOURCE_ID = "3b01bcb8-0b14-4abf-b6f2-c1bfd384ba69"   # "Real time Air Quality Index from various locations"
URL = f"https://api.data.gov.in/resource/{RESOURCE_ID}"
OUT = os.path.join(os.path.dirname(__file__), "..", "data", "air.json")
PAGE = 500

# data.gov.in spells some states differently from the site's map file
STATE_FIX = {
    "NCT of Delhi": "Delhi", "Delhi": "Delhi",
    "Jammu and Kashmir": "Jammu and Kashmir", "Jammu & Kashmir": "Jammu and Kashmir",
    "Andaman and Nicobar": "Andaman and Nicobar Islands",
    "Dadra and Nagar Haveli and Daman and Diu": "Dadra and Nagar Haveli",
}

def clean_state(s):
    s = (s or "").replace("_", " ").strip()
    return STATE_FIX.get(s, s)

def num(x):
    try:
        v = float(x)
        return v if 0 < v < 1500 else None      # drop NA, zero and absurd values
    except (TypeError, ValueError):
        return None

def fetch_all(key):
    records, offset = [], 0
    while True:
        params = {"api-key": key, "format": "json", "limit": PAGE, "offset": offset}
        for attempt in range(3):
            try:
                r = requests.get(URL, params=params, timeout=60,
                                 headers={"User-Agent": "CivicLens/0.1 (public-interest research)"})
                r.raise_for_status()
                data = r.json()
                break
            except Exception as e:
                print(f"attempt {attempt+1} failed: {e}", file=sys.stderr)
                time.sleep(5 * (attempt + 1))
        else:
            raise SystemExit("Could not reach data.gov.in after 3 tries. Keeping the old file.")
        batch = data.get("records", [])
        records += batch
        total = int(data.get("total", 0) or 0)
        offset += PAGE
        if not batch or offset >= total:
            break
    return records

def summarise(records):
    # station -> its latest PM2.5 / PM10 average
    stations = {}
    for r in records:
        pol = (r.get("pollutant_id") or "").strip().upper().replace(".", "")
        if pol not in ("PM25", "PM10"):
            continue
        v = num(r.get("pollutant_avg"))
        if v is None:
            continue
        st = clean_state(r.get("state"))
        key = (st, r.get("city"), r.get("station"))
        stations.setdefault(key, {})[pol] = v
        stations[key]["updated"] = r.get("last_update") or ""
    by_state = defaultdict(lambda: {"pm25": [], "pm10": [], "stations": set(), "updated": ""})
    for (st, city, station), d in stations.items():
        s = by_state[st]
        if "PM25" in d: s["pm25"].append(d["PM25"])
        if "PM10" in d: s["pm10"].append(d["PM10"])
        s["stations"].add(station)
        s["updated"] = max(s["updated"], d.get("updated", ""))
    out = {}
    for st, s in by_state.items():
        if not st or not s["pm25"]:
            continue
        out[st] = {
            "pm25": round(sum(s["pm25"]) / len(s["pm25"]), 1),
            "pm10": round(sum(s["pm10"]) / len(s["pm10"]), 1) if s["pm10"] else None,
            "stations_reporting": len(s["stations"]),
            "source_last_update": s["updated"],
        }
    return out

def main():
    key = os.environ.get("DATA_GOV_API_KEY")
    if not key:
        raise SystemExit("Missing DATA_GOV_API_KEY.")
    records = fetch_all(key)
    print(f"Downloaded {len(records)} readings.")
    if records:
        print("First record (check field names):", json.dumps(records[0])[:400])
    states = summarise(records)
    if len(states) < 5:
        raise SystemExit(f"Only {len(states)} states had usable PM2.5 data. Not overwriting the old file.")
    payload = {
        "status": "ok",
        "source": "CPCB real-time air quality via data.gov.in",
        "measure": "Average of latest PM2.5 and PM10 readings across reporting stations (ug/m3). Raw readings, not an official AQI.",
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "states": states,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=1, ensure_ascii=False)
    print(f"Wrote {len(states)} states to data/air.json")

if __name__ == "__main__":
    main()
