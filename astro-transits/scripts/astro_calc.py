#!/usr/bin/env python3
"""astro_calc.py — precise astrological ephemeris calculations for transit analysis.

Built on pyswisseph (Swiss Ephemeris) in Moshier mode: no ephemeris data
files needed, accuracy well under an arcminute for 1800-2200 CE — more than
enough for astrological work.

Subcommands:
  natal         compute a natal chart (positions, houses), optionally save JSON
  snapshot      transit positions at a moment + aspects to a natal chart
  transits      scan a date range for exact transit-to-natal aspect hits
                (finds ALL passes of retrograde loops, i.e. triple passes)
  stations      find retrograde/direct stations in a date range
  lunations     find New/Full Moons, flagging those near natal points
  progressions  secondary progressed positions + aspects to natal

Typical workflow:
  1. astro_calc.py natal --date 1990-05-15 --time 14:30 --tz 8 \
       --lat 39.9 --lon 116.4 --save chart.json
  2. astro_calc.py transits --natal chart.json --start 2026-01-01 --end 2027-12-31
  3. astro_calc.py stations --start 2026-01-01 --end 2027-01-01
  4. astro_calc.py lunations --natal chart.json --start 2026-07-01 --end 2026-08-01
  5. astro_calc.py progressions --natal chart.json --at 2026-07-14

License: AGPL-3.0 (required by the Swiss Ephemeris license of pyswisseph).
"""
import argparse
import json
import sys

try:
    import swisseph as swe
except ImportError:
    sys.exit("pyswisseph is required:  pip install pyswisseph")

FLAG = swe.FLG_MOSEPH | swe.FLG_SPEED

PLANETS = {
    'sun': swe.SUN, 'moon': swe.MOON, 'mercury': swe.MERCURY,
    'venus': swe.VENUS, 'mars': swe.MARS, 'jupiter': swe.JUPITER,
    'saturn': swe.SATURN, 'uranus': swe.URANUS, 'neptune': swe.NEPTUNE,
    'pluto': swe.PLUTO,
}
SIGNS = ['Aries', 'Taurus', 'Gemini', 'Cancer', 'Leo', 'Virgo', 'Libra',
         'Scorpio', 'Sagittarius', 'Capricorn', 'Aquarius', 'Pisces']
ASPECTS = {'conjunction': 0, 'sextile': 60, 'square': 90,
           'trine': 120, 'opposition': 180}
# default orbs (degrees) for the snapshot command
SNAPSHOT_ORBS = {0: 3.0, 60: 2.0, 90: 3.0, 120: 3.0, 180: 3.0}
# daily-motion-aware scan steps (days) so fast planets aren't missed
SCAN_STEP = {'sun': 0.5, 'moon': 0.05, 'mercury': 0.25, 'venus': 0.5,
             'mars': 0.5, 'jupiter': 1.0, 'saturn': 1.0, 'uranus': 2.0,
             'neptune': 2.0, 'pluto': 2.0}
DEFAULT_TRANSITERS = ['mars', 'jupiter', 'saturn', 'uranus', 'neptune', 'pluto']


# ---------------------------------------------------------------- utilities

