#!/usr/bin/env python3
"""AstroLab ephemeris calculator for natal, transit, and progression work."""
import argparse
import csv
import datetime as dt
from functools import lru_cache
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sys
import tempfile
import urllib.request
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

try:
    import swisseph as swe
except ImportError:
    sys.exit("pyswisseph is required: python -m pip install pyswisseph")

VERSION = "0.2.0"
SCHEMA_VERSION = 2
MAX_RANGE_DAYS = 366 * 50
ENGINE_FLAGS = {
    "auto": swe.FLG_SWIEPH,
    "swiss": swe.FLG_SWIEPH,
    "moshier": swe.FLG_MOSEPH,
    "jpl": swe.FLG_JPLEPH,
}
ACTIVE_ENGINE = "auto"
ACTIVE_FLAG = swe.FLG_SWIEPH | swe.FLG_SPEED
ACTIVE_EPHE_PATH = None
ACTIVE_JPL_FILE = None
ENGINES_USED = set()
PLANETS = {
    "sun": swe.SUN, "moon": swe.MOON, "mercury": swe.MERCURY,
    "venus": swe.VENUS, "mars": swe.MARS, "jupiter": swe.JUPITER,
    "saturn": swe.SATURN, "uranus": swe.URANUS, "neptune": swe.NEPTUNE,
    "pluto": swe.PLUTO,
}
EXTENDED_BODIES = {
    "true_node": swe.TRUE_NODE,
    "mean_node": swe.MEAN_NODE,
    "chiron": swe.CHIRON,
    "lilith": swe.MEAN_APOG,
}
BODIES = {**PLANETS, **EXTENDED_BODIES}
DEFAULT_CHART_BODIES = list(PLANETS) + ["true_node", "chiron", "lilith"]
SIGNS = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo", "Libra",
         "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"]
ASPECTS = {"conjunction": 0, "sextile": 60, "square": 90,
           "trine": 120, "opposition": 180}
SNAPSHOT_ORBS = {0: 3.0, 60: 2.0, 90: 3.0, 120: 3.0, 180: 3.0}
SCAN_STEP = {"sun": 0.5, "moon": 0.05, "mercury": 0.25, "venus": 0.5,
             "mars": 0.5, "jupiter": 1.0, "saturn": 1.0, "uranus": 2.0,
             "neptune": 2.0, "pluto": 2.0}
SERIES_GAP = {"sun": 30.0, "moon": 5.0, "mercury": 90.0, "venus": 180.0,
              "mars": 300.0, "jupiter": 300.0, "saturn": 400.0,
              "uranus": 500.0, "neptune": 500.0, "pluto": 500.0}
DEFAULT_TRANSITERS = ["mars", "jupiter", "saturn", "uranus", "neptune", "pluto"]
EPHEMERIS_FILES = ("sepl_18.se1", "semo_18.se1", "seas_18.se1", "sefstars.txt")
EPHEMERIS_BASE_URL = "https://raw.githubusercontent.com/aloistr/swisseph/master/ephe"
MAX_DOWNLOAD_BYTES = 160 * 1024 * 1024
UTC = dt.timezone.utc
UNIX_JD = 2440587.5


def configure_output_encoding():
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8")


def fmt_lon(lon):
    sign = int(lon // 30) % 12
    deg = lon % 30
    minutes = int(round((deg - int(deg)) * 60))
    degree = int(deg)
    if minutes == 60:
        degree, minutes = degree + 1, 0
    if degree == 30:
        sign, degree = (sign + 1) % 12, 0
    return f"{SIGNS[sign]} {degree}°{minutes:02d}'"


def angdiff(a, b):
    return (a - b + 180.0) % 360.0 - 180.0


def default_ephe_path():
    configured = os.environ.get("ASTROLAB_EPHE_PATH") or os.environ.get("SE_EPHE_PATH")
    return Path(configured).expanduser() if configured else Path.home() / ".astrolab" / "ephe"


def display_path(path):
    resolved = Path(path).expanduser().resolve()
    try:
        return str(Path("~") / resolved.relative_to(Path.home().resolve()))
    except ValueError:
        return str(resolved)


def sanitize_local_paths(value):
    return str(value).replace(str(Path.home()), "~")


def engine_from_flags(flags):
    if flags & swe.FLG_JPLEPH:
        return "jpl"
    if flags & swe.FLG_SWIEPH:
        return "swiss"
    if flags & swe.FLG_MOSEPH:
        return "moshier"
    return "analytic"


def configure_ephemeris(args):
    global ACTIVE_ENGINE, ACTIVE_FLAG, ACTIVE_EPHE_PATH, ACTIVE_JPL_FILE
    ACTIVE_ENGINE = getattr(args, "engine", None) or "auto"
    if ACTIVE_ENGINE not in ENGINE_FLAGS:
        raise ValueError(f"unknown ephemeris engine {ACTIVE_ENGINE!r}")
    requested_path = getattr(args, "ephe_path", None)
    path = Path(requested_path).expanduser() if requested_path else default_ephe_path()
    ACTIVE_EPHE_PATH = str(path.resolve())
    swe.set_ephe_path(ACTIVE_EPHE_PATH)
    ACTIVE_JPL_FILE = getattr(args, "jpl_file", None)
    if ACTIVE_ENGINE == "jpl":
        if not ACTIVE_JPL_FILE:
            raise ValueError("--engine jpl requires --jpl-file")
        jpl_path = Path(ACTIVE_JPL_FILE).expanduser().resolve()
        if not jpl_path.is_file():
            raise ValueError(f"JPL ephemeris file not found: {jpl_path}")
        swe.set_ephe_path(str(jpl_path.parent))
        swe.set_jpl_file(jpl_path.name)
        ACTIVE_EPHE_PATH, ACTIVE_JPL_FILE = str(jpl_path.parent), str(jpl_path)
    ACTIVE_FLAG = ENGINE_FLAGS[ACTIVE_ENGINE] | swe.FLG_SPEED
    ENGINES_USED.clear()
    _body_state.cache_clear()


@lru_cache(maxsize=240_000)
def _body_state(jd, body, flag):
    values, returned = swe.calc_ut(jd, body, flag)
    actual = engine_from_flags(returned)
    ENGINES_USED.add(actual)
    if ACTIVE_ENGINE == "swiss" and body in PLANETS.values() and actual != "swiss":
        raise ValueError(
            f"Swiss ephemeris data unavailable in {display_path(ACTIVE_EPHE_PATH)}; "
            "run `astrolab ephemeris download` or choose --engine moshier"
        )
    if ACTIVE_ENGINE == "jpl" and body in PLANETS.values() and actual != "jpl":
        raise ValueError("JPL ephemeris could not serve the requested planetary calculation")
    return tuple(values), returned


def body_state(jd, body):
    return _body_state(jd, body, ACTIVE_FLAG)


def planet_state(jd, planet):
    values, _ = body_state(jd, planet)
    return values[0], values[3]


def lon_of(jd, planet):
    return planet_state(jd, planet)[0]


def speed_of(jd, planet):
    return planet_state(jd, planet)[1]


def coordinate_record(jd, name, body):
    values, flags = body_state(jd, body)
    equatorial, _ = _body_state(jd, body, ACTIVE_FLAG | swe.FLG_EQUATORIAL)
    return {
        "name": name,
        "longitude": values[0],
        "latitude": values[1],
        "distance_au": values[2],
        "longitude_speed": values[3],
        "right_ascension": equatorial[0],
        "declination": equatorial[1],
        "retrograde": values[3] < 0,
        "engine": engine_from_flags(flags),
    }


def source_metadata():
    files = []
    path = Path(ACTIVE_EPHE_PATH) if ACTIVE_EPHE_PATH else default_ephe_path()
    manifest_summary = None
    hashes = {}
    manifest_path = path / "astrolab-ephemeris-manifest.json"
    if manifest_path.is_file():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if not isinstance(manifest, dict) or not isinstance(manifest.get("files", []), list):
                raise ValueError("invalid manifest")
            hashes = {item["name"]: item.get("sha256") for item in manifest.get("files", [])
                      if isinstance(item, dict) and isinstance(item.get("name"), str)}
            manifest_summary = {key: manifest.get(key) for key in ("source", "base_url", "downloaded_at")}
        except (OSError, json.JSONDecodeError, UnicodeDecodeError, ValueError):
            manifest_summary = {"error": "manifest could not be read"}
    for name in EPHEMERIS_FILES:
        candidate = path / name
        if candidate.is_file():
            files.append({"name": name, "bytes": candidate.stat().st_size,
                          "sha256": hashes.get(name)})
    return {
        "requested_engine": ACTIVE_ENGINE,
        "actual_engines": sorted(ENGINES_USED),
        "swiss_ephemeris_version": swe.version,
        "jpl_file": Path(ACTIVE_JPL_FILE).name if ACTIVE_JPL_FILE else None,
        "data_files": files,
        "data_manifest": manifest_summary,
    }


def source_label():
    metadata = source_metadata()
    engines = ", ".join(metadata["actual_engines"]) or "not yet resolved"
    return f"{engines}; Swiss Ephemeris {metadata['swiss_ephemeris_version']}"


def parse_date(value):
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ValueError(f"invalid date {value!r}; expected YYYY-MM-DD")
    try:
        return dt.date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"invalid date {value!r}: {exc}") from None


