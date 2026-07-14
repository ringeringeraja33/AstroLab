# AstroLab Interpretation Method

How to turn computed ephemeris data into an analysis that is worth more than
the sum of its cookbook meanings. These practices are what separate a deep
reading from a horoscope-site printout.

## Contents

1. Verify before interpreting
2. The triple-pass narrative
3. Stations are louder than crossings
4. Audit the orb cutoff
5. Synthesize structures, not line items
6. Layer hierarchy
7. Houses as requirements
8. Communication standards

## 1. Verify before interpreting

Recompute the natal chart and match it against whatever source the user
trusts, to the arcminute. State that you did this in one line. All the
authority of your dates rests on this step.

## 2. The triple-pass narrative

When an outer planet (Jupiter outward) aspects a natal point, retrograde
loops usually produce three exact hits (occasionally one or five). Read them
as one story arc, not three events:

- **First pass (direct)** — the theme announces itself; events sketch the outline.
- **Second pass (retrograde)** — revision; the same material returns for rework.
- **Third pass (direct)** — resolution; the durable version settles in.

Present all passes with dates in one block. If the user brings up something
that happened near an earlier pass ("my interview was on the 11th"), connect
it: the past pass calibrates what the remaining passes are about.

## 3. Stations are louder than crossings

A planet stationing **on or within ~1° of a natal point** parks its full
weight there for weeks (Mercury/Venus) to months (Saturn–Pluto). Always run
the `stations` command over your analysis window and check each station
longitude against the natal chart. A Saturn station 0°40' from the natal
Moon outranks nearly everything else in the period — even though a plain
transit list shows nothing special that week.

Also note stations that land on a degree a transit had already activated
(e.g. Jupiter stationing exactly where it squared the Sun months earlier):
that degree's story gets a second act.

## 4. Audit the orb cutoff

Astrology sites typically list aspects within 2°. Two classes of important
material get cut:

- **Applying heavyweights just outside orb** — Saturn 6° before the natal
  Moon is not "no aspect", it is the next twelve months. Run a `transits`
  scan past the end of the question's window to catch what is incoming.