def fmt_lon(lon):
    sign = int(lon // 30) % 12
    deg = lon % 30
    minutes = int(round((deg - int(deg)) * 60))
    d = int(deg)
    if minutes == 60:
        d, minutes = d + 1, 0
    if d == 30:  # rounding carried past the sign boundary
        sign, d = (sign + 1) % 12, 0
    return f"{SIGNS[sign]} {d}°{minutes:02d}'"


def angdiff(a, b):
    """signed shortest angular distance a-b in (-180, 180]"""
    return (a - b + 180.0) % 360.0 - 180.0


def lon_of(jd, planet):
    return swe.calc_ut(jd, planet, FLAG)[0][0]


def speed_of(jd, planet):
    return swe.calc_ut(jd, planet, FLAG)[0][3]


def jd_from_local(date_str, time_str, tz):
    y, m, d = (int(x) for x in date_str.split('-'))
    parts = time_str.split(':')
    hour = int(parts[0]) + int(parts[1]) / 60.0 + (int(parts[2]) if len(parts) > 2 else 0) / 3600.0
    return swe.julday(y, m, d, hour - tz)


def jd_to_str(jd, tz):
    y, m, d, h = swe.revjul(jd + tz / 24.0)
    hh = int(h)
    mm = int(round((h - hh) * 60))
    if mm == 60:
        hh, mm = hh + 1, 0
    tzs = f"{'+' if tz >= 0 else '-'}{abs(tz):04.1f}".replace('.0', ':00')
    return f"{y}-{m:02d}-{d:02d} {hh:02d}:{mm:02d} UTC{tzs}"


def bisect_crossing(fn, a, b, iters=48):
    """fn is signed and changes sign between a and b; return the zero."""
    fa = fn(a)
    for _ in range(iters):
        m = (a + b) / 2.0
        fm = fn(m)
        if (fa < 0) != (fm < 0):
            b = m
        else:
            a, fa = m, fm
    return (a + b) / 2.0


def scan_crossings(fn, jd0, jd1, step):
    """find all zeros of a signed angular function over [jd0, jd1].
    fn must be continuous mod 360; jumps >=180 are treated as wraparound,
    not crossings."""
    hits = []
    jd, prev = jd0, fn(jd0)
    while jd < jd1:
        jdn = min(jd + step, jd1)
        cur = fn(jdn)
        if (prev < 0) != (cur < 0) and abs(prev - cur) < 180.0:
            hits.append(bisect_crossing(fn, jd, jdn))
        jd, prev = jdn, cur
    return hits


# ------------------------------------------------------------------- natal

def compute_natal(args):
    jd = jd_from_local(args.date, args.time, args.tz)
    chart = {
        'meta': {'date': args.date, 'time': args.time, 'tz': args.tz,
                 'lat': args.lat, 'lon': args.lon, 'hsys': args.hsys,
                 'jd_ut': jd},
        'points': {},
        'retro': {},
    }
    for name, p in PLANETS.items():
        pos = swe.calc_ut(jd, p, FLAG)[0]
        chart['points'][name] = pos[0]
        chart['retro'][name] = pos[3] < 0
    cusps, ascmc = swe.houses(jd, args.lat, args.lon, args.hsys.encode())
    chart['points']['asc'] = ascmc[0]
    chart['points']['mc'] = ascmc[1]
    chart['cusps'] = list(cusps)
    return chart


def natal_house_of(chart, lon):
    """which natal house a longitude falls in (1-12)"""
    cusps = chart['cusps']
    for i in range(12):
        a, b = cusps[i], cusps[(i + 1) % 12]
        span = (b - a) % 360.0
        if (lon - a) % 360.0 < span:
            return i + 1
    return 12


def cmd_natal(args):
    chart = compute_natal(args)
    print(f"Natal chart  {args.date} {args.time} UTC{args.tz:+.1f}  "
          f"lat {args.lat}  lon {args.lon}  ({args.hsys} houses)")
    for name in list(PLANETS) + ['asc', 'mc']:
        lon = chart['points'][name]
        retro = ' R' if chart['retro'].get(name) else ''
        house = '' if name in ('asc', 'mc') else f"  house {natal_house_of(chart, lon)}"
        print(f"  {name.capitalize():9s} {fmt_lon(lon):18s}{retro}{house}")
    print("  Cusps: " + "  ".join(f"{i+1}:{fmt_lon(c)}" for i, c in enumerate(chart['cusps'])))
    if args.save:
        with open(args.save, 'w') as f:
            json.dump(chart, f, indent=1)
        print(f"Saved to {args.save}")


# ---------------------------------------------------------------- snapshot

def load_chart(path):
    with open(path) as f:
        return json.load(f)


def cmd_snapshot(args):
    chart = load_chart(args.natal)
    tz = args.tz if args.tz is not None else chart['meta']['tz']
    jd = jd_from_local(args.date, args.time, tz)
    print(f"Transits at {jd_to_str(jd, tz)}  vs natal {chart['meta']['date']}")
    rows = []
    for name, p in PLANETS.items():
        pos = swe.calc_ut(jd, p, FLAG)[0]
        lon, spd = pos[0], pos[3]
        retro = 'R' if spd < 0 else ' '
        house = natal_house_of(chart, lon)
        print(f"  {name.capitalize():9s} {fmt_lon(lon):18s} {retro}  natal house {house}")
        for tname, tlon in chart['points'].items():
            for aname, angle in ASPECTS.items():
                orb_limit = SNAPSHOT_ORBS[angle] * (args.orb_scale or 1.0)
                d = angdiff(angdiff(lon, tlon), angle) if angle != 0 else angdiff(lon, tlon)
                # check both +angle and -angle geometries
                for signed in ({d} if angle in (0, 180) else
                               {angdiff(angdiff(lon, tlon), angle),
                                angdiff(angdiff(lon, tlon), -angle)}):
                    if abs(signed) <= orb_limit:
                        # applying if orb shrinks tomorrow
                        lon2 = lon_of(jd + 1, p)
                        d2 = min(abs(angdiff(angdiff(lon2, tlon), angle)),
                                 abs(angdiff(angdiff(lon2, tlon), -angle)))
                        trend = 'applying' if d2 < abs(signed) else 'separating'
                        rows.append((abs(signed), name, aname, tname, trend))
    print("Aspects to natal (tightest first):")
    for orb, name, aname, tname, trend in sorted(set(rows)):
        print(f"  {name.capitalize():9s} {aname:12s} natal {tname.capitalize():9s} "
              f"orb {orb:4.2f}°  {trend}")


# ---------------------------------------------------------------- transits

def cmd_transits(args):
    chart = load_chart(args.natal)
    tz = args.tz if args.tz is not None else chart['meta']['tz']
    jd0 = jd_from_local(args.start, '00:00', tz)
    jd1 = jd_from_local(args.end, '00:00', tz)
    movers = [m.strip().lower() for m in args.planets.split(',')]
    targets = ([t.strip().lower() for t in args.targets.split(',')]
               if args.targets else list(chart['points']))
    aspects = ([a.strip().lower() for a in args.aspects.split(',')]
               if args.aspects else list(ASPECTS))
    events = []
    for mover in movers:
        planet = PLANETS[mover]
        step = SCAN_STEP[mover]
        for tname in targets:
            tlon = chart['points'][tname]
            for aname in aspects:
                angle = ASPECTS[aname]
                geometries = [angle] if angle in (0, 180) else [angle, -angle]
                for g in geometries:
                    goal = (tlon + g) % 360.0
                    fn = lambda jd, goal=goal, planet=planet: angdiff(lon_of(jd, planet), goal)
                    for hit in scan_crossings(fn, jd0, jd1, step):
                        retro = speed_of(hit, planet) < 0
                        events.append((hit, mover, aname, tname, retro))
    # number the passes within each (mover, aspect, target) series
    events.sort()
    counts, seen = {}, {}
    for _, m, a, t, _ in events:
        counts[(m, a, t)] = counts.get((m, a, t), 0) + 1
    print(f"Exact transit hits {args.start} .. {args.end} "
          f"(movers: {', '.join(movers)})")
    for jd, m, a, t, retro in events:
        key = (m, a, t)
        seen[key] = seen.get(key, 0) + 1
        tag = f"pass {seen[key]}/{counts[key]}" if counts[key] > 1 else "single pass"
        print(f"  {jd_to_str(jd, tz)}  {m.capitalize():9s} {a:12s} "
              f"natal {t.capitalize():9s} {'R' if retro else 'D'}  ({tag})")
    if not events:
        print("  (none)")


# ---------------------------------------------------------------- stations

def cmd_stations(args):
    tz = args.tz
    jd0 = jd_from_local(args.start, '00:00', tz)
    jd1 = jd_from_local(args.end, '00:00', tz)
    movers = [m.strip().lower() for m in args.planets.split(',')]
    print(f"Stations {args.start} .. {args.end}")
    for mover in movers:
        planet = PLANETS[mover]
        fn = lambda jd, planet=planet: speed_of(jd, planet)
        for hit in scan_crossings(fn, jd0, jd1, 1.0):
            kind = 'stations retrograde' if speed_of(hit + 0.5, planet) < 0 else 'stations direct'
            print(f"  {jd_to_str(hit, tz)}  {mover.capitalize():9s} {kind:19s} "
                  f"@ {fmt_lon(lon_of(hit, planet))}")


# --------------------------------------------------------------- lunations

def cmd_lunations(args):
    chart = load_chart(args.natal) if args.natal else None
    tz = args.tz if args.tz is not None else (chart['meta']['tz'] if chart else 0.0)
    jd0 = jd_from_local(args.start, '00:00', tz)
    jd1 = jd_from_local(args.end, '00:00', tz)
    print(f"Lunations {args.start} .. {args.end}")
    for kind, angle in (('New Moon ', 0), ('Full Moon', 180)):
        fn = lambda jd, angle=angle: angdiff(
            angdiff(lon_of(jd, swe.MOON), lon_of(jd, swe.SUN)), angle)
        for hit in scan_crossings(fn, jd0, jd1, 0.25):
            mlon = lon_of(hit, swe.MOON)
            note = ''
            if chart:
                near = [(abs(angdiff(mlon, plon)), pname)
                        for pname, plon in chart['points'].items()
                        if abs(angdiff(mlon, plon)) <= args.orb]
                if near:
                    orb, pname = min(near)
                    note = f"  ** on natal {pname.capitalize()} (orb {orb:.2f}°)"
                note += f"  [natal house {natal_house_of(chart, mlon)}]"
            print(f"  {jd_to_str(hit, tz)}  {kind} @ {fmt_lon(mlon)}{note}")


# ------------------------------------------------------------ progressions

def cmd_progressions(args):
    chart = load_chart(args.natal)
    tz = chart['meta']['tz']
    jd_natal = chart['meta']['jd_ut']
    jd_event = jd_from_local(args.at, '12:00', tz)
    years = (jd_event - jd_natal) / 365.2422
    jd_prog = jd_natal + years  # day-for-a-year
    print(f"Secondary progressions for {args.at}  (age {years:.2f})")
    prog = {}
    for name in ('sun', 'moon', 'mercury', 'venus', 'mars'):
        prog[name] = lon_of(jd_prog, PLANETS[name])
        print(f"  prog {name.capitalize():8s} {fmt_lon(prog[name])}")
    # progressed Sun-Moon phase
    phase = (prog['moon'] - prog['sun']) % 360.0
    print(f"  progressed lunation phase: {phase:.1f}° "
          f"(0=prog New Moon, 90=first quarter, 180=prog Full Moon)")
    print("Progressed aspects to natal (orb <= 1°):")
    found = False
    for pname, plon in prog.items():
        for tname, tlon in chart['points'].items():
            for aname, angle in ASPECTS.items():
                for g in ([angle] if angle in (0, 180) else [angle, -angle]):
                    d = angdiff(angdiff(plon, tlon), g)
                    if abs(d) <= 1.0:
                        print(f"  prog {pname.capitalize():8s} {aname:12s} "
                              f"natal {tname.capitalize():9s} orb {abs(d):.2f}°")
                        found = True
    if not found:
        print("  (none)")


# --------------------------------------------------------------------- cli

def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)

    n = sub.add_parser('natal', help='compute natal chart')
    n.add_argument('--date', required=True, help='YYYY-MM-DD (local)')
    n.add_argument('--time', required=True, help='HH:MM local')
    n.add_argument('--tz', type=float, required=True, help='UTC offset hours, e.g. 8')
    n.add_argument('--lat', type=float, required=True)
    n.add_argument('--lon', type=float, required=True, help='east positive')
    n.add_argument('--hsys', default='P', help='house system letter (P=Placidus, W=whole sign...)')
    n.add_argument('--save', help='write chart JSON here')
    n.set_defaults(func=cmd_natal)

    s = sub.add_parser('snapshot', help='transits at a moment vs natal')
    s.add_argument('--natal', required=True, help='chart JSON from `natal --save`')
    s.add_argument('--date', required=True)
    s.add_argument('--time', required=True)
    s.add_argument('--tz', type=float, help='defaults to natal tz')
    s.add_argument('--orb-scale', type=float, default=1.0)
    s.set_defaults(func=cmd_snapshot)

    t = sub.add_parser('transits', help='scan date range for exact aspect hits')
    t.add_argument('--natal', required=True)
    t.add_argument('--start', required=True, help='YYYY-MM-DD')
    t.add_argument('--end', required=True)
    t.add_argument('--planets', default=','.join(DEFAULT_TRANSITERS),
                   help='comma list of transiting planets')
    t.add_argument('--targets', help='comma list of natal points (default: all)')
    t.add_argument('--aspects', help='comma list of aspect names (default: all five)')
    t.add_argument('--tz', type=float, help='defaults to natal tz')
    t.set_defaults(func=cmd_transits)

    st = sub.add_parser('stations', help='retrograde/direct stations')
    st.add_argument('--start', required=True)
    st.add_argument('--end', required=True)
    st.add_argument('--planets', default='mercury,venus,mars,jupiter,saturn')
    st.add_argument('--tz', type=float, default=0.0)
    st.set_defaults(func=cmd_stations)

    lu = sub.add_parser('lunations', help='new/full moons, flag hits on natal points')
    lu.add_argument('--start', required=True)
    lu.add_argument('--end', required=True)
    lu.add_argument('--natal', help='optional chart JSON to flag natal hits')
    lu.add_argument('--orb', type=float, default=3.0)
    lu.add_argument('--tz', type=float, help='defaults to natal tz or 0')
    lu.set_defaults(func=cmd_lunations)

    pr = sub.add_parser('progressions', help='secondary progressions')
    pr.add_argument('--natal', required=True)
    pr.add_argument('--at', required=True, help='YYYY-MM-DD')
    pr.set_defaults(func=cmd_progressions)

    args = ap.parse_args()
    args.func(args)


if __name__ == '__main__':
    main()
