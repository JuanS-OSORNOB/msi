"""Plot miniSEED coverage after the three-step time extraction workflow.

Reads each identifier's summarize_msi.csv and gaps_msi.csv, using the directory
name as the full identifier (the summary CSV only stores its last four digits).
Naive timestamps from the summary are interpreted as UTC, as in MSI output.
Coverage and gaps reflect the upstream summarizer's interval convention.

Run from the repository root (requires matplotlib):
    python osorno/visualize_timeline.py
    python osorno/visualize_timeline.py osorno/SPZ/2026/DEPLOYMENT_01 --show
    python osorno/visualize_timeline.py --ids 453039009 453039078 --output /tmp/gaps.pdf

Defaults to SPZ/2026/DEPLOYMENT_01 beside this script. Saves a PNG and an exact
per-component CSV report. --show also opens a window with zoom/pan controls.
--tolerance-seconds controls comparisons between components; gaps still display
at their original size. This viewer does not read or change the miniSEED files.
"""

import argparse
import csv
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path


COMPONENTS = ("E", "N", "Z")
COLORS = {"E": "#247ba0", "N": "#368f55", "Z": "#7953a9"}
GAP_COLOR = "#c62828"
WARNING_COLOR = "#b85c00"


def timestamp(value):
    parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def read_csv(path, required):
    with path.open(newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        missing = set(required) - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"{path}: missing columns {', '.join(sorted(missing))}")
        return list(reader)


@dataclass
class Channel:
    start: datetime
    end: datetime
    expected_gaps: int
    gaps: list = field(default_factory=list)

    @property
    def gap_seconds(self):
        return sum((end - start).total_seconds() for start, end in self.gaps)

    @property
    def segments(self):
        cursor = self.start
        segments = []
        for start, end in self.gaps:
            if cursor < start:
                segments.append((cursor, start))
            cursor = end
        if cursor < self.end:
            segments.append((cursor, self.end))
        return segments


def load_node(directory):
    channels = {}
    for row in read_csv(directory / "summarize_msi.csv",
                        ("Channel", "First_Start", "Last_End", "Number_of_Gaps")):
        name = row["Channel"].strip()
        if name not in COMPONENTS or name in channels:
            raise ValueError(f"{directory}: unexpected or duplicate component {name!r}")
        start, end = timestamp(row["First_Start"]), timestamp(row["Last_End"])
        count = int(row["Number_of_Gaps"])
        if end < start or count < 0:
            raise ValueError(f"{directory}: invalid range or gap count for {name}")
        channels[name] = Channel(start, end, count)
    if not channels:
        raise ValueError(f"{directory}: empty summary")
    # Require this file even for zero gaps: its header is written by step three.
    for row in read_csv(directory / "gaps_msi.csv", ("Channel", "Start", "End")):
        name = row["Channel"].strip()
        if name not in channels:
            raise ValueError(f"{directory}: gap references unknown component {name!r}")
        start, end = timestamp(row["Start"]), timestamp(row["End"])
        channel = channels[name]
        if not channel.start <= start < end <= channel.end:
            raise ValueError(f"{directory}: gap outside {name}'s coverage range")
        channel.gaps.append((start, end))
    for name, channel in channels.items():
        channel.gaps.sort()
        if len(channel.gaps) != channel.expected_gaps:
            raise ValueError(f"{directory}: {name} gap count differs between CSVs; "
                             "rerun summarize_msi.py for this identifier")
        if any(right[0] < left[1] for left, right in
               zip(channel.gaps, channel.gaps[1:])):
            raise ValueError(f"{directory}: overlapping gaps for {name}; "
                             "check the upstream summary")
    return channels


def compare_channels(channels, tolerance):
    starts = [channel.start for channel in channels.values()]
    ends = [channel.end for channel in channels.values()]
    start_spread = (max(starts) - min(starts)).total_seconds()
    end_spread = (max(ends) - min(ends)).total_seconds()
    issues = []
    missing = [name for name in COMPONENTS if name not in channels]
    if missing:
        issues.append("missing " + "/".join(missing))
    if start_spread > tolerance:
        issues.append("start mismatch")
    if end_spread > tolerance:
        issues.append("end mismatch")
    reference = next(iter(channels.values())).gaps
    for channel in channels.values():
        if len(channel.gaps) != len(reference) or any(
            abs((a - b).total_seconds()) > tolerance
            for pair, other in zip(channel.gaps, reference)
            for a, b in zip(pair, other)
        ):
            issues.append("gap mismatch")
            break
    return issues, start_spread, end_spread


