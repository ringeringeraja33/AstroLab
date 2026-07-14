---
name: astro-transits
description: >
  Deep astrological transit analysis backed by real Swiss Ephemeris computation
  instead of recycled horoscope text. Use this skill whenever the user asks
  about their birth chart, natal chart, transits, predictive astrology,
  house placements, house rulers, annual forecasts, secondary progressions,
  retrogrades, "when will Saturn/Pluto/... hit
  my X", lunar returns, new/full moons relative to their chart, or pastes a
  URL from an astrology site (ixingpan, astro.com, astro-seek, etc.). Also use
  it when the user asks to time events astrologically ("what does this month
  look like", "pick a date for..."). It computes exact hit dates, retrograde
  triple passes, stations, and progressions with arcminute precision — always
  prefer it over answering astrology questions from memory, because recalled
  planetary positions and dates are unreliable.
---

# AstroLab

AstroLab turns astrology questions into ephemeris computations. The core
principle: **never state a planetary position or transit date from memory** —
LLM recall of ephemeris data is unreliable — and **never pad an analysis with
generic cookbook text** the user could read on any horoscope site. Everything
you assert should either come out of `scripts/astro_calc.py` or be an
interpretive synthesis you can point back to computed data.

## Setup (once per machine)

```bash
pip install pyswisseph        # or: python3 -m venv venv && venv/bin/pip install pyswisseph
```

No ephemeris data files are needed — the script runs Swiss Ephemeris in
Moshier mode (analytic theory, accuracy far below one arcminute for
1800–2200 CE, which is more than enough for astrology).

## Workflow

### 1. Get birth data, compute the natal chart, VERIFY it

You need: birth date, local time, UTC offset, latitude, longitude. If the
user pastes a chart URL (ixingpan, astro.com...), fetch it and extract both
the birth data and the listed positions.

```bash
python scripts/astro_calc.py natal --date 2000-11-09 --time 04:55 --tz 8 \
    --lat 40.8 --lon 111.68 --save chart.json
```

Cross-check your output against whatever the user already has (a site
report, an app screenshot). Positions should match to the arcminute. If they
don't, suspect the timezone or DST before suspecting the math — historical
DST is the usual culprit. Only proceed once verified: every date you produce
downstream inherits this trust.

Treat birth data as sensitive. Keep chart JSONs out of anything public and
out of committed files.

### 2. Snapshot the moment (if the question is about "now" / a specific time)

```bash
python scripts/astro_calc.py snapshot --natal chart.json --date 2026-07-14 --time 17:15
```

Gives transit positions, which natal house each falls in, and all aspects to
natal points sorted by tightness, marked applying/separating.

### 3. Scan timelines — this is where the real value is

```bash
# outer-planet hits on personal points across a window
python scripts/astro_calc.py transits --natal chart.json \
    --start 2026-01-01 --end 2027-12-31

# narrow it: one mover, one target, one aspect
python scripts/astro_calc.py transits --natal chart.json \
    --start 2026-01-01 --end 2027-06-30 \
    --planets saturn --targets moon --aspects conjunction

# stations, lunations, progressions
python scripts/astro_calc.py stations --start 2026-01-01 --end 2027-01-01 --tz 8
python scripts/astro_calc.py lunations --natal chart.json --start 2026-07-01 --end 2026-12-31
python scripts/astro_calc.py progressions --natal chart.json --at 2026-07-14
```

The transit scanner finds **every** pass of a retrograde loop and numbers
them (`pass 2/3`), which is the backbone of serious transit work. The
lunation scanner flags New/Full Moons that land on natal points — a lunation
within a degree of an angle is always worth reporting.

### 4. Synthesize

Read `references/method.md` before writing the analysis — it contains the
interpretation methodology: triple-pass narrative structure, station-on-degree
emphasis, orb-cutoff audits, structural pattern synthesis, layer hierarchy
(progressions → outer transits → inner transits → lunations), and the
communication standards.

For anything involving **houses** — a transit moving through a natal house,
natal house placements, house rulers, lunations falling in a house, or a
question about chart gifts and potential — also read `references/houses.md`.
It reframes the houses as twelve standing questions and separates basic
planetary endowments from the routes and motives described by houses. Use its
four observation layers and accumulation/expression rules instead of treating
a house as a canned life event.

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