def parse_time(value):
    if not isinstance(value, str) or not re.fullmatch(r"\d{2}:\d{2}(?::\d{2})?", value):
        raise ValueError(f"invalid time {value!r}; expected HH:MM or HH:MM:SS")
    try:
        return dt.time.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"invalid time {value!r}: {exc}") from None


def is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def validate_tz(tz):
    if not is_number(tz) or not -14.0 <= tz <= 14.0:
        raise ValueError(f"UTC offset {tz!r} is outside the supported range -14..+14")
    return float(tz)


def get_zone(name):
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError, TypeError):
        raise ValueError(f"unknown IANA timezone {name!r}") from None


def local_zone_datetime(date_str, time_str, zone_name, fold=None):
    naive = dt.datetime.combine(parse_date(date_str), parse_time(time_str))
    zone = get_zone(zone_name)
    candidates = []
    for value in (0, 1):
        aware = naive.replace(tzinfo=zone, fold=value)
        valid = aware.astimezone(UTC).astimezone(zone).replace(tzinfo=None) == naive
        if valid:
            candidates.append(aware)
    if not candidates:
        raise ValueError(f"local time {date_str} {time_str} does not exist in {zone_name}")
    offsets = {item.utcoffset() for item in candidates}
    if len(offsets) > 1 and fold is None:
        raise ValueError(
            f"local time {date_str} {time_str} is ambiguous in {zone_name}; use --fold 0 or --fold 1"
        )
    selected_fold = 0 if fold is None else fold
    return naive.replace(tzinfo=zone, fold=selected_fold)


def jd_from_local(date_str, time_str, tz):
    date, time = parse_date(date_str), parse_time(time_str)
    tz = validate_tz(tz)
    hour = time.hour + time.minute / 60.0 + time.second / 3600.0
    return swe.julday(date.year, date.month, date.day, hour - tz)


def jd_from_zone(date_str, time_str, zone_name, fold=None):
    instant = local_zone_datetime(date_str, time_str, zone_name, fold).astimezone(UTC)
    hour = instant.hour + instant.minute / 60.0 + instant.second / 3600.0
    return swe.julday(instant.year, instant.month, instant.day, hour)


def timezone_spec(args, chart=None, default=0.0):
    tz_name = getattr(args, "tz_name", None)
    if tz_name:
        get_zone(tz_name)
        return tz_name
    tz = getattr(args, "tz", None)
    if tz is not None:
        return validate_tz(tz)
    if chart:
        if chart["meta"].get("tz_name"):
            return chart["meta"]["tz_name"]
        return chart["meta"]["tz"]
    return validate_tz(default)


def jd_for_local(date_str, time_str, tz_spec, fold=None):
    if isinstance(tz_spec, str):
        return jd_from_zone(date_str, time_str, tz_spec, fold)
    return jd_from_local(date_str, time_str, tz_spec)


def jd_range(start, end, tz_spec, fold=None):
    start_date, end_date = parse_date(start), parse_date(end)
    if end_date < start_date:
        raise ValueError(f"end date {end} precedes start date {start}")
    if (end_date - start_date).days + 1 > MAX_RANGE_DAYS:
        raise ValueError(f"date range exceeds the {MAX_RANGE_DAYS}-day safety limit")
    next_date = end_date + dt.timedelta(days=1)
    return (jd_for_local(start_date.isoformat(), "00:00", tz_spec, fold),
            jd_for_local(next_date.isoformat(), "00:00", tz_spec, fold))


def fmt_tz(tz):
    tz = validate_tz(tz)
    total = int(round(abs(tz) * 60))
    hours, minutes = divmod(total, 60)
    return f"{'+' if tz >= 0 else '-'}{hours:02d}:{minutes:02d}"


def jd_to_datetime(jd):
    return dt.datetime(1970, 1, 1, tzinfo=UTC) + dt.timedelta(days=jd - UNIX_JD)


