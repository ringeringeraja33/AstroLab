# AstroLab: transit calculations for Claude and the command line

AstroLab calculates astrological transits with the Swiss Ephemeris. You can use it
as a [Claude Code skill](https://docs.anthropic.com/en/docs/claude-code) or run
it directly from the command line.

It finds exact transit dates, tracks retrograde passes, lists stations, checks
lunations against natal points, and calculates secondary progressions. The
scripts use the Moshier ephemeris built into `pyswisseph`, so you do not need to
download a separate set of ephemeris files.

## Install

```bash
pip install pyswisseph
```

The scripts run Swiss Ephemeris in Moshier mode. For dates between 1800 and
2200, the calculated positions are accurate to well under one arcminute.

### Use it as a Claude Code skill

Copy the skill folder into your Claude Code skills directory:

```bash
cp -r astro-transits ~/.claude/skills/
```

You can then ask Claude questions such as `Analyze my current transits` or
`When does Saturn hit my Moon?` Claude will call the calculator instead of
trying to recall the positions from memory.

### Use it from the command line

```bash
cd astro-transits/scripts

# 1. Calculate a natal chart and save it
python astro_calc.py natal --date 1990-05-15 --time 14:30 --tz 8 \
    --lat 39.9 --lon 116.4 --save chart.json

# 2. Find exact outer-planet transits, including numbered retrograde passes
python astro_calc.py transits --natal chart.json --start 2026-01-01 --end 2027-12-31

# 3. List transits at one moment, sorted by orb
python astro_calc.py snapshot --natal chart.json --date 2026-07-14 --time 17:15

# 4. List retrograde and direct stations
python astro_calc.py stations --start 2026-01-01 --end 2027-01-01 --tz 8

# 5. Find new and full moons near natal points
python astro_calc.py lunations --natal chart.json --start 2026-07-01 --end 2026-12-31

# 6. Calculate secondary progressions
python astro_calc.py progressions --natal chart.json --at 2026-07-14
```

Example `transits` output:

```text
Exact transit hits 2026-01-01 .. 2027-06-30 (movers: saturn)
  2026-04-26 11:39 UTC+08:00  Saturn  conjunction  natal Moon  D  (pass 1/3)
  2026-11-13 21:39 UTC+08:00  Saturn  conjunction  natal Moon  R  (pass 2/3)
  2027-01-07 09:24 UTC+08:00  Saturn  conjunction  natal Moon  D  (pass 3/3)
```

## Repository layout

```text
astro-transits/
|-- SKILL.md                 # Trigger rules and workflow for Claude
|-- scripts/astro_calc.py    # Calculation engine with six subcommands
`-- references/
    |-- method.md            # Interpretation method: triple passes,
    |                        # stations, orb checks, and layer hierarchy
    `-- houses.md            # House questions, planetary endowments,
                             # ruler links, and house-transit interpretation
```

The calculator uses the Python standard library plus `pyswisseph`.

## Things to check

- The default house system is Placidus (`--hsys P`). Use `W` for whole-sign
  houses. Placidus is undefined at polar latitudes.
- `--tz` takes a plain UTC offset, such as `--tz 8`. It does not look up
  historical daylight-saving time. If a chart differs from a trusted source,
  check the birth-time offset first.
- Birth data is personal data. Chart JSON files are gitignored by default, and
  they should stay out of public repositories.
- The project treats astrology as a symbolic and reflective practice. The
  software calculates positions and dates; interpretation is up to the user.
  Do not use it as medical, financial, or legal advice.

## License

This project uses AGPL-3.0 because
[`pyswisseph`](https://github.com/astrorigin/pyswisseph) wraps the Swiss
Ephemeris, which is available under either the AGPL or a commercial license.
See [LICENSE](LICENSE).

## A note on cycles / 关于周期的补充说明

AstroLab treats transits as clocks, not verdicts. An aspect does not make an
event happen, just as a clock hand reaching five does not make someone tired.
It marks a phase in a repeating cycle and points to an area of experience that
may deserve attention.

Jupiter's roughly twelve-year return, Saturn's roughly twenty-nine-year return,
and the annual solar return provide different scales for reflection. A tense
aspect is not a bad event to dodge. It can prompt us to notice a recurring
psychological pattern, review what has changed, and decide what needs attention
next. AstroLab supplies dates and geometry; the interpretation remains
reflective rather than deterministic.

AstroLab 把行运看成时钟，不把它当成判决。相位不会像外力一样制造事件，就像时针走到下午五点并不会让人疲惫；它标记的是反复出现的周期阶段，提醒我们某部分经验值得留意。

木星约十二年的回归、土星约二十九年的回归，以及每年的太阳回归，提供了不同尺度的回看节点。紧张相位也不必当成需要躲开的坏事，它可以用来辨认反复出现的心理模式，回顾已经发生的变化，再决定下一步需要处理什么。AstroLab 负责计算日期和几何关系，解释仍然用于反思，不作宿命判断。
