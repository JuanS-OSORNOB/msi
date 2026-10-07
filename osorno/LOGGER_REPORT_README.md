# DigiSolo log reporting

`digisolo_report.py` reads `[SectionNNNNN]` headers and `key = value` entries.
It creates a PDF summary, five groups of PNG figures for this log, JSON data,
and CSV tables. It does not read seismic waveforms from the DLD files.


## Run with the local environment already installed

In PowerShell, from this folder:

```powershell
& '.\.logger_venv\Scripts\python.exe' digisolo_report.py DigiSolo.LOG
```

DEFAULTS:
Without arguments, the script looks for `DigiSolo.LOG` beside the Python file.
The default output directory is `DigiSolo_summary` beside the input log.
Running it again replaces reports and exports with the same output names.

## Run on another computer

Python 3.10 or newer is required. Install the two reporting dependencies:

```powershell
python -m pip install -r logger_requirements.txt
python digisolo_report.py 'C:\path\to\another.LOG' --output-dir 'C:\path\to\report'
```

Matplotlib creates the figures; ReportLab creates the PDF. PyMuPDF was installed
locally only to render and check the PDF; the reporting script does not need it.
The `.logger_venv` folder is local to this computer; recreate it when moving computers.

Other useful commands:

```powershell
python digisolo_report.py DigiSolo.LOG --format plots
python digisolo_report.py DigiSolo.LOG --parse-only
python digisolo_report.py DigiSolo.LOG --voltage-threshold 6.5
python digisolo_report.py another.LOG --encoding cp1252
```

`--parse-only` needs only the Python standard library. `--format pdf` and
`--format both` create the PDF and retain its PNG figures. `--format plots`
creates PNG figures and data exports. `--voltage-threshold` draws a line at a
value explicitly chosen by you; it does not infer a threshold from device codes.

## Example contents of a log

There are 50,104 sections in eight families:

| Family | Records | Contents |
|---|---:|---|
| DeviceInfo | 2 | Boot settings, device identity, channel checks, SD information |
| BatteryPowerOnStop | 1 | Empty, untimed marker |
| Notify | 18 | Acquisition start and file changes |
| GPS | 34,614 | 11,115 Cycle On, 11,115 Cycle Off, 12,384 Synchronization records |
| Temperature | 9,942 | Temperature and UTC time |
| Battery | 3,345 | Voltage and UTC time |
| Memory | 2,180 | Total, used, available counters and UTC time |
| Error | 2 | Device-reported errors |

The numeric tuple before the first section is retained as an opaque preamble.
Timed records span 2026-07-03 05:54:09 through 2026-09-11 06:28:31 UTC,
about 70 days. `Start Date` is a configuration field, not the observed beginning
of this log. `Boot RTC` contains a 2015 value and is not used for coverage.

The first error, at 2026-08-08 23:59:43 UTC, says
`Wrong 1pps time(1870659584,1124933)`.
The second, at 2026-08-20 02:56:07 UTC, has **two Error_Type entries**:
`Battery Low Warning` and `Compared Voltage    6.499,   6.500`.
Both entries are kept in the PDF event list, events.csv, and the raw JSON.

Voltage ranges from 6.0904 to 8.1721; temperature ranges from 9.625 to 45.875.
V and degrees C are conventional assumptions because the file supplies no units.
The final storage counters are 26,600 used and 94,383 available out of 120,983,
or 21.99% used. The absolute memory units are not stated.

## Decisions and reasons

- Parse headers directly instead of using a strict INI parser: section families
  have numeric suffixes, and repeated keys carry useful information.
- Keep raw pairs and source line numbers: every reported observation can be
  traced back to the log. Plots use the last repeated scalar key within a section;
  event details preserve every pair, including repeated Error_Type messages.
- Use record `UTC Time` and sort each measurement series: boot clocks and GPS-fix
  clocks describe other instants and should not determine coverage.
- Plot all valid samples as points without smoothing or interpolation: this
  preserves spikes and avoids suggesting continuity across gaps.
- Preserve outliers: reported GPS scatter can reflect fix quality and does not
  establish instrument movement. A separate percentile zoom changes only the
  display limits; the full view and exports keep the outliers.
- Show storage percentage: it has a clear meaning without guessing whether the
  raw counters represent MB, blocks or another unit.
- Label assumed and unspecified units: phase error, DAC, tick and test units
  cannot be safely inferred from field names alone. The raw threshold `650,600`
  is not automatically divided by 100 or interpreted as voltage thresholds.
- Treat status counts as record counts: they are not GPS duty-cycle durations.
- Treat RTC-minus-UTC and fix age as timestamp comparisons: logging latency and
  asynchronous updates can affect them; they are not calibrated clock-error tests.
- Flag gaps over three times a metric's median positive interval for review:
  this heuristic concerns logger observations, not waveform completeness.

Unknown section families are exported. Their timed numeric scalar fields are
also plotted. UTF-8 and UTF-16 BOMs are detected; Windows cp1252 is a documented
fallback. Malformed timestamps are reported and excluded from timed plots while
their raw records remain available. `--strict` rejects malformed UTC values,
unparsed section lines and duplicate keys; this supplied log intentionally fails
strict mode because its second error has repeated Error_Type keys.

## Output files

- `DigiSolo_summary.pdf`: inventory, statistics, figures, boot comparisons,
  complete event list and interpretation notes.
- `figures/`: reusable PNG figures.
- `summary.json`: coverage, counts, measurement statistics, warnings and decisions.
- `parsed_log.json`: all sections, key/value pairs and unparsed content, in source order.
- `csv/`: one wide table per section family; scalar columns use the last duplicate.
- `events.csv`: source lines, UTC times and all event pairs.

Validation covered the full supplied log plus synthetic examples with repeated
sections, duplicate keys, unordered timestamps, unfamiliar sensors, invalid
values, UTF-8/UTF-16 BOMs, and derived GPS/storage measurements. Every PDF page
was rendered and visually reviewed.