def write_report(nodes, path, tolerance):
    fields = ["Identifier", "Component", "Status", "First_Start_UTC", "Last_End_UTC",
              "Start_Spread_seconds", "End_Spread_seconds", "Start_Delay_seconds",
              "End_Shortfall_seconds", "Number_of_Gaps", "Gap_seconds",
              "Longest_Gap_seconds", "Data_seconds", "Coverage_percent"]
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for identifier, channels in nodes.items():
            issues, start_spread, end_spread = compare_channels(channels, tolerance)
            earliest = min(channel.start for channel in channels.values())
            latest = max(channel.end for channel in channels.values())
            for name in COMPONENTS:
                row = dict(Identifier=identifier, Component=name,
                           Status="; ".join(issues) if issues else "aligned",
                           Start_Spread_seconds=start_spread, End_Spread_seconds=end_spread)
                if name in channels:
                    channel = channels[name]
                    span = (channel.end - channel.start).total_seconds()
                    data = span - channel.gap_seconds
                    row.update(First_Start_UTC=channel.start.isoformat(),
                               Last_End_UTC=channel.end.isoformat(),
                               Start_Delay_seconds=(channel.start - earliest).total_seconds(),
                               End_Shortfall_seconds=(latest - channel.end).total_seconds(),
                               Number_of_Gaps=len(channel.gaps), Gap_seconds=channel.gap_seconds,
                               Longest_Gap_seconds=max(((b-a).total_seconds() for a, b in
                                                        channel.gaps), default=0),
                               Data_seconds=data,
                               Coverage_percent=100 * data / span if span else "")
                else:
                    row["Status"] = "missing component; " + row["Status"]
                writer.writerow(row)


