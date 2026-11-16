"""Build data/regions.json: monthly AC yield (kWh per kWp) by region and roof direction.

Runs offline on a developer machine, never in the deployed app.

    uv run python tools/build_yield_table.py            # uses NREL_API_KEY or DEMO_KEY
    uv run python tools/build_yield_table.py --full     # every direction for every region (needs a real key)

Default source is PVGIS (no key). With --source pvwatts and DEMO_KEY (low rate limit) the tool calls PVWatts for a south-facing roof in every
region, and for all directions in two reference regions only. Other directions are then
derived from the reference regions' month-by-month ratios to south.
"""
import argparse, datetime, json, os, sys, time
from pathlib import Path
import httpx

API = "https://developer.nlr.gov/api/pvwatts/v8.json"   # NREL is now the National Laboratory of the Rockies
TILT, LOSSES = 10, 14
DIRECTIONS = {"south": (180, TILT), "east": (90, TILT), "west": (270, TILT), "north": (0, TILT), "flat": (180, 0)}

# Representative point per region: a main population centre. Used only here, offline.
REGIONS = [
    ("NCR", "National Capital Region", 14.60, 121.00),
    ("CAR", "Cordillera Administrative Region", 16.41, 120.60),
    ("I", "Ilocos Region (Region I)", 16.62, 120.32),
    ("II", "Cagayan Valley (Region II)", 17.61, 121.73),
    ("III", "Central Luzon (Region III)", 15.03, 120.69),
    ("IV-A", "CALABARZON (Region IV-A)", 14.21, 121.17),
    ("MIMAROPA", "MIMAROPA Region", 13.41, 121.18),
    ("V", "Bicol Region (Region V)", 13.14, 123.74),
    ("VI", "Western Visayas (Region VI)", 10.72, 122.56),
    ("NIR", "Negros Island Region", 10.68, 122.95),
    ("VII", "Central Visayas (Region VII)", 10.31, 123.89),
    ("VIII", "Eastern Visayas (Region VIII)", 11.24, 125.00),
    ("IX", "Zamboanga Peninsula (Region IX)", 6.91, 122.08),
    ("X", "Northern Mindanao (Region X)", 8.48, 124.65),
    ("XI", "Davao Region (Region XI)", 7.07, 125.61),
    ("XII", "SOCCSKSARGEN (Region XII)", 6.50, 124.85),
    ("XIII", "Caraga (Region XIII)", 8.95, 125.54),
    ("BARMM", "Bangsamoro (BARMM)", 7.22, 124.25),
]
REFERENCE = ["NCR", "XI"]


def pvwatts(client, key, lat, lon, azimuth, tilt):
    params = dict(api_key=key, lat=lat, lon=lon, system_capacity=1, azimuth=azimuth, tilt=tilt,
                  array_type=1, module_type=0, losses=LOSSES)
    for attempt in range(3):
        r = client.get(API, params=params, timeout=60)
        if r.status_code == 429:
            time.sleep(60 * (attempt + 1)); continue
        r.raise_for_status()
        d = r.json()
        if d.get("errors"):
            raise RuntimeError(d["errors"])
        return [round(x, 1) for x in d["outputs"]["ac_monthly"]], d["station_info"]["weather_data_source"]
    raise RuntimeError("rate limited")


PVGIS_API = "https://re.jrc.ec.europa.eu/api/v5_3/PVcalc"
PVGIS_ASPECT = {"south": (0, TILT), "east": (-90, TILT), "west": (90, TILT), "north": (180, TILT), "flat": (0, 0)}


def pvgis(client, lat, lon, aspect, angle):
    params = dict(lat=lat, lon=lon, peakpower=1, loss=LOSSES, angle=angle, aspect=aspect,
                  raddatabase="PVGIS-ERA5", outputformat="json")
    for attempt in range(3):
        r = client.get(PVGIS_API, params=params, timeout=60)
        if r.status_code == 429:
            time.sleep(5 * (attempt + 1)); continue
        r.raise_for_status()
        return [round(m["E_m"], 1) for m in r.json()["outputs"]["monthly"]["fixed"]]
    raise RuntimeError("rate limited")


def main_pvgis(out_path):
    out = []
    with httpx.Client() as c:
        for code, name, lat, lon in REGIONS:
            y = {d: pvgis(c, lat, lon, *PVGIS_ASPECT[d]) for d in PVGIS_ASPECT}
            out.append({"code": code, "name": name, "yield_kwh_per_kwp": y})
            print(code, round(sum(y["south"])), "kWh/kWp/yr (south)")
            time.sleep(0.5)
    doc = {
        "source": f"EU JRC PVGIS 5.3 (ERA5 weather data); fixed roof mount, tilt {TILT} degrees (flat: 0), "
                  f"system losses {LOSSES}%. Cross-check: NREL PVWatts v8 (Himawari data) gives about 5% less for Metro Manila.",
        "method": "all directions modelled per region",
        "generated": datetime.date.today().isoformat(),
        "regions": out,
    }
    Path(out_path).write_text(json.dumps(doc, indent=1), encoding="utf-8")
    print("wrote", out_path)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--full", action="store_true")
    ap.add_argument("--source", choices=["pvwatts", "pvgis"], default="pvgis",
                    help="pvgis needs no key; pvwatts needs NREL_API_KEY for a full run")
    ap.add_argument("--out", default=str(Path(__file__).resolve().parents[1] / "data" / "regions.json"))
    a = ap.parse_args()
    if a.source == "pvgis":
        return main_pvgis(a.out)
    key = os.environ.get("NREL_API_KEY", "DEMO_KEY")
    full = a.full or key != "DEMO_KEY"
    out, sources = [], set()
    with httpx.Client() as c:
        ratios = {}
        if not full:
            for code in REFERENCE:
                lat, lon = next((r[2], r[3]) for r in REGIONS if r[0] == code)
                res = {d: pvwatts(c, key, lat, lon, *DIRECTIONS[d])[0] for d in DIRECTIONS}
                ratios[code] = {d: [x / s for x, s in zip(res[d], res["south"])] for d in DIRECTIONS}
                print("reference", code, {d: round(sum(v), 0) for d, v in res.items()})
            avg = {d: [sum(ratios[r][d][m] for r in REFERENCE) / len(REFERENCE) for m in range(12)] for d in DIRECTIONS}
        for code, name, lat, lon in REGIONS:
            if full:
                y = {}
                for d in DIRECTIONS:
                    y[d], src = pvwatts(c, key, lat, lon, *DIRECTIONS[d]); sources.add(src)
            else:
                south, src = pvwatts(c, key, lat, lon, *DIRECTIONS["south"]); sources.add(src)
                y = {d: [round(s * f, 1) for s, f in zip(south, avg[d])] for d in DIRECTIONS}
            out.append({"code": code, "name": name, "yield_kwh_per_kwp": y})
            print(code, round(sum(y["south"])), "kWh/kWp/yr (south)")
            time.sleep(1.5)
    doc = {
        "source": f"NREL/NLR PVWatts v8; weather data: {', '.join(sorted(sources))}; fixed roof mount, "
                  f"tilt {TILT} degrees (flat: 0), system losses {LOSSES}%, standard modules",
        "method": "all directions modelled per region" if full else
                  f"south modelled per region; other directions scaled by monthly ratios from {', '.join(REFERENCE)}",
        "generated": datetime.date.today().isoformat(),
        "regions": out,
    }
    Path(a.out).write_text(json.dumps(doc, indent=1), encoding="utf-8")
    print("wrote", a.out)


if __name__ == "__main__":
    sys.exit(main())
