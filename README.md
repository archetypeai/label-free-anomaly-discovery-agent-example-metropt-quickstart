# Label-Free Anomaly Discovery on a metro train's air compressor: quickstart

> You have three weeks of sensor data from one machine. Nobody has labelled it,
> and nobody knows whether anything went wrong in it. The **Label-Free Anomaly Discovery
> Agent** runs over it in batch and scores every hour by how unlike the rest of the file
> it is; this example turns those scores into a short list of episodes, with what each one
> looks like in the sensors. No normal-only reference, no
> labelled examples, nothing trained ahead of time. The operator's maintenance reports
> are opened only at the end, to grade what it found.

## TL;DR

- **What:** the Archetype AI platform's `od` blueprint, **Label-Free Anomaly Discovery**,
  run in batch through **Agent Lifecycle 2.0** (project → blueprint → package →
  deployment → session). `od` scores every window of a file against the file's other
  windows: Omega 1.5 embeddings plus 7 statistics per channel, fused into a Local Outlier
  Factor detector that is fitted on that same file. A score near 1 is ordinary; the higher,
  the more unusual.
- **Data:** [MetroPT-3](https://archive.ics.uci.edu/dataset/791/metropt+3+dataset) (UCI,
  CC BY 4.0), the air-production unit of a Porto metro train, Feb–Sep 2020: 7 analog
  sensors every 10 s, and 4 air leaks in the operator's maintenance reports. This
  quickstart uses three 3-week stretches of it.
- **The lifecycle:**