def plot_timeline(nodes, output, tolerance, title, show=False):
    # Select the non-GUI backend before importing pyplot for file-only runs.
    import matplotlib
    if not show:
        matplotlib.use("Agg")
    import matplotlib.dates as dates
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    from matplotlib.patches import Patch

    figure, axis = plt.subplots(figsize=(16, max(5, len(nodes) * 0.86 + 2.8)))
    ticks, labels, label_colors = [], [], []
    warning_count = 0
    total_gaps = 0
    for index, (identifier, channels) in enumerate(nodes.items()):
        issues, start_spread, end_spread = compare_channels(channels, tolerance)
        warning_count += bool(issues)
        y_base = index * 4
        axis.axhspan(y_base - 0.6, y_base + 2.6,
                     color="#fff0df" if issues else ("#f3f5f7" if index % 2 == 0 else "white"),
                     zorder=0)
        earliest = min(channel.start for channel in channels.values())
        latest = max(channel.end for channel in channels.values())
        status = " / ".join(issues) if issues else "aligned"
        node_gaps = sum(len(channel.gaps) for channel in channels.values())
        total_gaps += node_gaps
        axis.text(1.01, y_base + 1, f"{status}\n{node_gaps} component gaps",
                  transform=axis.get_yaxis_transform(), va="center", fontsize=8,
                  color=WARNING_COLOR if issues else "#555555")
        for offset, name in enumerate(COMPONENTS):
            y = y_base + offset
            ticks.append(y)
            labels.append(f"{identifier}  {name}")
            label_colors.append(WARNING_COLOR if issues else "#333333")
            if name not in channels:
                axis.text(dates.date2num(earliest), y, "MISSING", va="center",
                          fontsize=9, color=GAP_COLOR, fontweight="bold")
                continue
            channel = channels[name]

            def bars(intervals, color, **kwargs):
                spans = [(dates.date2num(a), dates.date2num(b) - dates.date2num(a))
                         for a, b in intervals]
                if spans:
                    axis.broken_barh(spans, (y - 0.28, 0.56), facecolors=color, **kwargs)

            bars(channel.segments, COLORS[name], zorder=2)
            bars(channel.gaps, GAP_COLOR, zorder=3)
            # Fixed-size ticks keep even sub-second gaps visible when zoomed out.
            for a, b in channel.gaps:
                axis.plot(dates.date2num(a + (b-a)/2), y, marker="|", color=GAP_COLOR,
                          markersize=10, markeredgewidth=1.5, zorder=4)
            shortfalls = []
            if (channel.start - earliest).total_seconds() > tolerance:
                shortfalls.append((earliest, channel.start))
            if (latest - channel.end).total_seconds() > tolerance:
                shortfalls.append((channel.end, latest))
            bars(shortfalls, "#ffce91", hatch="///", edgecolors=WARNING_COLOR, zorder=1)
            for value, spread in ((channel.start, start_spread), (channel.end, end_spread)):
                if spread > tolerance:
                    axis.plot(dates.date2num(value), y, marker="D", color=WARNING_COLOR,
                              markersize=4, zorder=5)
            if channel.start == channel.end:
                axis.plot(dates.date2num(channel.start), y, marker="o", color=COLORS[name])

    axis.set_yticks(ticks, labels, fontsize=8)
    for label, color in zip(axis.get_yticklabels(), label_colors):
        label.set_color(color)
    axis.set_ylim(len(nodes) * 4 - 0.7, -0.8)
    locator = dates.AutoDateLocator(tz=timezone.utc)
    axis.xaxis.set_major_locator(locator)
    axis.xaxis.set_major_formatter(dates.ConciseDateFormatter(locator, tz=timezone.utc))
    axis.grid(axis="x", color="#dddddd", linewidth=0.6)
    axis.set_axisbelow(True)
    axis.margins(x=0.02)
    axis.set_xlabel("Time (UTC)")
    axis.set_title(f"{title}\n{len(nodes)} identifiers | {warning_count} with component differences "
                   f"| {total_gaps} component gaps", loc="left", fontsize=12, pad=14)
    legend = [Patch(color=COLORS[name], label=name) for name in COMPONENTS]
    legend += [Patch(color=GAP_COLOR, label="Gap"),
               Line2D([], [], color=GAP_COLOR, marker="|", linestyle="None",
                      markersize=10, label="Small gap marker"),
               Patch(facecolor="#ffce91", edgecolor=WARNING_COLOR, hatch="///",
                     label="Start/end shortfall"),
               Line2D([], [], color=WARNING_COLOR, marker="D", linestyle="None",
                      label="Different start/end")]
    figure.legend(handles=legend, loc="lower center", ncol=7, fontsize=8,
                  bbox_to_anchor=(0.5, 0.035))
    figure.text(0.5, 0.016, f"Comparison tolerance: {tolerance:g} s. Red ticks mark gaps at any scale; "
                "their width is symbolic. Exact times and durations are in the CSV report.",
                ha="center", fontsize=8, color="#555555")
    figure.subplots_adjust(left=0.13, right=0.81, bottom=0.12, top=0.92)
    figure.savefig(output, dpi=180)
    if show:
        plt.show()
    plt.close(figure)


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    default = Path(__file__).resolve().parent / "SPZ" / "2025" / "DEPLOYMENT_02" #NOTE : Change this default to the deployment you want to visualize.
    parser.add_argument("deployment", nargs="?", type=Path, default=default,
                        help="deployment directory containing identifier subdirectories")
    parser.add_argument("--ids", nargs="+", help="only plot these identifier directory names")
    parser.add_argument("--output", type=Path, help="image path (.png, .pdf, or .svg); "
                        "default: DEPLOYMENT/timeline.png")
    parser.add_argument("--tolerance-seconds", type=float, default=0,
                        help="allowed E/N/Z start, end, and gap boundary difference (default: 0)")
    parser.add_argument("--show", action="store_true", help="also open a zoomable plot window")
    args = parser.parse_args()
    if not 0 <= args.tolerance_seconds < float("inf"):
        parser.error("--tolerance-seconds must be finite and nonnegative")
    if not args.deployment.is_dir():
        parser.error(f"deployment directory does not exist: {args.deployment}")
    directories = sorted(path for path in args.deployment.iterdir() if path.is_dir())
    if args.ids:
        missing = set(args.ids) - {path.name for path in directories}
        if missing:
            parser.error(f"identifier directories not found: {', '.join(sorted(missing))}")
        directories = [path for path in directories if path.name in args.ids]
    if not directories:
        parser.error("no identifier directories found")
    output = args.output or args.deployment / "timeline.png"
    if output.suffix.lower() not in (".png", ".pdf", ".svg"):
        parser.error("--output must end in .png, .pdf, or .svg")
    try:
        nodes = {path.name: load_node(path) for path in directories}
        output.parent.mkdir(parents=True, exist_ok=True)
        title = " / ".join(args.deployment.resolve().parts[-3:])
        plot_timeline(nodes, output, args.tolerance_seconds, title, args.show)
        report = output.with_name(output.stem + "_report.csv")
        write_report(nodes, report, args.tolerance_seconds)
    except (OSError, ValueError, ImportError) as error:
        parser.exit(1, f"Error: {error}\n")
    print(f"Timeline: {output.resolve()}")
    print(f"Exact times and coverage: {report.resolve()}")
    for identifier, channels in nodes.items():
        issues, start_spread, end_spread = compare_channels(channels, args.tolerance_seconds)
        if issues:
            print(f"{identifier}: {', '.join(issues)} "
                  f"(start spread {start_spread:g} s, end spread {end_spread:g} s)")


if __name__ == "__main__":
    main()