def jd_to_str(jd, tz_spec):
    utc = (jd_to_datetime(jd) + dt.timedelta(seconds=30)).replace(second=0, microsecond=0)
    if isinstance(tz_spec, str):
        local = utc.astimezone(get_zone(tz_spec))
        return f"{local:%Y-%m-%d %H:%M} {tz_spec} (UTC{local:%z})"
    local = utc + dt.timedelta(hours=validate_tz(tz_spec))
    return f"{local:%Y-%m-%d %H:%M} UTC{fmt_tz(tz_spec)}"


def parse_names(value, allowed, label):
    raw = [item.strip().lower() for item in value.split(",") if item.strip()]
    names = list(dict.fromkeys(raw))
    if not names:
        raise ValueError(f"{label} list cannot be empty")
    unknown = sorted(set(names) - set(allowed))
    if unknown:
        raise ValueError(f"unknown {label}: {', '.join(unknown)}; choose from {', '.join(allowed)}")
    return names


def cluster_hits(hits, max_gap):
    clusters = []
    for hit in sorted(hits):
        if not clusters or hit - clusters[-1][-1] > max_gap:
            clusters.append([hit])
        elif hit - clusters[-1][-1] > 1e-6:
            clusters[-1].append(hit)
    return clusters


def aspect_trend(signed_orb, speed):
    if abs(signed_orb) < 1e-7:
        return "exact"
    return "applying" if signed_orb * speed < 0 else "separating"


def bisect_crossing(fn, a, b, iters=48):
    fa = fn(a)
    for _ in range(iters):
        middle = (a + b) / 2.0
        fm = fn(middle)
        if (fa < 0) != (fm < 0):
            b = middle
        else:
            a, fa = middle, fm
    return (a + b) / 2.0


def minimize_abs(fn, a, b, iters=64):
    ratio = (math.sqrt(5.0) - 1.0) / 2.0
    c, d = b - ratio * (b - a), a + ratio * (b - a)
    fc, fd = abs(fn(c)), abs(fn(d))
    for _ in range(iters):
        if fc < fd:
            b, d, fd = d, c, fc
            c = b - ratio * (b - a)
            fc = abs(fn(c))
        else:
            a, c, fc = c, d, fd
            d = a + ratio * (b - a)
            fd = abs(fn(d))
    return (a + b) / 2.0


def scan_crossings(fn, jd0, jd1, step, tolerance=1e-7):
    """Find sign-changing and tangent zeros of a continuous signed function."""
    samples = [(jd0, fn(jd0))]
    cursor = jd0
    while cursor < jd1:
        cursor = min(cursor + step, jd1)
        samples.append((cursor, fn(cursor)))
    hits = []
    for (a, fa), (b, fb) in zip(samples, samples[1:]):
        if abs(fa) <= tolerance:
            hits.append(a)
        if (fa < 0) != (fb < 0) and abs(fa - fb) < 180.0:
            hits.append(bisect_crossing(fn, a, b))
    if abs(samples[-1][1]) <= tolerance:
        hits.append(samples[-1][0])
    for left, middle, right in zip(samples, samples[1:], samples[2:]):
        if (abs(middle[1]) <= abs(left[1]) and abs(middle[1]) <= abs(right[1])
                and abs(left[1] - middle[1]) < 180.0
                and abs(middle[1] - right[1]) < 180.0):
            hit = minimize_abs(fn, left[0], right[0])
            if abs(fn(hit)) <= tolerance:
                hits.append(hit)
    return [cluster[0] for cluster in cluster_hits(hits, 1e-6)]


def output_mode(args):
    return "json" if getattr(args, "json", False) else "csv" if getattr(args, "csv", False) else "text"


def emit_structured(args, payload, rows, fields):
    mode = output_mode(args)
    if mode == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False))
        return True
    if mode == "csv":
        writer = csv.DictWriter(sys.stdout, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else value
                             for key, value in row.items()})
        return True
    return False


