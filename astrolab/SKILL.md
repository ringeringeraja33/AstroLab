---
name: astrolab
description: >
  Deep astrological transit analysis backed by real Swiss Ephemeris computation
  instead of recycled horoscope text. Use this skill whenever the user asks
  about their birth chart, natal chart, transits, predictive astrology,
  house placements, house rulers, annual forecasts, secondary progressions,
  eclipses, sign ingresses, house crossings, lunar nodes, Chiron, Lilith,
  retrogrades, "when will Saturn/Pluto/... hit
  my X", lunar returns, new/full moons relative to their chart, or pastes a
  URL from an astrology site (ixingpan, astro.com, astro-seek, etc.). Also use
  it when the user asks to time events astrologically ("what does this month
  look like", "pick a date for..."). It computes exact hit dates, retrograde
  multi-pass transits, stations, ingresses, eclipses, and progressions — always
  prefer it over answering astrology questions from memory, because recalled
  planetary positions and dates are unreliable.
---

# AstroLab

AstroLab turns astrology questions into ephemeris computations. The core
principle: **never state a planetary position or transit date from memory** —
LLM recall of ephemeris data is unreliable — and **never pad an analysis with
generic cookbook text** the user could read on any horoscope site. Everything
you assert should either come out of `${CLAUDE_SKILL_DIR}/scripts/astro_calc.py` or be an
interpretive synthesis you can point back to computed data.

## Setup (once per machine)

Install the bounded runtime dependency with `python -m pip install "pyswisseph>=2.10,<3"`.
Check the data backend with `python "${CLAUDE_SKILL_DIR}/scripts/astro_calc.py" ephemeris status`.
If official data files are missing and network access is allowed, run
`python "${CLAUDE_SKILL_DIR}/scripts/astro_calc.py" ephemeris download` once.
In PowerShell, use `$env:CLAUDE_SKILL_DIR` in place of `${CLAUDE_SKILL_DIR}`.
This downloads the current compressed planet, Moon, main-asteroid, and fixed-star
files from the official Astrodienst repository, records hashes, and enables
Chiron plus strict `--engine swiss` calculations. Without them, `auto` uses
Moshier where necessary and reports the actual backend.

## Workflow

### 1. Get birth data, compute the natal chart, VERIFY it

You need: birth date, local time, an IANA timezone or UTC offset, latitude,
and longitude. Prefer an IANA name because it applies historical daylight
saving rules. If the
user pastes a chart URL (ixingpan, astro.com...), fetch it and extract both
the birth data and the listed positions.

On macOS or Linux:

```bash
python "${CLAUDE_SKILL_DIR}/scripts/astro_calc.py" natal --date 2000-11-09 --time 04:55 --tz-name Asia/Shanghai --lat 40.8 --lon 111.68 --private-save "${CLAUDE_SESSION_ID}" --force
```

On Windows PowerShell:

```powershell
python "$env:CLAUDE_SKILL_DIR/scripts/astro_calc.py" natal --date 2000-11-09 --time 04:55 --tz-name Asia/Shanghai --lat 40.8 --lon 111.68 --private-save "$env:CLAUDE_SESSION_ID" --force
```

Read the private path printed by the command and substitute it for
`<chart-path>` below. The file is written atomically with mode `0600` on POSIX.

Cross-check your output against whatever the user already has (a site
report, an app screenshot). Positions should match to the arcminute. If they
don't, suspect the timezone or DST before suspecting the math — historical
DST is the usual culprit. Only proceed once verified: every date you produce
downstream inherits this trust.

Treat birth data as sensitive. Keep chart JSONs out of public or committed
files. Delete the temporary chart with the available file tool after the final
answer; do not leave it in the session temp directory.

### 2. Snapshot the moment (if the question is about "now" / a specific time)

```bash
python "${CLAUDE_SKILL_DIR}/scripts/astro_calc.py" snapshot --natal "<chart-path>" --date 2026-07-14 --time 17:15
```

Gives transit positions, which natal house each falls in, and all aspects to
natal points sorted by tightness, marked applying/separating. It also reports
ecliptic latitude, right ascension, declination, true node, Chiron, and mean
lunar-apogee Lilith when the required data are available.

### 3. Scan timelines — this is where the real value is

```bash
python "${CLAUDE_SKILL_DIR}/scripts/astro_calc.py" transits --natal "<chart-path>" --start 2026-01-01 --end 2027-12-31
python "${CLAUDE_SKILL_DIR}/scripts/astro_calc.py" transits --natal "<chart-path>" --start 2026-01-01 --end 2027-06-30 --planets saturn --targets moon --aspects conjunction
python "${CLAUDE_SKILL_DIR}/scripts/astro_calc.py" stations --start 2026-01-01 --end 2027-01-01 --tz-name Asia/Shanghai
python "${CLAUDE_SKILL_DIR}/scripts/astro_calc.py" lunations --natal "<chart-path>" --start 2026-07-01 --end 2026-12-31
python "${CLAUDE_SKILL_DIR}/scripts/astro_calc.py" progressions --natal "<chart-path>" --at 2026-07-14
python "${CLAUDE_SKILL_DIR}/scripts/astro_calc.py" ingresses --natal "<chart-path>" --start 2026-01-01 --end 2026-12-31 --kind both
python "${CLAUDE_SKILL_DIR}/scripts/astro_calc.py" eclipses --natal "<chart-path>" --start 2026-01-01 --end 2027-12-31
```

PowerShell uses the same arguments; replace `${CLAUDE_SKILL_DIR}` with
`$env:CLAUDE_SKILL_DIR`. Add `--json` or `--csv` when machine-readable output
is easier to inspect. Use `--quiet` to suppress transit progress messages.

The transit scanner finds **every** pass of a retrograde loop and numbers
them (`pass 2/3`), which is the backbone of serious transit work. The
lunation scanner flags New/Full Moons that land on natal points — a lunation
within a degree of an angle is always worth reporting.

Use `--engine swiss` when a reproducible high-precision calculation is required;
the command must fail if the official files are unavailable. Use the default
`auto` for portability. State the actual engine shown by the output. Do not
describe Chiron or another unavailable body as calculated.

### 4. Synthesize

Read `${CLAUDE_SKILL_DIR}/references/method.md` before writing the analysis. It covers triple-pass
narrative structure, station-on-degree emphasis, orb-cutoff audits, structural
pattern synthesis, layer hierarchy, house requirements, planetary endowments,
house-ruler links, transit application, and communication standards. For house
work, use its four observation layers and accumulation/expression rules instead
of treating a house as a canned life event.

The short version of the method:

- Lead with the one or two findings that are **exact now or rare** (a
  station on a natal degree, a lunation on an angle), not with a flat list.
- Present multi-pass transits as one story with dates, not as separate hits.
- Audit what the user's astrology site cut off with its orb limit — an
  applying Saturn-to-Moon at 6° is more important than half the aspects that
  made the site's 2° list.
- End with a compact date calendar the user can act on.

## Framing and ethics

Present astrology as a symbolic/reflective tradition, not as established
causal prediction — keep the analysis internally rigorous (real dates, real
geometry) while staying honest about epistemic status; a natural place to
signal this is a brief note when first presenting results. Never present
transit interpretations as medical, financial, or legal advice, and don't
use frightening determinism ("this transit means divorce/illness/ruin").
The computed timeline is the service; the meaning stays the user's to make.