| stage | what happens | time |
|---|---|---|
| 0 | download MetroPT-3 (218 MB) | ~5 s |
| 1a–1c | check the raw data, prepare the three input files, check them against `od`'s rules | ~3 s |
| 2 | **Discover:** `od` on the platform, one batch session per file | ~1.5 min |
| 3 | **Review** (this example's code, not the agent): `od`'s flagged hours as episodes, described from the sensor data | ~1 s |
| 4 | **Grade** (this example's code): open the maintenance reports and compare | ~1 s |

  Only Stage 2 is the agent. Stages 0–1 prepare its input; Stages 3–4 are post-processing
  of its output, run on your computer.

- **Result:** both reported leaks in the data are found. Leak #4 is the top-ranked hour of
  its file (AUROC 0.997), flagged **13 hours before** the operator's report. Leak #1 is
  flagged in all 23 of its hours (AUROC 0.974). `od` also finds episodes nobody reported,
  several with a leak's exact signature, including in the file with no reported failure.
- **In a hurry?** The three input files are already prepared in `data/prepared/`: after
  [Setup](#setup), skip straight to [Stage 2: Discover](#stage-2-discover).
- **What `od` returns:** a score and a label per window, in batch (no serving); it doesn't
  say which sensors drove a score. Stage 3, this example's own code, describes each episode
  from the data instead.

## The scenario

- **You** run a fleet of metro trains and have the sensor log of one train's air
  compressor. You want to know whether anything unusual happened in it, and when. You
  have no labels and no "known good" period to compare against.
- **The agent** looks at each file on its own and ranks its hours by how unlike the rest
  of the file they are. It needs no reference and learns nothing ahead of time, so it can
  run on the day the data arrives.
- **The answer** comes in two parts. The agent returns a score and a label for every
  hour. This example's own code (Stage 3) turns them into a short list of episodes per
  file, each with its time, length, peak score and what stands out in the sensors:
  something a person can check.
- **Grading:** Metro do Porto's maintenance reports list four air leaks. We open them only
  in Stage 4, after the review is written, to see what the agent found that the operator
  knew about, and what it found that they didn't.

This differs from the [TEP quickstart](https://github.com/archetypeai/anomaly-discovery-agent-example-tep-quickstart),
where the Anomaly Discovery agent (`ad`) is fitted on a normal-only library, tuned on
labelled incidents with the Optimizations API, tested with Evals and then monitors new
data. Here there is no library, nothing to tune on, and nothing to monitor: one batch pass
over data that has just arrived.

### The files

Three stretches of three weeks. We picked the dates with the maintenance reports in hand,
so that A and B each hold one reported leak and C none: that sets up Stage 4's grading.
Nothing from the reports goes into the files. The leaks are a small part of each file,
which is what `od` assumes (LOF flags what is rare, so anomalies should be under ~10–15%
of the windows).

| file | dates | data | one-hour windows | in the maintenance reports |
|---|---|---|---|---|
| A | Apr 4 – Apr 25, 2020 | 16.7 days | 401 (375 gap-free) | leak #1, Apr 18, ~24 h |
| B | Jul 1 – Jul 22, 2020 | 17.1 days | 409 (376 gap-free) | leak #4, Jul 15, 4.5 h |
| C | Mar 1 – Mar 22, 2020 | 17.7 days | 423 (394 gap-free) | nothing |

The dataset has gaps when the train is out of service, so 3 weeks hold ~17 days of data.
Leaks #2 and #3 are only 6 days apart; a quickstart doesn't need them.

The 7 analog channels, as the dataset describes them:

| channel | what it measures |
|---|---|
| `TP2` | pressure at the compressor (bar) |
| `TP3` | pressure at the pneumatic panel (bar) |
| `H1` | pressure drop when the cyclonic separator filter discharges (bar) |
| `DV_pressure` | pressure drop when the air-dryer towers discharge; reads zero when the compressor works under load (bar) |
| `Reservoirs` | pressure downstream of the reservoirs, close to `TP3` (bar) |
| `Oil_temperature` | the compressor's oil temperature (°C) |
| `Motor_current` | one phase of the motor: ~0 A off, ~4 A running offloaded, ~7 A under load, ~9 A starting (A) |

The dataset's 8 digital channels (valve and switch signals) are left out.

### The maintenance reports

The sensor data has no labels: no row says "leak". What the dataset does come with is a
table of four failures that the train operator reported, published in its documentation
(the "Failure Information" table on the
[UCI page](https://archive.ics.uci.edu/dataset/791/metropt+3+dataset), and in
`Data Description_Metro.pdf`, which Stage 0 downloads with the data):

| Nr. | start | end | failure | severity | report |
|---|---|---|---|---|---|
| #1 | 4/18/2020 0:00 | 4/18/2020 23:59 | Air leak | High stress | |
| #1 | 5/29/2020 23:30 | 5/30/2020 6:00 | Air Leak | High stress | Maintenance on 30Apr at 12:00 |
| #3 | 6/5/2020 10:00 | 6/7/2020 14:30 | Air Leak | High stress | Maintenance on 8Jun at 16:00 |
| #4 | 7/15/2020 14:30 | 7/15/2020 19:00 | Air Leak | High stress | Maintenance on 16Jul at 00:00 |

- **They are records of failures someone noticed and acted on,** with rough time windows,
  not labels on the sensor readings. A leak likely starts before anyone writes it down, and
  something unusual that nobody reported isn't in the table.
- **Two typos in the published table:** the second row is numbered #1 (it is the second
  leak; this example numbers the four 1 to 4), and its maintenance is dated 30 April, a
  month before the failure it follows (probably 30 May). Neither matters here: only the
  start and end times are used.
- **This example uses them in two places, never as input to the agent:** we picked the
  three files' dates with the table in hand (A and B hold a leak, C none), and Stage 4
  reads the start and end times, copied into `common.py`, to grade the result.

Your own data may have nothing like this, or may have work orders, shift logs or repair
tickets that serve the same purpose.

## Setup

```sh
git clone https://github.com/archetypeai/label-free-anomaly-discovery-agent-example-metropt-quickstart.git
cd label-free-anomaly-discovery-agent-example-metropt-quickstart
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt          # numpy, pandas; the platform calls use the standard library
[ -f .env ] || cp .env.example .env     # then fill in ATAI_API_KEY and ATAI_API_ENDPOINT
```

`.env` wins over `ATAI_API_KEY` / `ATAI_API_ENDPOINT` exported in your shell: keys are per
deployment, and a key exported for another one is the usual reason a first call fails.
Every platform script prints the endpoint and the key's last 4 characters it uses. The
endpoint can be the bare deployment root or end in `/api`. `od` is available on production
(`https://platform.u1.archetypeai.app`) as of November 2026.

**Skip to Stage 2.** The three input files are already prepared and in the repo
(`data/prepared/metropt_{A,B,C}.csv`), so you don't need to download or prepare anything:

```sh
python prep/preflight.py      # optional: check the files against od's rules (Stage 1c)
python run/discover.py        # Stage 2: Discover
```

Stages 0–1 are there to show how the files were made, and to rebuild them from the
original data. Every stage's output from our run is in `eval_out/` too, to read without
running anything.

## The stages

Every script runs from the repo folder and is safe to rerun.

### Stage 0: download

> Optional: `data/prepared/` already holds this stage's and Stage 1's result. To start
> there, go to [Stage 2](#stage-2-discover).

```sh
python prep/download.py
```

Downloads the UCI zip and extracts `MetroPT3(AirCompressor).csv` (1,516,948 rows) and the
data description PDF into `data/raw/` (git-ignored), then checks the CSV's SHA-256.
**Expect:** `data/raw/MetroPT3(AirCompressor).csv: SHA-256 verified`.

### Stage 1: check, prepare, check again

```sh
python prep/preflight_raw.py      # 1a: the raw file, read-only
python prep/prepare.py            # 1b: the 10 s grid and the three files
python prep/preflight.py          # 1c: the files against od's rules, read-only
```

- **1a** checks the raw file before any decision. **Expect:** `8 PASS, 3 WARN, 0 FAIL,
  1 INFO`. Each WARN names the 1b decision it leads to:
  - `cadence`: samples are ~10 s apart but not exactly, so 1b snaps them to a 10 s grid;
  - `gaps`: 331 gaps over a minute, when the train is out of service. Nothing is
    interpolated across one;
  - `frozen logger`: stretches where every channel holds one value for 30 minutes or
    more, which a working compressor can't produce. 1b cuts them out. Left in, they crowd
    the top of the ranking: on file A, all 36 frozen hours were flagged and took ranks 3 to
    ~40, pushing most of leak #1 from ranks 3–36 down to 42 and below (its AUROC fell from
    0.974 to 0.883).
- **1b** builds the 10 s grid, cuts the frozen stretches (170 hours of the 7 months), and
  writes the three files by date. **Expect:**
  ```
  grid: 1,516,948 raw rows -> 1,514,658 rows at 10 s; frozen-logger rows cut: 61,186 (170 h)
    A: 2020-04-04 .. 2020-04-25  144,719 rows (16.7 days of data) in 41 continuous pieces
    B: 2020-07-01 .. 2020-07-22  147,518 rows (17.1 days of data) in 47 continuous pieces
    C: 2020-03-01 .. 2020-03-22  152,515 rows (17.7 days of data) in 37 continuous pieces
  ```
  The files keep raw units: `od` z-scores what it needs, on the file it scores.
- **1c** checks each file the way `od` will read it: a timestamp column and the 7
  channels, no label column, finite values, strictly increasing 10 s timestamps, no
  frozen stretch left, and enough gap-free windows for LOF. **Expect:** `18 PASS, 0 WARN,
  0 FAIL, 3 INFO`, the INFO lines being the LOF neighbourhood size: K = 20% of a file's
  windows, about 75, so an episode longer than ~75 hours would form its own neighbourhood
  and hide.

**Writes:** `data/prepared/metropt_{A,B,C}.csv` and `prepare_report.json`. No label is read.

#### The input files

What Stage 2 sends to `od`, one file per session. Each is a plain CSV:

```
timestamp,TP2,TP3,H1,DV_pressure,Reservoirs,Oil_temperature,Motor_current
1585967540,6.452,5.942,-0.01,-0.026,5.936,29.45,5.56
1585967550,5.988,6.096,-0.012,-0.026,6.094,29.875,5.59
```

- `timestamp`: seconds since 1970, one row every 10 s exactly. It is the dataset's own
  clock (Portugal), written as if it were UTC, with no shift.
- The 7 analog channels in their original units (bar, °C, A), not normalised.
- No label column, and nothing derived from the maintenance reports.

| | A | B | C |
|---|---|---|---|
| dates | Apr 4 – Apr 25 | Jul 1 – Jul 22 | Mar 1 – Mar 22 |
| rows | 144,719 | 147,518 | 152,515 |
| days of data in the 3 weeks | 16.7 | 17.1 | 17.7 |
| continuous pieces | 41 (median 2.1 h, longest 53 h) | 47 (median 1.3 h, longest 49 h) | 37 (median 6.6 h, longest 47 h) |
| gaps between pieces | median 46 min, longest 21 h | median 7 min, longest 24 h | median 38 min, longest 9 h |
| compressor off / offloaded / under load | 60% / 25% / 15% | 45% / 41% / 14% | 54% / 33% / 13% |
| typical oil temperature | 58 °C | 68 °C | 62 °C |
| one-hour windows (gap-free) | 401 (375) | 409 (376) | 423 (394) |
| size | 7.5 MB | 7.7 MB | 8.0 MB |
| in the maintenance reports (Stage 4 only) | leak #1, Apr 18 | leak #4, Jul 15 | nothing |

Normal operation differs by month: in July the oil runs ~10 °C warmer and the compressor
idles offloaded more. That is one reason `od` compares each file only with itself.

How 1b builds them from the raw file:

1. **A 10 s grid.** Raw samples arrive every 10–12 s; each is snapped to a 10 s slot (the
   mean when two land in one).
2. **Short holes filled, long gaps kept.** Up to 50 s missing is sampling jitter and takes
   the last value; anything longer, usually the train out of service, stays a gap. Nothing
   is interpolated across one, so each file is 37–47 separate pieces.
3. **Frozen stretches removed.** Every channel holding one value for 30 minutes or more is
   the logger, not the compressor: 170 hours across the dataset are cut.
4. **Cut by date** into three ranges of three weeks, so that each reported leak is a small
   share of its file (6% of A, 1% of B), as `od` assumes.
5. **The 7 analog channels only;** the 8 digital ones (valve and switch signals) are left
   out.

`od` cuts each file into one-hour windows (360 rows) from the first row, without overlap.
A window that crosses a gap is marked invalid and left out of the fit: a piece shorter than
an hour, or the end of a longer one, always lands in such a window, which is why 6–8% of
each file's windows are invalid. The rest are each compared with the rest of the same file.

### Stage 2: Discover

```sh
python run/discover.py                   # all three files; --files A to run one
```

The platform run, on Agent Lifecycle 2.0. Every object lives in one project:

| step | call | here |
|---|---|---|
| project | `POST /api/projects` | `Label-Free AD MetroPT quickstart`, reused on reruns |
| blueprint | `POST /api/agents/blueprints/od/copy` with `overrides.values` | `od-metropt-qs`: the timestamp column, the 7 channels, `window_size` 360 and `step_size` 360 (one hour, no overlap). Everything else is `od`'s default |
| package | `POST /api/agents/packages` | the copy, with the Omega 1.5 encoder resolved once |
| deployment | `POST /api/agents/deployments` (`kind: batch`) | ready at once; reused |
| session | `POST /api/agents/sessions` with the file's id | one per file; `od` fits LOF on that file's gap-free windows and scores them |
| results | `GET /api/agents/sessions/{id}/results` | a CSV, one row per window |

No optimization, no promotion, no fitted model: `od` has nothing to train ahead of time.
The ids go to `out/discover_state.json`, so a rerun resumes, and an output is downloaded
again until it has a row for every window. A rerun also replaces what can't finish: a failed
package is deleted and built again, and a session that failed, or whose output stayed short
for 10 minutes, is ended and gets a new one; the other files go on meanwhile. **Expect**
(~1.5 min on production, 2026-11-12):

```
A: 401 windows, 26 invalid (cross a gap), 55 over 1.5
B: 409 windows, 33 invalid (cross a gap), 27 over 1.5
C: 423 windows, 29 invalid (cross a gap), 18 over 1.5
```

**Writes:** `eval_out/discover/od-metropt_<file>.csv`:
`finish_timestamp, start_timestamp, predicted_label, invalid, anomaly_score`. A window
that crosses a gap is `invalid` and has no score. `predicted_label` is `anomaly` when the
score is over `od`'s default 1.5.

Rerunning a file gives the same label on every window; scores differ by up to ~4×10⁻⁶
(the arithmetic of the platform's GPU), so a rerun's file may not be byte-identical.

#### How the settings were chosen

Four values are set in the copy of `od` (its `overrides`); everything else is `od`'s
default, the threshold included.

| value | here | why |
|---|---|---|
| `timestamp_column` | `timestamp` | names the column; not a tuning choice |
| `data_columns` | the 7 analog channels | the digital ones are on/off switch signals; not a tuning choice |
| `window_size` | 360 (one hour) | chosen by reasoning about the machine, not tuned (below) |
| `step_size` | 360 | no overlap: each hour is scored once, and the windows stay independent for LOF |

**`od`'s defaults, unchanged:**
- `threshold` 1.5: a window scoring above it is labelled `anomaly`.
- Neighbours: K = 20% of the file's valid windows, at least 5, at most 100, never more
  than a third (here K ≈ 75).
- Distance and features: L1 distance; Omega 1.5 embeddings reduced to 5 components per
  channel, plus 7 statistics per channel (mean, std, range, min, max, slope, median).
- Data checks: a window is invalid if its sample spacing varies by more than 5% (it
  crosses a gap), plus limits on missing values.

**How the window was chosen.** One hour was picked before any result was seen, and never
tuned against the maintenance reports. One input did come from them: how long the leaks
last.
- **Shorter than the events of interest.** A window much longer than an event dilutes it.
  The reported leaks last 4.5 hours to two days, so an hour is well under the shortest.
  Whoever runs the machine usually knows this much ("these problems last hours, not
  minutes"); if you don't, it is the one thing to ask them.
- **Longer than the machine's own rhythm.** The compressor starts every 19–28 minutes
  (the median in each file) and runs about 9 minutes each time, so an hour holds two to
  three full cycles: a window shouldn't look unusual just because it caught a cycle at a
  different point.
- **Enough windows for LOF.** About 400 per file. With K = 20%, an episode up to ~75 hours
  long still stands out (Stage 1c prints that limit).
- **Within the encoder's limits:** 16 to 1,024 samples per window.

### Stage 3: Review

```sh
python run/review.py                     # --top 5 episodes per file
```

**Not part of the agent.** This is this example's own post-processing, run on your
computer: the agent's output is Stage 2's score per window, and everything below is built
from that and the input file. It shows one way to turn the scores into something a person
can read and act on, e.g. a report for the people who run the machine.

Flagged windows that follow each other merge into an **episode**, ranked by its highest
score. For each, what stands out in the input itself:
every channel's level (mean) and spread (std) over the episode, as a robust z against the
file's usual hour, and how much of the time the compressor runs, and runs under load (from
`Motor_current`). No label or report is read. **Expect** (the first episodes of each file):

```
=== File A: 375 hours scored; 55 flagged (score over 1.5) in 9 episodes; usually the compressor runs 32% of an hour, under load 7%.
  1. Sun Apr 12 11:44 -> Sun Apr 12 23:44  12 h  peak 3.88  running 99%, loaded 88%  DV_pressure level +91, TP2 level +22, H1 level -22
  2. Sat Apr 18 01:15 -> Sun Apr 19 01:15  24 h  peak 3.00  running 100%, loaded 85%  DV_pressure level +101, H1 level -22, TP2 level +20
  3. Sun Apr 19 02:42 -> Sun Apr 19 03:42   1 h  peak 2.59  running 48%, loaded 11%  Reservoirs spread +15, TP3 spread +15, H1 spread +3
=== File B: 376 hours scored; 27 flagged in 7 episodes; usually the compressor runs 49% of an hour, under load 11%.
  1. Wed Jul 15 00:20 -> Wed Jul 15 17:20  17 h  peak 5.25  running 100%, loaded 46%  Motor_current spread -19, H1 level -6, TP2 level +5
  2. Wed Jul 08 17:50 -> Wed Jul 08 19:50   2 h  peak 4.54  running 90%, loaded 38%  TP3 spread +48, Reservoirs spread +48, Reservoirs level -17
=== File C: 394 hours scored; 18 flagged in 5 episodes; usually the compressor runs 41% of an hour, under load 9%.
  1. Wed Mar 11 23:49 -> Thu Mar 12 12:49  13 h  peak 4.55  running 94%, loaded 82%  DV_pressure level +64, H1 level -15, TP2 level +12
  2. Wed Mar 11 05:18 -> Wed Mar 11 06:18   1 h  peak 2.97  running 98%, loaded 77%  DV_pressure level +60, H1 level -13, TP2 level +9
  3. Fri Mar 06 21:34 -> Fri Mar 06 23:34   2 h  peak 2.67  running 92%, loaded 63%  DV_pressure level +33, H1 level -10, TP2 level +8
```

Two kinds of episode stand out, without any label:
- **The compressor never switches off and works under load most of the time** (loaded
  46–88% of the hour, against a usual 7–11%), with `TP2` high, `H1` near zero and
  `DV_pressure` raised, though the dataset says it reads zero under load. A compressor
  that keeps loading is what you'd expect if air escapes as fast as it is made.
- **Pressure swings** in the panel and reservoirs (`TP3`, `Reservoirs`: spread 10–48
  times the usual), with the compressor near its usual duty.

File C's episodes also form a sequence: loaded 63% on Mar 6, 47% on Mar 9, 39% on Mar 10,
then 77% and 82% on Mar 11–12. That looks like something building up, a question for the
machine's operators rather than a finding.

**Writes:** `eval_out/review/review.md` (the table a person would read) and `review.json`.

### Stage 4: Grade

```sh
python run/grade.py                      # --lead-h 24
```

**Not part of the agent.** This is this example's own evaluation, run on your computer,
to show how well the agent did. It needs answers the agent never sees, the operator's
maintenance reports. In real use there are often no such answers; here they let us check
the agent's work, as you could with good maintenance records. It is the only stage
that reads the reports.

Per file: the **AUROC** of the reported leak's hours against all other hours (the chance
that a leak hour outranks an ordinary one: 1.0 is perfect, 0.5 is chance), the ranks the
leak's hours reached, and the first flag. A leak builds before anyone reports it, so a flag up to `--lead-h` (24) hours before
the report's start counts as early. Then each Stage 3 episode as matching a report or not.
**Expect** (each file's summary; the episodes follow it):

```
=== File A: 2020-04-04 to 2020-04-25, 375 valid hours, 1 reported failure
  report #1 (air leak, 2020-04-18 00:00 .. 2020-04-18 23:59): 23 hours; AUROC 0.974; ranks [3, 4, 7, 10, 11, 13, 14, 15] ...; 23/23 flagged; first flag 2.3 h after the reported start
  episodes: 9, 1 match a report, 8 not reported (31 flagged hours)
=== File B: 2020-07-01 to 2020-07-22, 376 valid hours, 1 reported failure
  report #4 (air leak, 2020-07-15 14:30 .. 2020-07-15 19:00): 4 hours; AUROC 0.997; ranks [1, 2, 5, 6]; 4/4 flagged; first flag 13.2 h before the reported start
  episodes: 7, 2 match a report, 5 not reported (9 flagged hours)
=== File C: 2020-03-01 to 2020-03-22, 394 valid hours, 0 reported failures
  episodes: 5, 0 match a report, 5 not reported (18 flagged hours)
```

**How to read it:**
- **Both leaks are found.** Leak #4's hours are the top two of its file, and the episode
  around it starts at 00:20, 13 hours before the 14:30 report: the compressor had already
  stopped switching off. Every hour of leak #1 is flagged.
- **"Not reported" is not the same as "false alarm".** The reports list failures someone
  acted on. File A's top episode (Apr 12, 12 hours) and file C's (Mar 11–12, 13 hours) look
  in Stage 3 just like leak #1: never off, loaded 82–88% of the time, `DV_pressure` raised.
  One is six days before leak #1, the other in a file with no reported failure at all.
  They may be leaks that weren't written up; only the operator can say. That is the point
  of the review: it hands those hours to someone who can check.
- **`od` always ranks something.** File C has no reported failure and still has 18 hours
  over 1.5. "Nothing happened" can't be read off the ranking; a person reviewing the top
  episodes decides. The fixed 1.5 is a starting point, not a verdict.
- **AUROC counts unreported episodes against the agent.** If Apr 12 was a leak, the
  ranking is better than 0.974 says.

**Writes:** `eval_out/grade/grade.json`.

### Try it by hand

The same lifecycle with `curl` and `jq`, for one file:

```sh
set -a; source .env; set +a
ROOT="${ATAI_API_ENDPOINT%/}"; ROOT="${ROOT%/api}"; API="$ROOT/api"; AUTH="Authorization: Bearer $ATAI_API_KEY"

PRJ=$(curl -s -X POST "$API/projects" -H "$AUTH" -H "Content-Type: application/json" \
  -d '{"name": "Label-Free AD by hand"}' | jq -r .id)
COLS='["TP2","TP3","H1","DV_pressure","Reservoirs","Oil_temperature","Motor_current"]'
BLP=$(curl -s -X POST "$API/agents/blueprints/od/copy" -H "$AUTH" -H "Content-Type: application/json" \
  -d "$(jq -n --arg p "$PRJ" --argjson c "$COLS" '{project_id: $p, blueprint_key: "od-by-hand",
        overrides: {values: {timestamp_column: "timestamp", data_columns: $c, window_size: 360, step_size: 360}}}')" | jq -r .id)
PKG=$(curl -s -X POST "$API/agents/packages" -H "$AUTH" -H "Content-Type: application/json" \
  -d "{\"blueprint_ids\": [\"$BLP\"], \"target\": {\"kind\": \"platform\"}}" | jq -r .id)
curl -s "$API/agents/packages/$PKG" -H "$AUTH" | jq -r .status                       # until: ready
DPL=$(curl -s -X POST "$API/agents/deployments" -H "$AUTH" -H "Content-Type: application/json" \
  -d "{\"package_id\": \"$PKG\", \"kind\": \"batch\"}" | jq -r .id)
FILE=$(curl -s -X POST "$API/files" -H "$AUTH" \
  -F "file=@data/prepared/metropt_B.csv;type=text/csv;filename=metropt_B-$(date -u +%Y%m%dT%H%M%SZ).csv" | jq -r .file_id)
SES=$(curl -s -X POST "$API/agents/sessions" -H "$AUTH" -H "Content-Type: application/json" \
  -d "{\"deployment_id\": \"$DPL\", \"connectors\": {\"source\": [{\"type\": \"file\", \"id\": \"$FILE\"}]}}" | jq -r .id)
curl -s "$API/agents/sessions/$SES" -H "$AUTH" | jq '{status, error}'                # until: completed
REF=$(curl -s "$API/agents/sessions/$SES/results" -H "$AUTH" | jq -r '.data[0] | (.data.ref // .ref)')
curl -s "$ROOT$REF" -H "$AUTH" -o od-metropt_B.csv                                   # the ref already starts with /api
sort -t, -k5 -gr od-metropt_B.csv | head -5
```

File ids are file names, so upload under a new name each time: replacing a file a session
is reading can break it.

### Clean up the platform

```sh
python run/cleanup.py          # lists what would go
python run/cleanup.py --yes    # deletes it
```

Sessions (cancelled first if still going), the deployment (stopped first), the package,
the copy of `od`, then the project if nothing else is left in it. Uploaded files stay. An
object already gone counts as done, so a rerun finishes an interrupted cleanup.

## Results

Our run on production (2026-11-12), with a member key in a new project. An earlier run on
another deployment gave the same labels, episodes and grades, with scores within 3×10⁻⁶.

| stage | measure | result |
|---|---|---|
| 1 | raw checks; prepared-file checks | 8 PASS / 3 WARN; 18 PASS / 0 WARN |
| 2 | windows scored per file (A / B / C) | 375 / 376 / 394 of 401 / 409 / 423 |
| 4 | leak #1: AUROC, hours flagged, first flag | 0.974; 23 of 23; 2.3 h after the report's start |
| 4 | leak #4: AUROC, hours flagged, first flag | 0.997 (top 2 hours of the file); 4 of 4; **13.2 h before** the report's start |
| 4 | flagged hours not in a report (A / B / C) | 31 / 9 / 18, several with a leak's signature |

## What this says about the Label-Free Anomaly Discovery Agent

- **It works on data nobody has prepared it for.** No reference period, no labels, no
  tuning: one pass over a file found both reported leaks, one of them half a day early.
- **Its output is a ranking for a person, not a verdict.** It always finds something.
  Here that something is often worth a look, an unreported episode with a leak's exact
  signature, but deciding needs someone who knows the machine.
- **It needs anomalies to be rare in the file.** Files of three weeks with leaks of 4–24
  hours suit it. A file that is mostly fault would hide the fault from it; Stage 1c prints
  the limit.
- **A description of each episode makes the ranking usable.** Stage 3's summary shows how
  much a "which sensors, and how" view adds to the scores alone.

## Repo layout

| path | what it is |
|---|---|
| `common.py` | paths, the files' dates, the channels, the reports (read by Stage 4 only) |
| `od_api.py` | a small standard-library client for the Lifecycle 2.0 calls |
| `prep/download.py` | Stage 0 |
| `prep/preflight_raw.py`, `prep/prepare.py`, `prep/preflight.py` | Stages 1a, 1b, 1c |
| `run/discover.py` | Stage 2, the platform run |
| `run/review.py`, `run/grade.py` | Stages 3 and 4: post-processing of the agent's output, local |
| `run/cleanup.py` | deletes what Stage 2 made |
| `data/prepared/` | the three files (Stage 1b) |
| `eval_out/` | every stage's output from the run above |

## Licence

- **The code and documentation:** Apache License 2.0 ([LICENSE](LICENSE)).
- **The data files in `data/prepared/`:** derived from MetroPT-3 and licensed under
  [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/), like the original; **not**
  Apache-2.0. Their attribution is below and in [`data/prepared/README.md`](data/prepared/README.md),
  which travels with them.
- **`eval_out/`:** the outputs of our run (scores, episodes, grades). They contain no
  values from the dataset beyond timestamps, and are under the Apache License 2.0.

## Data attribution

The data in `data/prepared/` is derived from the **MetroPT-3 Dataset**: Davari, N.,
Veloso, B., Ribeiro, R., & Gama, J. (2021), UCI Machine Learning Repository,
[doi:10.24432/C5VW3R](https://doi.org/10.24432/C5VW3R)
([dataset page](https://archive.ics.uci.edu/dataset/791/metropt+3+dataset)), licensed
under the [Creative Commons Attribution 4.0 International License](https://creativecommons.org/licenses/by/4.0/). Introductory paper: Davari, N.,
Veloso, B., Ribeiro, R. P., Pereira, P. M., & Gama, J. (2021), *Predictive maintenance
based on anomaly detection using deep learning for air production unit in the railway
industry*, IEEE DSAA 2021. The maintenance reports in `common.py` and in this README are
quoted from the dataset page.

**What was changed** (November 2026, by `prep/prepare.py`): the raw samples were snapped to a 10 s grid (short holes
forward-filled, longer gaps left as gaps), stretches where the logger froze were removed,
three date ranges were cut out, and only the 7 analog channels were kept. Timestamps are
the dataset's own clock, written as seconds since 1970. The authors and their institutions
are not involved in this example and do not endorse it.