- **Tight natal aspects** activated by transit — if a transiting planet hits
  one leg of a tight natal aspect (say a natal Sun–Uranus square at 0°12'),
  it triggers the whole configuration. Check the natal chart's internal
  aspects for anything under ~1° and watch for transits to either leg.

## 5. Synthesize structures, not line items

Scan the full aspect list for geometry before writing: three or more
simultaneous aspects often form a named pattern (grand trine, kite, T-square)
with a **focal planet**. A natal planet receiving trines from two outer
planets while a third opposes it is one rewiring-project with a terminal —
say that, instead of listing four aspects separately. The natal planet's
condition (house, dignity, natal aspects) tells you what is being rewired.

## 6. Layer hierarchy

Order findings by how slow/rare the layer is — slower = more structural:

1. **Secondary progressions** (prog Sun ~1°/year; a prog Sun conjunction to
   a natal planet happens once in a lifetime) — the backdrop era.
2. **Outer-planet transits** (Saturn–Pluto) — the multi-year chapters.
3. **Jupiter and inner-planet transits, retrograde cycles** — the months.
4. **Lunations and fast triggers** — the days. A New/Full Moon within ~1° of
   an angle or personal planet is a legitimate headline despite being a
   "fast" event; lunations elsewhere are filler and usually not worth
   reporting.

Also compute the progressed lunation phase — it names the era's tempo
(building, crisis of action, harvest, dissolution) in one number.

## 7. Houses as requirements

The PDF supplied to this project attributes this framework to dogcatcher
(2012). Treat the twelve houses as recurring requirements rather than twelve
fixed life areas.

### The twelve requirements

| House | Requirement |
|---|---|
| 1  | A coherent identity and the capacity to act as oneself. |
| 2  | Stable self-worth and discernment about where to invest resources. |
| 3  | Curiosity about the immediate environment and an understanding of what is happening. |
| 4  | Belonging, rootedness, and emotional security. |
| 5  | Play, creative expression, and enjoyment. |
| 6  | Competent practice, task completion, and useful service. |
| 7  | Meeting others, negotiating differences, and sustaining partnership. |
| 8  | Engaging with shared resources and desires while remaining capable of change. |
| 9  | Pursuing knowledge, truth, freedom, and a broader horizon. |
| 10 | Achievement, responsibility, and direction in public life. |
| 11 | Community participation, mutual recognition, and commitment to shared hopes. |
| 12 | Withdrawal, release, reflection, and engagement with what lies beyond conscious control. |

### Read a natal chart through the requirements

Use four observation layers:

1. **Planets in a house** show the person's characteristic response and
   attitude toward that requirement. Each planet is a psychological drive, so
   the house's occupants show what kind of energy gets spent meeting it.
2. **The house ruler's placement** shows where the person tries to meet the
   requirement. A ruler of the 10th in the 6th pursues achievement through
   daily craft and usefulness.
3. **The ruler's condition** shows how much weight the person gives that
   requirement relative to others. Check dignity, strength, and influence over
   other rulers.
4. **Links between rulers** show how requirements depend on one another. Check
   reception, mutual reception, and aspects.

### The endowment hypothesis

The supplied PDF attributes the endowment hypothesis to dogcatcher (2012). It
is an interpretive hypothesis, not a measured fact. Here, *endowment* means a
constructive quality or the potential to build a satisfying life. It may appear
as a physical trait, a psychological capacity, outside support, or something
developed through practice.

Keep two layers separate:

1. **Basic endowments** come from the luminaries and visible planets. They
   describe psychological functions and qualities available to the person.
2. **Upper endowments** come from houses and angles. They describe where those
   qualities seek a route, what motivates their use, and which requirements
   receive more weight.

A house does not supply a trait by itself, and a planet does not describe the
route by itself. Read the planet as a capacity, then read its house, rulerships,
and links as the route through which that capacity is sought and expressed.

#### Basic endowments carried by planets

| Factor | Constructive capacity |
|---|---|
| Sun | vitality, initiative, being seen, dignity |
| Moon | warmth, care, safety, belonging |
| Mercury | precision, detail, fluency, agility |
| Venus | harmony, beauty, comfort, pleasure |
| Mars | will, force, speed, directed action |
| Jupiter | breadth, freedom, foresight, uplift |
| Saturn | maturity, reliability, order, necessary control |

The model groups the Sun and Moon around vitality and emotional nourishment,
Venus and Jupiter around easier or more expansive experience, and Mercury and
Saturn around effort, tension, and refinement. Use these pairings as an
interpretive aid, not a scoring system.

Uranus, Neptune, and Pluto may pressure or transform a requirement, but they do
not directly carry a personal endowment in this model. Fixed stars may be used
as endowment signals only when the chosen method supports them.

#### Upper endowments carried by houses

House value is relative. Social values and personal priorities determine which
answers receive attention. The Ascendant and 1st house collect "I exist / who
am I?", while the MC and 10th house collect "I accomplish / am I succeeding?"
The model treats these as the two largest collection points, with the Ascendant
carrying the broader claim to existence.

The other houses modify, support, delay, or redirect those two requirements. The
four angular houses form a visible scaffold: the 1st for existence, the 4th for
belonging and inner security, the 7th for facing another person, and the 10th
for achievement and public command. Do not classify houses as inherently good
or bad.

#### Accumulate and express endowments

Use two verbs:

- **Accumulate:** strengthen, integrate, or layer capacities.
- **Express:** make a capacity visible as a stable trait, choice, or practiced
  ability.

Check these routes:

1. **Planetary condition.** Essential dignity can strengthen a planet's own
   mode of expression. A weak planet may rely more on dispositors, reception,
   or other supporting links.
2. **House stewardship.** A planet gathers the requirements of the houses it
   rules, joining planetary capacities to house motives.
3. **Placement.** A planet expresses its capacity through the house it occupies.
4. **Angles.** A close relationship with the Ascendant or MC can make the
   capacity more visible. Use only techniques supported by the chosen method.
5. **Planetary links.** Reception, mutual reception, aspects, antiscia, or light
   transmission may combine or relay capacities. Use only links that can be
   calculated or verified from the chart.

Low support for a capacity does not prove a fixed personal deficit. It may
suggest fewer ready psychological resources, more effort spent developing
them, or a need for help and alternate routes. Phrase this as a working
interpretation, never as a diagnosis or moral judgment.

### Apply the requirements to transit work

- **A transit planet moving through a natal house presses that house's
  requirement.** Saturn transiting the 6th subjects competence, task
  completion, and useful service to sustained review. Phrase the reading as a
  requirement being emphasized by a planet.
- **A transit to a natal planet activates the requirements of every house that
  planet rules**, along with the house it occupies. A hit on natal Venus in a
  Libra rising chart presses both the 1st-house and 8th-house requirements.
- **Lunations and stations in a house** can mark a new chapter, a culmination,
  or sustained pressure around its requirement.

Keep Uranus, Neptune, and Pluto in the role of pressure on a requirement rather
than traits of the person.

### Use extended calculations selectively

- State whether a lunar-node position is true or mean; do not mix them within
  one timeline.
- AstroLab defines Lilith as the mean lunar apogee. Name that definition in the
  reading because other software may use the osculating apogee or an asteroid.
- Treat Chiron as an optional interpretive point and confirm that the output
  reports a Swiss data file. Omit it when calculation data are unavailable.
- Use sign ingresses to mark a change in mode and natal-house crossings to mark
  a change in the requirement receiving attention. A retrograde crossing can
  reverse and repeat; present the complete sequence.
- Rank an eclipse by its exact distance from natal planets and angles, then by
  its natal house. A distant eclipse is background context, not a personal
  headline.
- Declination, right ascension, and ecliptic latitude are computed coordinates.
  Interpret parallels or other non-longitudinal techniques only when the user
  asks for a method that uses them.

## 8. Communication standards

- **Dates, always.** "Late 2026 will be heavy" is horoscope-speak;
  "Nov 13 – Jan 7, with the station Dec 11 at 0°40' from your Moon" is
  analysis. Give hits to the day, stations to the day, and say which pass
  each hit is.
- **No cookbook padding.** Never paste generic paragraph meanings of
  "Saturn in the 6th house". One sentence of meaning per finding, anchored
  to the user's actual situation if they've shared it.
- **End with a calendar.** A compact table — date, event, one-line reading —
  is the artifact the user keeps.
- **Rank ruthlessly.** Lead with the rarest/tightest finding. If everything
  is important, nothing is.
- **Symbolic framing, honest epistemics.** Present the work as a reflective
  /symbolic tradition done rigorously, not as causal prediction. No medical,
  financial, or legal directives; no fatalism. Frame hard transits as
  load-bearing periods with concrete, mundane preparations.

---

*The house and endowment framework is condensed from the supplied PDF* 12
Houses and Self-Inquiry. *That PDF attributes the model to dogcatcher (2012)
but does not provide a complete bibliographic citation. Do not infer missing
publication details. This guide interprets the source; it does not reproduce
the PDF.*
