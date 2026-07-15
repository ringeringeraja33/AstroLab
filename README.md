# AstroLab

AstroLab calculates natal charts, exact transits, stations, sign ingresses,
house crossings, eclipses, lunations, and secondary progressions with the Swiss
Ephemeris. It can run as a command-line program or as a
[Claude Code skill](https://code.claude.com/docs/en/skills).

The transit scanner follows retrograde loops across the requested window and
labels each exact hit, including uncommon five-pass sequences. It runs without
separate data files through Moshier and can install Astrodienst's official
compressed files for strict Swiss Ephemeris calculations.

## Interpretive stance

AstroLab treats planetary cycles as objective chronological markers and their
astrological meanings as a symbolic interpretive framework. An aspect does not
name a predetermined event; it organizes attention around a period of tension,
and the person's response is often more informative than a generic forecast.
Because interpretation can alter attention, self-description, and action,
readings should distinguish prior experience from meanings prompted by the
reading. AstroLab remains methodologically agnostic about causal or synchronic
claims: symbolic usefulness does not establish external causation.

## Install

AstroLab requires Python 3.9 or newer.

```bash
python -m pip install .
astrolab --version
```

Install the official 1800–2399 data set and check it:

```bash
astrolab ephemeris download
astrolab ephemeris status
```

The command retrieves `sepl_18.se1`, `semo_18.se1`, `seas_18.se1`, and
`sefstars.txt` from the
[official Astrodienst Swiss Ephemeris repository](https://github.com/aloistr/swisseph).
Files are stored under `~/.astrolab/ephe`; a local manifest records their
source, size, and SHA-256 hash. No birth data is sent during this operation.

To use the source script without installing the command:

```bash
python -m pip install -r requirements.txt
python astrolab/scripts/astro_calc.py --version
```

### Install the Claude Code skill

On macOS or Linux:

```bash
cp -R astrolab ~/.claude/skills/astrolab
```

On Windows PowerShell:

```powershell
Copy-Item -Recurse astrolab "$HOME/.claude/skills/astrolab"
```

After that, ask Claude a chart or transit question. The skill tells Claude to
calculate the dates instead of recalling ephemeris data from memory.

## Quick start

The examples below use the installed `astrolab` command. `python -m astrolab`
accepts the same arguments.

```bash
astrolab natal --date 1990-05-15 --time 14:30 --tz-name Asia/Shanghai --lat 39.9 --lon 116.4 --save chart.json
astrolab snapshot --natal chart.json --date 2026-07-14 --time 17:15
astrolab transits --natal chart.json --start 2026-01-01 --end 2027-12-31
astrolab stations --start 2026-01-01 --end 2027-01-01 --tz-name Asia/Shanghai
astrolab lunations --natal chart.json --start 2026-07-01 --end 2026-12-31
astrolab progressions --natal chart.json --at 2026-07-14
astrolab ingresses --natal chart.json --start 2026-01-01 --end 2026-12-31 --kind both
astrolab eclipses --natal chart.json --start 2026-01-01 --end 2027-12-31
```

Filter a transit scan by planet, natal point, and aspect:

```bash
astrolab transits --natal chart.json --start 2026-01-01 --end 2027-06-30 --planets saturn --targets venus --aspects conjunction
```

The scanner prints progress to stderr for long searches. Add `--quiet` in
scripts. Date ranges include the entire `--end` civil date and are limited to
50 years per command to catch accidental inputs.

## Ephemeris engines and coordinates

`--engine auto` is the default. It prefers installed Swiss files and records
every backend actually used. `--engine swiss` requires those files and fails
if a core planetary calculation falls back. `--engine moshier` is fully local.
`--engine jpl --jpl-file FILE` accepts a separately obtained JPL binary file.

Natal and snapshot results include longitude, latitude, distance, longitudinal
speed, right ascension, declination, and the backend used for each body. Core
planets are always retained in natal charts. The default extended set adds the
true lunar node, Chiron, and Lilith defined as the mean lunar apogee. Use
`--bodies mean_node,chiron,lilith` to choose other extended points.

Saved charts record the Swiss Ephemeris library version, requested backend,
actual backends, data-file names, sizes, and recorded hashes. Local absolute
paths are excluded from chart metadata.

## Timezones

Use an IANA timezone such as `Asia/Shanghai` or `America/New_York` when local
daylight-saving rules matter:

```bash
astrolab natal --date 1990-05-15 --time 14:30 --tz-name Asia/Shanghai --lat 39.9 --lon 116.4
```

A fixed offset remains available through `--tz 8`. During a repeated clock
hour, add `--fold 0` for the first occurrence or `--fold 1` for the second.
Nonexistent local times are rejected instead of silently shifted.

## JSON and CSV

Every calculation command accepts `--json` or `--csv`:

```bash
astrolab transits --natal chart.json --start 2026-01-01 --end 2026-12-31 --json --quiet
astrolab snapshot --natal chart.json --date 2026-07-14 --time 17:15 --csv
```

Saved chart files carry a schema version and are validated before use. AstroLab
rejects malformed nested values, unsupported schema versions, and non-finite
numbers with a concise command-line error.

## Birth-data safety

Birth data is personal data. `--save` refuses to overwrite an existing file
unless `--force` is supplied. Writes are atomic and use mode `0600` on POSIX.
The Claude skill uses `--private-save SESSION_ID` to place a session chart in
the system temporary directory and instructs the agent to delete it afterward.
This repository ignores JSON files as an additional guard.

## Repository layout

```text
astrolab/
|-- SKILL.md
|-- scripts/astro_calc.py
`-- references/method.md
tests/test_astro_calc.py
pyproject.toml
```

The house and endowment material in `method.md` is derived from a PDF supplied
to this project. That PDF attributes the model to dogcatcher (2012) but does not
include a complete bibliographic citation; the repository does not invent the
missing details.

## Test

```bash
python -m unittest discover -s tests -v
```

The test suite covers direct calculations, all command paths, structured output,
timezone edge cases, chart validation, private writes, backend fallback,
download integrity, ingress and eclipse scans, tangent roots, and three- and
five-pass transit grouping.

## Scope and license

AstroLab treats astrology as a symbolic and reflective practice. It calculates
positions and dates; it does not establish causal prediction or provide
medical, financial, or legal advice.

The project is licensed under AGPL-3.0 because
[`pyswisseph`](https://github.com/astrorigin/pyswisseph) wraps the Swiss
Ephemeris, which is offered under the AGPL or a commercial license. See
[LICENSE](LICENSE).