def save_chart(chart, destination, force=False):
    path = Path(destination).expanduser().resolve()
    if path.exists() and not force:
        raise ValueError(f"refusing to overwrite existing chart {path}; use --force")
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        if hasattr(os, "fchmod"):
            os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(chart, handle, ensure_ascii=False, indent=2, allow_nan=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
        if os.name != "nt":
            os.chmod(path, 0o600)
    except Exception:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass
        raise
    return path


def private_chart_path(session_id):
    safe = re.sub(r"[^A-Za-z0-9_.-]", "-", session_id).strip(".-")
    if not safe:
        raise ValueError("private session id must contain a letter or number")
    return Path(tempfile.gettempdir()) / f"astrolab-{safe}.chart.json"


def download_ephemeris_file(name, destination, force=False):
    target = destination / name
    if target.exists() and not force:
        return {"name": name, "status": "kept", "bytes": target.stat().st_size,
                "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
                "url": f"{EPHEMERIS_BASE_URL}/{name}"}
    url = f"{EPHEMERIS_BASE_URL}/{name}"
    request = urllib.request.Request(url, headers={"User-Agent": f"AstroLab/{VERSION}"})
    descriptor, temp_name = tempfile.mkstemp(prefix=f".{name}.", dir=destination)
    digest, total = hashlib.sha256(), 0
    try:
        with os.fdopen(descriptor, "wb") as output, urllib.request.urlopen(request, timeout=60) as response:
            declared = response.headers.get("Content-Length")
            etag = response.headers.get("ETag")
            last_modified = response.headers.get("Last-Modified")
            if declared and int(declared) > MAX_DOWNLOAD_BYTES:
                raise ValueError(f"refusing oversized ephemeris file {name}")
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_DOWNLOAD_BYTES:
                    raise ValueError(f"refusing oversized ephemeris file {name}")
                output.write(chunk)
                digest.update(chunk)
            output.flush()
            os.fsync(output.fileno())
        if total == 0:
            raise ValueError(f"downloaded ephemeris file {name} is empty")
        os.replace(temp_name, target)
    except Exception:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass
        raise
    return {"name": name, "status": "downloaded", "bytes": total,
            "sha256": digest.hexdigest(), "url": url, "etag": etag,
            "last_modified": last_modified}


def cmd_ephemeris(args):
    destination = Path(args.destination).expanduser().resolve() if args.destination else default_ephe_path().resolve()
    if args.action == "status":
        rows = []
        for name in EPHEMERIS_FILES:
            path = destination / name
            rows.append({"name": name, "present": path.is_file(),
                         "bytes": path.stat().st_size if path.is_file() else None})
        payload = {"path": display_path(destination), "files": rows,
                   "complete": all(row["present"] for row in rows)}
        if emit_structured(args, payload, rows, ["name", "present", "bytes"]):
            return
        print(f"Ephemeris data: {display_path(destination)}")
        for row in rows:
            suffix = f" ({row['bytes']} bytes)" if row["present"] else ""
            print(f"  {row['name']:14s} {'present' if row['present'] else 'missing'}{suffix}")
        return
    destination.mkdir(parents=True, exist_ok=True)
    records = []
    for index, name in enumerate(EPHEMERIS_FILES, 1):
        print(f"Downloading {name} ({index}/{len(EPHEMERIS_FILES)})…", file=sys.stderr, flush=True)
        records.append(download_ephemeris_file(name, destination, args.force))
    manifest = {
        "source": "Astrodienst official Swiss Ephemeris GitHub repository",
        "base_url": EPHEMERIS_BASE_URL,
        "downloaded_at": dt.datetime.now(UTC).isoformat(),
        "files": records,
    }
    manifest_path = destination / "astrolab-ephemeris-manifest.json"
    with open(manifest_path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(manifest, handle, ensure_ascii=False, indent=2, allow_nan=False)
        handle.write("\n")
    if emit_structured(args, {"path": display_path(destination), **manifest}, records,
                       ["name", "status", "bytes", "sha256", "url", "etag", "last_modified"]):
        return
    print(f"Installed Swiss Ephemeris data in {display_path(destination)}")
    for row in records:
        print(f"  {row['name']:14s} {row['status']:10s} {row['sha256'][:12]}…")


def compute_natal(args):
    configure_ephemeris(args)
    if not -90.0 <= args.lat <= 90.0:
        raise ValueError(f"latitude {args.lat} is outside -90..+90")
    if not -180.0 <= args.lon <= 180.0:
        raise ValueError(f"longitude {args.lon} is outside -180..+180")
    if len(args.hsys) != 1 or not args.hsys.isalpha():
        raise ValueError("house system must be one letter, such as P or W")
    tz_spec = timezone_spec(args)
    jd = jd_for_local(args.date, args.time, tz_spec, getattr(args, "fold", None))
    if isinstance(tz_spec, str):
        aware = local_zone_datetime(args.date, args.time, tz_spec, getattr(args, "fold", None))
        birth_offset = aware.utcoffset().total_seconds() / 3600.0
    else:
        birth_offset = tz_spec
    meta = {"date": args.date, "time": args.time, "tz": birth_offset,
            "lat": args.lat, "lon": args.lon, "hsys": args.hsys, "jd_ut": jd}
    if isinstance(tz_spec, str):
        meta["tz_name"] = tz_spec
        meta["fold"] = 0 if getattr(args, "fold", None) is None else args.fold
    chart = {"schema_version": SCHEMA_VERSION, "meta": meta, "points": {},
             "retro": {}, "coordinates": {}, "unavailable_bodies": []}
    selected = parse_names(getattr(args, "bodies", None) or ",".join(DEFAULT_CHART_BODIES),
                           BODIES, "body")
    requested = list(PLANETS) + [name for name in selected if name not in PLANETS]
    for name in requested:
        try:
            record = coordinate_record(jd, name, BODIES[name])
        except swe.Error as exc:
            if name in PLANETS:
                raise
            chart["unavailable_bodies"].append({"name": name, "reason": sanitize_local_paths(exc)})
            continue
        chart["coordinates"][name] = record
        chart["points"][name] = record["longitude"]
        chart["retro"][name] = record["retrograde"]
    try:
        cusps, ascmc = swe.houses(jd, args.lat, args.lon, args.hsys.encode())
    except swe.Error as exc:
        raise ValueError(
            f"house calculation failed for {args.hsys} at latitude {args.lat}: {exc}. "
            "Try --hsys W for whole-sign houses at polar latitudes."
        ) from None
    chart["points"]["asc"], chart["points"]["mc"] = ascmc[0], ascmc[1]
    chart["cusps"] = list(cusps)
    chart["meta"]["ephemeris"] = source_metadata()
    return chart


def natal_house_of(chart, lon):
    for index in range(12):
        start, end = chart["cusps"][index], chart["cusps"][(index + 1) % 12]
        if (lon - start) % 360.0 < (end - start) % 360.0:
            return index + 1
    return 12


def validate_chart(chart, path="chart"):
    if not isinstance(chart, dict):
        raise ValueError(f"invalid natal chart {path}: top level must be an object")
    version = chart.get("schema_version", 0)
    if not isinstance(version, int) or isinstance(version, bool) or version not in (0, 1, SCHEMA_VERSION):
        raise ValueError(f"invalid natal chart {path}: unsupported schema_version {version!r}")
    required = {"meta", "points", "retro", "cusps"}
    missing = sorted(required - set(chart))
    if missing:
        raise ValueError(f"invalid natal chart {path}: missing {', '.join(missing)}")
    meta = chart["meta"]
    if not isinstance(meta, dict):
        raise ValueError(f"invalid natal chart {path}: meta must be an object")
    meta_required = {"date", "time", "tz", "lat", "lon", "hsys", "jd_ut"}
    missing = sorted(meta_required - set(meta))
    if missing:
        raise ValueError(f"invalid natal chart {path}: meta missing {', '.join(missing)}")
    parse_date(meta["date"])
    parse_time(meta["time"])
    validate_tz(meta["tz"])
    if not is_number(meta["lat"]) or not -90 <= meta["lat"] <= 90:
        raise ValueError(f"invalid natal chart {path}: malformed latitude")
    if not is_number(meta["lon"]) or not -180 <= meta["lon"] <= 180:
        raise ValueError(f"invalid natal chart {path}: malformed longitude")
    if not is_number(meta["jd_ut"]):
        raise ValueError(f"invalid natal chart {path}: malformed jd_ut")
    if not isinstance(meta["hsys"], str) or len(meta["hsys"]) != 1 or not meta["hsys"].isalpha():
        raise ValueError(f"invalid natal chart {path}: malformed house system")
    if "tz_name" in meta:
        get_zone(meta["tz_name"])
    points = chart["points"]
    required_points = set(PLANETS) | {"asc", "mc"}
    if not isinstance(points, dict) or not required_points <= set(points):
        raise ValueError(f"invalid natal chart {path}: missing required chart points")
    if any(not is_number(value) or not 0 <= value < 360 for value in points.values()):
        raise ValueError(f"invalid natal chart {path}: point longitudes must be finite values in [0, 360)")
    retro = chart["retro"]
    if not isinstance(retro, dict) or any(not isinstance(retro.get(name), bool) for name in PLANETS):
        raise ValueError(f"invalid natal chart {path}: retro flags must be booleans")
    cusps = chart["cusps"]
    if (not isinstance(cusps, list) or len(cusps) != 12
            or any(not is_number(value) or not 0 <= value < 360 for value in cusps)):
        raise ValueError(f"invalid natal chart {path}: cusps must contain 12 finite longitudes")
    coordinates = chart.get("coordinates")
    if coordinates is not None:
        if not isinstance(coordinates, dict):
            raise ValueError(f"invalid natal chart {path}: coordinates must be an object")
        numeric_fields = ("longitude", "latitude", "distance_au", "longitude_speed",
                          "right_ascension", "declination")
        for name, record in coordinates.items():
            if not isinstance(record, dict) or any(not is_number(record.get(field)) for field in numeric_fields):
                raise ValueError(f"invalid natal chart {path}: malformed coordinates for {name}")
            if not isinstance(record.get("retrograde"), bool) or not isinstance(record.get("engine"), str):
                raise ValueError(f"invalid natal chart {path}: malformed coordinate metadata for {name}")
    return chart


def load_chart(path):
    try:
        with open(path, encoding="utf-8") as handle:
            chart = json.load(handle, parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))
    except FileNotFoundError:
        raise ValueError(f"natal chart file not found: {path}") from None
    except (OSError, json.JSONDecodeError, UnicodeDecodeError, ValueError) as exc:
        raise ValueError(f"cannot read natal chart {path}: {exc}") from None
    return validate_chart(chart, path)


def cmd_natal(args):
    chart = compute_natal(args)
    tz_spec = timezone_spec(args)
    rows = []
    body_names = list(chart["coordinates"])
    for name in body_names + ["asc", "mc"]:
        longitude = chart["points"][name]
        coordinate = chart["coordinates"].get(name, {})
        rows.append({"record_type": "point", "name": name, "longitude": longitude,
                     "formatted": fmt_lon(longitude), "retrograde": chart["retro"].get(name),
                     "house": None if name in ("asc", "mc") else natal_house_of(chart, longitude),
                     "latitude": coordinate.get("latitude"), "declination": coordinate.get("declination"),
                     "right_ascension": coordinate.get("right_ascension"), "engine": coordinate.get("engine")})
    rows.extend({"record_type": "cusp", "name": str(index), "longitude": longitude,
                 "formatted": fmt_lon(longitude), "retrograde": None, "house": index}
                for index, longitude in enumerate(chart["cusps"], 1))
    destination = args.save
    if getattr(args, "private_save", None):
        destination = private_chart_path(args.private_save)
    saved = save_chart(chart, destination, args.force) if destination else None
    if emit_structured(args, {"chart": chart, "saved_to": str(saved) if saved else None}, rows,
                       ["record_type", "name", "longitude", "formatted", "latitude", "declination",
                        "right_ascension", "retrograde", "house", "engine"]):
        return
    zone_label = tz_spec if isinstance(tz_spec, str) else f"UTC{fmt_tz(tz_spec)}"
    print(f"Natal chart  {args.date} {args.time} {zone_label}  lat {args.lat}  lon {args.lon}  ({args.hsys} houses)")
    print(f"Ephemeris: {source_label()}")
    for row in rows[:len(body_names) + 2]:
        retro = " R" if row["retrograde"] else ""
        house = "" if row["house"] is None else f"  house {row['house']}"
        print(f"  {row['name'].capitalize():9s} {row['formatted']:18s}{retro}{house}")
    print("  Cusps: " + "  ".join(f"{index}:{fmt_lon(value)}" for index, value in enumerate(chart["cusps"], 1)))
    for unavailable in chart["unavailable_bodies"]:
        print(f"  {unavailable['name'].capitalize()}: unavailable ({unavailable['reason']})")
    if saved:
        print(f"Saved private chart to {saved} (mode 0600)")


def cmd_snapshot(args):
    configure_ephemeris(args)
    chart = load_chart(args.natal)
    tz_spec = timezone_spec(args, chart)
    if args.orb_scale <= 0:
        raise ValueError("orb scale must be greater than zero")
    jd = jd_for_local(args.date, args.time, tz_spec, getattr(args, "fold", None))
    positions, aspect_rows = [], []
    selected = parse_names(getattr(args, "bodies", None) or ",".join(DEFAULT_CHART_BODIES), BODIES, "body")
    unavailable = []
    for name in selected:
        planet = BODIES[name]
        try:
            coordinate = coordinate_record(jd, name, planet)
        except swe.Error as exc:
            if name in PLANETS:
                raise
            unavailable.append({"name": name, "reason": sanitize_local_paths(exc)})
            continue
        longitude, speed = coordinate["longitude"], coordinate["longitude_speed"]
        positions.append({"record_type": "position", "planet": name, "longitude": longitude,
                          "formatted": fmt_lon(longitude), "retrograde": speed < 0,
                          "natal_house": natal_house_of(chart, longitude),
                          "latitude": coordinate["latitude"], "declination": coordinate["declination"],
                          "right_ascension": coordinate["right_ascension"], "engine": coordinate["engine"]})
        for target, natal_lon in chart["points"].items():
            for aspect, angle in ASPECTS.items():
                geometries = [angle] if angle in (0, 180) else [angle, -angle]
                for geometry in geometries:
                    signed = angdiff(angdiff(longitude, natal_lon), geometry)
                    if abs(signed) <= SNAPSHOT_ORBS[angle] * args.orb_scale:
                        aspect_rows.append({"record_type": "aspect", "planet": name, "aspect": aspect,
                                            "target": target, "orb": abs(signed),
                                            "trend": aspect_trend(signed, speed)})
    aspect_rows = sorted({(r["orb"], r["planet"], r["aspect"], r["target"], r["trend"]): r
                          for r in aspect_rows}.values(), key=lambda row: row["orb"])
    rows = positions + aspect_rows
    if emit_structured(args, {"at": jd_to_str(jd, tz_spec), "source": source_metadata(),
                              "positions": positions, "aspects": aspect_rows,
                              "unavailable_bodies": unavailable}, rows,
                       ["record_type", "planet", "longitude", "formatted", "latitude", "declination",
                        "right_ascension", "retrograde", "natal_house", "engine", "aspect", "target", "orb", "trend"]):
        return
    print(f"Transits at {jd_to_str(jd, tz_spec)}  vs natal {chart['meta']['date']}")
    print(f"Ephemeris: {source_label()}")
    for row in positions:
        print(f"  {row['planet'].capitalize():9s} {row['formatted']:18s} {'R' if row['retrograde'] else ' '}  natal house {row['natal_house']}")
    print("Aspects to natal (tightest first):")
    for row in aspect_rows:
        print(f"  {row['planet'].capitalize():9s} {row['aspect']:12s} natal {row['target'].capitalize():9s} orb {row['orb']:4.2f}°  {row['trend']}")
    for item in unavailable:
        print(f"  {item['name'].capitalize()}: unavailable ({item['reason']})")


def cmd_transits(args):
    configure_ephemeris(args)
    chart = load_chart(args.natal)
    tz_spec = timezone_spec(args, chart)
    jd0, jd1 = jd_range(args.start, args.end, tz_spec, getattr(args, "fold", None))
    movers = parse_names(args.planets, BODIES, "body")
    targets = parse_names(args.targets, chart["points"], "target") if args.targets else list(chart["points"])
    aspects = parse_names(args.aspects, ASPECTS, "aspect") if args.aspects else list(ASPECTS)
    events = []
    for index_mover, mover in enumerate(movers, 1):
        if not getattr(args, "quiet", False):
            print(f"Scanning {mover} ({index_mover}/{len(movers)})…", file=sys.stderr, flush=True)
        planet, step = BODIES[mover], SCAN_STEP.get(mover, 1.0)
        for target in targets:
            natal_lon = chart["points"][target]
            for aspect in aspects:
                angle = ASPECTS[aspect]
                for geometry in ([angle] if angle in (0, 180) else [angle, -angle]):
                    goal = (natal_lon + geometry) % 360.0
                    fn = lambda jd, goal=goal, planet=planet: angdiff(lon_of(jd, planet), goal)
                    visible = scan_crossings(fn, jd0, jd1, step)
                    if not visible:
                        continue
                    gap = SERIES_GAP.get(mover, 400.0)
                    extended = scan_crossings(fn, min(visible) - 4 * gap, max(visible) + 4 * gap, step)
                    for cluster in cluster_hits(extended, gap):
                        if not any(jd0 <= hit < jd1 for hit in cluster):
                            continue
                        for pass_index, hit in enumerate(cluster, 1):
                            if jd0 <= hit < jd1:
                                events.append({"jd_ut": hit, "datetime": jd_to_str(hit, tz_spec),
                                               "planet": mover, "aspect": aspect, "target": target,
                                               "retrograde": speed_of(hit, planet) < 0,
                                               "pass": pass_index, "passes": len(cluster)})
    events.sort(key=lambda row: row["jd_ut"])
    if emit_structured(args, {"start": args.start, "end": args.end, "source": source_metadata(),
                              "events": events}, events,
                       ["jd_ut", "datetime", "planet", "aspect", "target", "retrograde", "pass", "passes"]):
        return
    print(f"Exact transit hits {args.start} .. {args.end} (movers: {', '.join(movers)})")
    print(f"Ephemeris: {source_label()}")
    for row in events:
        tag = f"pass {row['pass']}/{row['passes']}" if row["passes"] > 1 else "single pass"
        print(f"  {row['datetime']}  {row['planet'].capitalize():9s} {row['aspect']:12s} natal {row['target'].capitalize():9s} {'R' if row['retrograde'] else 'D'}  ({tag})")
    if not events:
        print("  (none)")


def cmd_stations(args):
    configure_ephemeris(args)
    tz_spec = timezone_spec(args)
    jd0, jd1 = jd_range(args.start, args.end, tz_spec, getattr(args, "fold", None))
    movers = parse_names(args.planets, BODIES, "body")
    events = []
    for mover in movers:
        planet = BODIES[mover]
        fn = lambda jd, planet=planet: speed_of(jd, planet)
        for hit in scan_crossings(fn, jd0, jd1, 1.0):
            direction = "retrograde" if speed_of(hit + 0.5, planet) < 0 else "direct"
            longitude = lon_of(hit, planet)
            events.append({"jd_ut": hit, "datetime": jd_to_str(hit, tz_spec), "planet": mover,
                           "direction": direction, "longitude": longitude, "formatted": fmt_lon(longitude)})
    events.sort(key=lambda row: row["jd_ut"])
    if emit_structured(args, {"start": args.start, "end": args.end, "source": source_metadata(),
                              "events": events}, events,
                       ["jd_ut", "datetime", "planet", "direction", "longitude", "formatted"]):
        return
    print(f"Stations {args.start} .. {args.end}")
    print(f"Ephemeris: {source_label()}")
    for row in events:
        print(f"  {row['datetime']}  {row['planet'].capitalize():9s} stations {row['direction']:10s} @ {row['formatted']}")
    if not events:
        print("  (none)")


def cmd_lunations(args):
    configure_ephemeris(args)
    chart = load_chart(args.natal) if args.natal else None
    tz_spec = timezone_spec(args, chart)
    if args.orb <= 0:
        raise ValueError("orb must be greater than zero")
    jd0, jd1 = jd_range(args.start, args.end, tz_spec, getattr(args, "fold", None))
    events = []
    for kind, angle in (("New Moon", 0), ("Full Moon", 180)):
        fn = lambda jd, angle=angle: angdiff(angdiff(lon_of(jd, swe.MOON), lon_of(jd, swe.SUN)), angle)
        for hit in scan_crossings(fn, jd0, jd1, 0.25):
            longitude = lon_of(hit, swe.MOON)
            near_target, near_orb = None, None
            house = natal_house_of(chart, longitude) if chart else None
            if chart:
                near = sorted((abs(angdiff(longitude, value)), name) for name, value in chart["points"].items()
                              if abs(angdiff(longitude, value)) <= args.orb)
                if near:
                    near_orb, near_target = near[0]
            events.append({"jd_ut": hit, "datetime": jd_to_str(hit, tz_spec), "kind": kind,
                           "longitude": longitude, "formatted": fmt_lon(longitude),
                           "natal_target": near_target, "orb": near_orb, "natal_house": house})
    events.sort(key=lambda row: row["jd_ut"])
    if emit_structured(args, {"start": args.start, "end": args.end, "source": source_metadata(),
                              "events": events}, events,
                       ["jd_ut", "datetime", "kind", "longitude", "formatted", "natal_target", "orb", "natal_house"]):
        return
    print(f"Lunations {args.start} .. {args.end}")
    print(f"Ephemeris: {source_label()}")
    for row in events:
        note = f"  ** on natal {row['natal_target'].capitalize()} (orb {row['orb']:.2f}°)" if row["natal_target"] else ""
        if row["natal_house"]:
            note += f"  [natal house {row['natal_house']}]"
        print(f"  {row['datetime']}  {row['kind']:9s} @ {row['formatted']}{note}")
    if not events:
        print("  (none)")


def cmd_ingresses(args):
    configure_ephemeris(args)
    chart = load_chart(args.natal) if args.natal else None
    if args.kind in ("houses", "both") and chart is None:
        raise ValueError("house crossings require --natal")
    tz_spec = timezone_spec(args, chart)
    jd0, jd1 = jd_range(args.start, args.end, tz_spec, getattr(args, "fold", None))
    movers = parse_names(args.bodies, BODIES, "body")
    events = []
    for mover in movers:
        body = BODIES[mover]
        step = SCAN_STEP.get(mover, 0.5)
        if args.kind in ("signs", "both"):
            for sign_index in range(12):
                boundary = sign_index * 30.0
                fn = lambda jd, boundary=boundary, body=body: angdiff(lon_of(jd, body), boundary)
                for hit in scan_crossings(fn, jd0, jd1, step):
                    before = int(lon_of(hit - 0.01, body) // 30) % 12
                    after = int(lon_of(hit + 0.01, body) // 30) % 12
                    if before == after:
                        continue
                    events.append({"jd_ut": hit, "datetime": jd_to_str(hit, tz_spec),
                                   "kind": "sign", "body": mover, "from": SIGNS[before],
                                   "to": SIGNS[after], "retrograde": speed_of(hit, body) < 0,
                                   "longitude": lon_of(hit, body), "cusp": None})
        if args.kind in ("houses", "both"):
            for cusp_index, boundary in enumerate(chart["cusps"], 1):
                fn = lambda jd, boundary=boundary, body=body: angdiff(lon_of(jd, body), boundary)
                for hit in scan_crossings(fn, jd0, jd1, step):
                    before = natal_house_of(chart, lon_of(hit - 0.01, body))
                    after = natal_house_of(chart, lon_of(hit + 0.01, body))
                    if before == after:
                        continue
                    events.append({"jd_ut": hit, "datetime": jd_to_str(hit, tz_spec),
                                   "kind": "house", "body": mover, "from": before, "to": after,
                                   "retrograde": speed_of(hit, body) < 0,
                                   "longitude": lon_of(hit, body), "cusp": cusp_index})
    events.sort(key=lambda row: (row["jd_ut"], row["kind"], row["body"]))
    if emit_structured(args, {"start": args.start, "end": args.end, "source": source_metadata(),
                              "events": events}, events,
                       ["jd_ut", "datetime", "kind", "body", "from", "to", "retrograde",
                        "longitude", "cusp"]):
        return
    print(f"Sign ingresses and house crossings {args.start} .. {args.end}")
    print(f"Ephemeris: {source_label()}")
    for row in events:
        destination = f"house {row['to']}" if row["kind"] == "house" else row["to"]
        origin = f"house {row['from']}" if row["kind"] == "house" else row["from"]
        print(f"  {row['datetime']}  {row['body'].capitalize():10s} {origin} → {destination}"
              f"  {'R' if row['retrograde'] else 'D'}")
    if not events:
        print("  (none)")


def eclipse_type(flags, solar):
    checks = [
        (swe.ECL_ANNULAR_TOTAL, "hybrid"),
        (swe.ECL_TOTAL, "total"),
        (swe.ECL_ANNULAR, "annular"),
        (swe.ECL_PARTIAL, "partial"),
    ]
    if not solar:
        checks.append((swe.ECL_PENUMBRAL, "penumbral"))
    for bit, label in checks:
        if flags & bit:
            return label
    return "unspecified"


def cmd_eclipses(args):
    configure_ephemeris(args)
    chart = load_chart(args.natal) if args.natal else None
    tz_spec = timezone_spec(args, chart)
    if args.orb <= 0:
        raise ValueError("orb must be greater than zero")
    jd0, jd1 = jd_range(args.start, args.end, tz_spec, getattr(args, "fold", None))
    flags = ACTIVE_FLAG & ~swe.FLG_SPEED
    events = []
    for family in ("solar", "lunar"):
        if args.kind not in ("both", family):
            continue
        cursor = jd0 - 1e-6
        while True:
            if family == "solar":
                returned, times = swe.sol_eclipse_when_glob(cursor, flags)
                body = swe.SUN
            else:
                returned, times = swe.lun_eclipse_when(cursor, flags)
                body = swe.MOON
            hit = times[0]
            if hit >= jd1:
                break
            if hit >= jd0:
                longitude = lon_of(hit, body)
                near_target, near_orb = None, None
                house = natal_house_of(chart, longitude) if chart else None
                if chart:
                    near = sorted((abs(angdiff(longitude, value)), name)
                                  for name, value in chart["points"].items()
                                  if abs(angdiff(longitude, value)) <= args.orb)
                    if near:
                        near_orb, near_target = near[0]
                events.append({"jd_ut": hit, "datetime": jd_to_str(hit, tz_spec),
                               "family": family, "type": eclipse_type(returned, family == "solar"),
                               "longitude": longitude, "formatted": fmt_lon(longitude),
                               "natal_target": near_target, "orb": near_orb,
                               "natal_house": house,
                               "begin": jd_to_str(times[2], tz_spec) if times[2] else None,
                               "end": jd_to_str(times[3], tz_spec) if times[3] else None})
            cursor = hit + 1.0
    events.sort(key=lambda row: row["jd_ut"])
    if emit_structured(args, {"start": args.start, "end": args.end, "source": source_metadata(),
                              "events": events}, events,
                       ["jd_ut", "datetime", "family", "type", "longitude", "formatted",
                        "natal_target", "orb", "natal_house", "begin", "end"]):
        return
    print(f"Eclipses {args.start} .. {args.end}")
    print(f"Ephemeris: {source_label()}")
    for row in events:
        note = f"  on natal {row['natal_target'].capitalize()} ({row['orb']:.2f}°)" if row["natal_target"] else ""
        if row["natal_house"]:
            note += f"  [natal house {row['natal_house']}]"
        print(f"  {row['datetime']}  {row['type'].capitalize():10s} {row['family']} eclipse"
              f" @ {row['formatted']}{note}")
    if not events:
        print("  (none)")


def cmd_progressions(args):
    configure_ephemeris(args)
    chart = load_chart(args.natal)
    tz_spec = timezone_spec(args, chart)
    jd_natal = chart["meta"]["jd_ut"]
    jd_event = jd_for_local(args.at, "12:00", tz_spec, getattr(args, "fold", None))
    years = (jd_event - jd_natal) / 365.2422
    jd_prog = jd_natal + years
    positions = [{"record_type": "position", "planet": name, "longitude": lon_of(jd_prog, PLANETS[name]),
                  "formatted": fmt_lon(lon_of(jd_prog, PLANETS[name]))}
                 for name in ("sun", "moon", "mercury", "venus", "mars")]
    prog = {row["planet"]: row["longitude"] for row in positions}
    phase = (prog["moon"] - prog["sun"]) % 360.0
    aspects = []
    for planet, longitude in prog.items():
        for target, natal_lon in chart["points"].items():
            for aspect, angle in ASPECTS.items():
                for geometry in ([angle] if angle in (0, 180) else [angle, -angle]):
                    orb = abs(angdiff(angdiff(longitude, natal_lon), geometry))
                    if orb <= 1.0:
                        aspects.append({"record_type": "aspect", "planet": planet, "aspect": aspect,
                                        "target": target, "orb": orb})
    if emit_structured(args, {"date": args.at, "age": years, "phase": phase,
                              "source": source_metadata(),
                              "positions": positions, "aspects": aspects}, positions + aspects,
                       ["record_type", "planet", "longitude", "formatted", "aspect", "target", "orb"]):
        return
    print(f"Secondary progressions for {args.at}  (age {years:.2f})")
    print(f"Ephemeris: {source_label()}")
    for row in positions:
        print(f"  prog {row['planet'].capitalize():8s} {row['formatted']}")
    print(f"  progressed lunation phase: {phase:.1f}° (0=prog New Moon, 90=first quarter, 180=prog Full Moon)")
    print("Progressed aspects to natal (orb <= 1°):")
    for row in aspects:
        print(f"  prog {row['planet'].capitalize():8s} {row['aspect']:12s} natal {row['target'].capitalize():9s} orb {row['orb']:.2f}°")
    if not aspects:
        print("  (none)")


def add_timezone(parser, required=False, default=None):
    group = parser.add_mutually_exclusive_group(required=required)
    group.add_argument("--tz", type=float, default=default, help="fixed UTC offset in hours")
    group.add_argument("--tz-name", help="IANA timezone, e.g. Asia/Shanghai")
    parser.add_argument("--fold", type=int, choices=(0, 1), help="side of an ambiguous DST time")


def add_output(parser):
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--json", action="store_true", help="emit JSON")
    group.add_argument("--csv", action="store_true", help="emit CSV")


def add_ephemeris_options(parser):
    parser.add_argument("--engine", choices=tuple(ENGINE_FLAGS), default="auto",
                        help="auto prefers Swiss files and falls back to Moshier")
    parser.add_argument("--ephe-path", help="directory containing Swiss Ephemeris .se1 files")
    parser.add_argument("--jpl-file", help="JPL binary ephemeris used with --engine jpl")


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", action="version", version=f"AstroLab {VERSION}")
    sub = parser.add_subparsers(dest="cmd", required=True)

    natal = sub.add_parser("natal", help="compute natal chart")
    natal.add_argument("--date", required=True)
    natal.add_argument("--time", required=True)
    add_timezone(natal, required=True)
    natal.add_argument("--lat", type=float, required=True)
    natal.add_argument("--lon", type=float, required=True)
    natal.add_argument("--hsys", default="P")
    natal.add_argument("--bodies", help="comma list; core planets are always retained")
    save = natal.add_mutually_exclusive_group()
    save.add_argument("--save")
    save.add_argument("--private-save", metavar="SESSION_ID")
    natal.add_argument("--force", action="store_true")
    add_ephemeris_options(natal)
    add_output(natal)
    natal.set_defaults(func=cmd_natal)

    snapshot = sub.add_parser("snapshot", help="transits at a moment vs natal")
    snapshot.add_argument("--natal", required=True)
    snapshot.add_argument("--date", required=True)
    snapshot.add_argument("--time", required=True)
    add_timezone(snapshot)
    snapshot.add_argument("--orb-scale", type=float, default=1.0)
    snapshot.add_argument("--bodies", help="comma list of displayed bodies")
    add_ephemeris_options(snapshot)
    add_output(snapshot)
    snapshot.set_defaults(func=cmd_snapshot)

    transits = sub.add_parser("transits", help="scan a date range for exact aspect hits")
    transits.add_argument("--natal", required=True)
    transits.add_argument("--start", required=True)
    transits.add_argument("--end", required=True)
    transits.add_argument("--planets", default=",".join(DEFAULT_TRANSITERS))
    transits.add_argument("--targets")
    transits.add_argument("--aspects")
    transits.add_argument("--quiet", action="store_true")
    add_ephemeris_options(transits)
    add_timezone(transits)
    add_output(transits)
    transits.set_defaults(func=cmd_transits)

    stations = sub.add_parser("stations", help="retrograde/direct stations")
    stations.add_argument("--start", required=True)
    stations.add_argument("--end", required=True)
    stations.add_argument("--planets", default="mercury,venus,mars,jupiter,saturn,uranus,neptune,pluto")
    add_ephemeris_options(stations)
    add_timezone(stations, default=0.0)
    add_output(stations)
    stations.set_defaults(func=cmd_stations)

    lunations = sub.add_parser("lunations", help="new/full moons and natal hits")
    lunations.add_argument("--start", required=True)
    lunations.add_argument("--end", required=True)
    lunations.add_argument("--natal")
    lunations.add_argument("--orb", type=float, default=3.0)
    add_ephemeris_options(lunations)
    add_timezone(lunations)
    add_output(lunations)
    lunations.set_defaults(func=cmd_lunations)

    progressions = sub.add_parser("progressions", help="secondary progressions")
    progressions.add_argument("--natal", required=True)
    progressions.add_argument("--at", required=True)
    add_ephemeris_options(progressions)
    add_timezone(progressions)
    add_output(progressions)
    progressions.set_defaults(func=cmd_progressions)

    ingresses = sub.add_parser("ingresses", help="sign ingresses and natal house crossings")
    ingresses.add_argument("--start", required=True)
    ingresses.add_argument("--end", required=True)
    ingresses.add_argument("--bodies", default=",".join(PLANETS))
    ingresses.add_argument("--kind", choices=("signs", "houses", "both"), default="signs")
    ingresses.add_argument("--natal", help="required for house crossings")
    add_timezone(ingresses)
    add_ephemeris_options(ingresses)
    add_output(ingresses)
    ingresses.set_defaults(func=cmd_ingresses)

    eclipses = sub.add_parser("eclipses", help="solar and lunar eclipses")
    eclipses.add_argument("--start", required=True)
    eclipses.add_argument("--end", required=True)
    eclipses.add_argument("--kind", choices=("solar", "lunar", "both"), default="both")
    eclipses.add_argument("--natal")
    eclipses.add_argument("--orb", type=float, default=3.0)
    add_timezone(eclipses)
    add_ephemeris_options(eclipses)
    add_output(eclipses)
    eclipses.set_defaults(func=cmd_eclipses)

    ephemeris = sub.add_parser("ephemeris", help="inspect or download official ephemeris data")
    ephemeris.add_argument("action", choices=("status", "download"))
    ephemeris.add_argument("--destination")
    ephemeris.add_argument("--force", action="store_true")
    add_output(ephemeris)
    ephemeris.set_defaults(func=cmd_ephemeris)
    return parser


def main():
    configure_output_encoding()
    parser = build_parser()
    args = parser.parse_args()
    try:
        args.func(args)
    except (ValueError, OSError, swe.Error) as exc:
        parser.error(sanitize_local_paths(exc))


if __name__ == "__main__":
    main()
