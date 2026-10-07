#!/usr/bin/env python3
"""Summarize DigiSolo and similarly structured [Section123] key=value logs.

Python 3.10+. Install: python -m pip install matplotlib reportlab
Run: python digisolo_report.py DigiSolo.LOG
Outputs: PDF, PNG figures, section CSVs, events.csv, summary.json, parsed_log.json.
Use --format plots or --parse-only to omit the PDF or all plotting dependencies.
Input is treated as data: no field, filename, or embedded text is executed.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import re
import statistics
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape

UTC = timezone.utc
HEADER = re.compile(r'^\[([^\]]+)\]\s*(?:[;#].*)?$')
NUMBER = re.compile(r'^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$')
KNOWN = {'DeviceInfo', 'GPS', 'Temperature', 'Battery', 'Memory', 'Notify', 'Error', 'BatteryPowerOnStop'}
DESCRIPTIONS = {
    'DeviceInfo': 'Boot/configuration, channel self-tests and storage identity',
    'GPS': 'Power-cycle, synchronization, location, satellites and orientation',
    'Temperature': 'Temperature observations',
    'Battery': 'Battery voltage observations',
    'Memory': 'Total, available and used storage counters',
    'Notify': 'Acquisition start and acquisition file changes',
    'Error': 'Device-reported errors, retained verbatim',
    'BatteryPowerOnStop': 'Power-stop marker; meaning not decoded',
}
# Units absent from the file stay explicitly unspecified. Conventional physical
# units are identified as assumptions rather than hidden conversions.
METRICS = [
    ('Battery', 'Voltage', 'V (assumed)'),
    ('Temperature', 'Temperature', 'deg C (assumed)'),
    ('Memory', 'Used Memory', 'logged units'),
    ('Memory', 'Available Memory', 'logged units'),
    ('GPS', 'Satellite Number', 'count'),
    ('GPS', 'Phase Error', 'unspecified'),
    ('GPS', 'Altitude', 'm (assumed; datum unknown)'),
    ('GPS', 'eCompass North', 'deg (assumed)'),
    ('GPS', 'Tilted Angle', 'deg (assumed)'),
    ('GPS', 'Roll Angle', 'deg (assumed)'),
    ('GPS', 'Pitch Angle', 'deg (assumed)'),
]


def clean(value: str) -> str:
    value = value.strip()
    return value[1:-1].strip() if len(value) >= 2 and value[0] == value[-1] and value[0] in '\"\'' else value


def number(value: str | None) -> float | None:
    if value is None or not NUMBER.fullmatch(clean(value)):
        return None
    result = float(clean(value))
    return result if math.isfinite(result) else None


def numbers(value: str | None) -> list[float]:
    if value is None:
        return []
    parts = [number(v.strip()) for v in clean(value).split(',')]
    return [v for v in parts if v is not None] if all(v is not None for v in parts) else []


def timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    value = clean(value)
    for fmt in ('%Y/%m/%d,%H:%M:%S', '%Y/%m/%d,%H:%M:%S.%f', '%Y-%m-%d,%H:%M:%S'):
        try:
            return datetime.strptime(value, fmt).replace(tzinfo=UTC)
        except ValueError:
            pass
    try:
        result = datetime.fromisoformat(value.replace('Z', '+00:00'))
        return result.replace(tzinfo=UTC) if result.tzinfo is None else result.astimezone(UTC)
    except ValueError:
        return None


def norm(value: str) -> str:
    return re.sub(r'\s+', ' ', value.strip()).casefold()


@dataclass
class Section:
    name: str
    family: str
    line: int
    pairs: list[tuple[str, str]] = field(default_factory=list)
    unparsed: list[tuple[int, str]] = field(default_factory=list)
    fields: dict[str, str] = field(default_factory=dict)

    def get(self, key: str) -> str | None:
        return self.fields.get(norm(key))

    @property
    def time(self) -> datetime | None:
        # Other clock fields never substitute for the record's UTC timestamp.
        return timestamp(self.get('UTC Time'))


def parse_log(source: Path, encoding: str | None = None) -> tuple[list[Section], dict]:
    """Stream lines; keep repeated sections, duplicate keys and unparsed text."""
    warnings: list[str] = []
    if not encoding:
        with source.open('rb') as handle:
            prefix = handle.read(4)
        if prefix.startswith((b'\xff\xfe', b'\xfe\xff')):
            encoding = 'utf-16'
        else:
            encoding = 'utf-8-sig'
            try:
                with source.open(encoding=encoding) as handle:
                    for _ in handle:
                        pass
            except UnicodeDecodeError:
                encoding = 'cp1252'
                warnings.append('UTF-8 decoding failed; using Windows cp1252. Override with --encoding if needed.')
    sections: list[Section] = []
    preamble: list[tuple[int, str]] = []
    current: Section | None = None
    duplicates = 0
    with source.open(encoding=encoding, errors='strict') as handle:
        for line_no, raw in enumerate(handle, 1):
            line = raw.strip()
            if not line or line.startswith((';', '#')):
                continue
            match = HEADER.fullmatch(line)
            if match:
                name = match[1].strip()
                family = re.sub(r'\d+$', '', name)
                family = next((f for f in KNOWN if f.casefold() == family.casefold()), family)
                current = Section(name, family, line_no)
                sections.append(current)
            elif current is None:
                preamble.append((line_no, raw.rstrip('\r\n')))
            elif '=' in line:
                key, value = line.split('=', 1)
                key, value = key.strip(), clean(value)
                if not key:
                    current.unparsed.append((line_no, raw.rstrip('\r\n')))
                    continue
                duplicates += norm(key) in current.fields
                current.pairs.append((key, value))
                current.fields[norm(key)] = value
            else:
                current.unparsed.append((line_no, raw.rstrip('\r\n')))
    if not sections:
        raise ValueError('No [section] headers found; expected a DigiSolo-style sectioned key=value log.')
    if duplicates:
        warnings.append(f'{duplicates} duplicate keys: raw pairs preserved; plots use the last occurrence within each section.')
    odd = sum(len(s.unparsed) for s in sections)
    if odd:
        warnings.append(f'{odd} non-key/value lines inside sections were retained but not interpreted.')
    invalid = sum(s.get('UTC Time') is not None and s.time is None for s in sections)
    if invalid:
        warnings.append(f'{invalid} invalid UTC timestamps; records retained but omitted from time-series plots.')
    if preamble:
        warnings.append('Preamble/header retained verbatim; its numeric tuple is not decoded without a format specification.')
    return sections, {'encoding': encoding, 'preamble': preamble, 'warnings': warnings}


def series(sections: list[Section], family: str, key: str) -> list[tuple[datetime, float]]:
    result = [(s.time, number(s.get(key))) for s in sections if s.family == family]
    return sorted((t, v) for t, v in result if t is not None and v is not None)


def stats(points: list[tuple[datetime, float]]) -> dict:
    values = [v for _, v in points]
    if not values:
        return {'count': 0}
    result = {'count': len(values), 'min': min(values), 'median': statistics.median(values),
              'max': max(values), 'first': values[0], 'last': values[-1]}
    intervals = [(b[0] - a[0]).total_seconds() for a, b in zip(points, points[1:])]
    positive = [v for v in intervals if v > 0]
    if positive:
        cadence = statistics.median(positive)
        result.update(median_interval_seconds=cadence, max_gap_seconds=max(positive),
                      gaps_over_3x_median=sum(v > 3 * cadence for v in positive))
    result['duplicate_timestamps'] = sum(v == 0 for v in intervals)
    return result


def summarize(source: Path, sections: list[Section], meta: dict) -> dict:
    times = [s.time for s in sections if s.time]
    counts = Counter(s.family for s in sections)
    events = [{'section': s.name, 'line': s.line, 'utc': s.time.isoformat() if s.time else None,
               'fields': dict(s.pairs), 'pairs': s.pairs} for s in sections
              if s.family in {'Error', 'Notify', 'BatteryPowerOnStop'}]
    warnings = list(meta['warnings'])
    devices = [s for s in sections if s.family == 'DeviceInfo']
    if any(s.get('Boot RTC') and (timestamp(s.get('Boot RTC')) is None or
           (times and timestamp(s.get('Boot RTC')).year != min(times).year)) for s in devices):
        warnings.append('Boot RTC is invalid or in a different year from timed observations; excluded from coverage dates.')
    if any(s.family == 'GPS' and number(s.get('Leap Second')) == 0 for s in sections):
        warnings.append('Some GPS records report Leap Second = 0; UTC fields are used as logged, without automatic correction.')
    backwards = defaultdict(int)
    previous = {}
    for s in sections:
        if s.time:
            if s.family in previous and s.time < previous[s.family]:
                backwards[s.family] += 1
            previous[s.family] = s.time
    if backwards:
        warnings.append(f'Out-of-order timestamps by family: {dict(backwards)}. Plots sort by UTC; exports preserve source order.')
    unknown = sorted(set(counts) - KNOWN)
    if unknown:
        warnings.append('Additional section families retained/exported: ' + ', '.join(unknown))
    return {
        'source': str(source.resolve()), 'source_bytes': source.stat().st_size,
        'encoding': meta['encoding'], 'section_count': len(sections), 'section_counts': dict(counts),
        'utc_start': min(times).isoformat() if times else None,
        'utc_end': max(times).isoformat() if times else None,
        'span_days': (max(times) - min(times)).total_seconds() / 86400 if times else None,
        'gps_status_counts': dict(Counter(s.get('GPS Status') for s in sections if s.family == 'GPS' and s.get('GPS Status'))),
        'metrics': {f'{f}.{k}': {'unit': u, **stats(series(sections, f, k))} for f, k, u in METRICS},
        'events': events, 'warnings': warnings, 'preamble': meta['preamble'],
        'decisions': [
            'Use record UTC Time for coverage and chronological plots; preserve other clocks separately.',
            'Group headers by trailing numeric suffix; retain every original section and source line.',
            'Preserve outliers and unknown fields. No automatic filtering, interpolation or unit conversion.',
            'Temperature deg C, voltage V, angles deg, coordinates deg and altitude m are conventional assumptions, not declared units.',
            'Memory is in unspecified logged units; use Used/Total*100 for storage percentage.',
            'Phase Error, GPS Tick, gains and diagnostic units are not decoded. Voltage Threshold is retained raw.',
            'Coordinate scatter describes reported fixes, not confirmed movement; zoom is display-only.',
            'RTC minus record UTC and latest-fix age compare logged timestamps; neither alone proves a clock fault.',
            'A gap over three times median positive cadence is a review flag, not proof of lost acquisition.',
            'Log end is an observation boundary, not evidence of shutdown. DLD waveforms are separate files.',
        ],
    }


def export_data(out: Path, sections: list[Section], summary: dict) -> None:
    out.mkdir(parents=True, exist_ok=True)
    (out / 'summary.json').write_text(json.dumps(summary, indent=2, allow_nan=False), encoding='utf-8')
    raw = {'preamble': summary['preamble'], 'sections': [
        {'name': s.name, 'family': s.family, 'line': s.line, 'pairs': s.pairs, 'unparsed': s.unparsed} for s in sections]}
    (out / 'parsed_log.json').write_text(json.dumps(raw, indent=2, allow_nan=False), encoding='utf-8')
    csv_dir = out / 'csv'
    csv_dir.mkdir(exist_ok=True)
    groups = defaultdict(list)
    for s in sections:
        groups[s.family].append(s)
    for index, (family, records) in enumerate(groups.items(), 1):
        keys = sorted({k for s in records for k in s.fields})
        safe = re.sub(r'[^A-Za-z0-9_-]', '_', family)[:60] or 'section'
        with (csv_dir / f'{index:02d}_{safe}.csv').open('w', newline='', encoding='utf-8-sig') as handle:
            writer = csv.writer(handle)
            writer.writerow(['_section', '_source_line', '_utc_iso', *keys])
            for s in records:
                writer.writerow([s.name, s.line, s.time.isoformat() if s.time else '', *[s.fields.get(k, '') for k in keys]])
    with (out / 'events.csv').open('w', newline='', encoding='utf-8-sig') as handle:
        writer = csv.writer(handle)
        writer.writerow(['section', 'source_line', 'utc', 'details'])
        for e in summary['events']:
            writer.writerow([e['section'], e['line'], e['utc'] or '', json.dumps(e['pairs'])])


def derived(sections: list[Section], kind: str) -> list[tuple[datetime, float]]:
    points = []
    for s in sections:
        t = s.time
        if t is None:
            continue
        value = None
        if kind == 'memory_percent' and s.family == 'Memory':
            used, total = number(s.get('Used Memory')), number(s.get('Total Memory'))
            if used is not None and total is not None and total > 0:
                value = 100 * used / total
        elif kind == 'strength' and s.family == 'GPS':
            values = numbers(s.get('GPS Strength'))
            if values:
                value = statistics.mean(values)
        elif kind in {'fix_age', 'rtc_difference'} and s.family == 'GPS':
            other = timestamp(s.get('Latest Fix UTC Time' if kind == 'fix_age' else 'RTC Time'))
            if other:
                value = (t - other).total_seconds() if kind == 'fix_age' else (other - t).total_seconds()
        if value is not None and math.isfinite(value):
            points.append((t, value))
    return sorted(points)


def make_figures(out: Path, sections: list[Section], voltage_threshold: float | None = None):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    import numpy as np
    plt.rcParams.update({'font.size': 10, 'axes.titlesize': 12, 'axes.labelsize': 10,
                         'figure.dpi': 110, 'savefig.dpi': 170, 'axes.spines.top': False,
                         'axes.spines.right': False})
    folder = out / 'figures'
    folder.mkdir(exist_ok=True)
    figures = []

    def plot(ax, points, title, label, color='#186c9c'):
        ax.set_title(title, loc='left', fontweight='bold')
        ax.set_ylabel(label)
        ax.grid(alpha=.2)
        if points:
            ax.plot([t for t, _ in points], [v for _, v in points], '.', ms=1.9, alpha=.6, color=color)
            locator = mdates.AutoDateLocator(minticks=3, maxticks=5, tz=UTC)
            ax.xaxis.set_major_locator(locator)
            ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(locator, tz=UTC))
            ax.set_xlabel('Record time (UTC)')
        else:
            ax.text(.5, .5, 'No valid timed observations', ha='center', transform=ax.transAxes)

    def save(fig, name, title, caption):
        dest = folder / f'{name}.png'
        fig.savefig(dest, facecolor='white')
        plt.close(fig)
        figures.append((title, dest, caption))

    if any(s.family in {'Battery', 'Temperature', 'Memory'} or s.get('Phase Error') for s in sections):
        fig, axes = plt.subplots(4, 1, figsize=(8, 8.8), layout='constrained')
        plot(axes[0], series(sections, 'Battery', 'Voltage'), 'Battery voltage', 'V (assumed)')
        if voltage_threshold is not None:
            axes[0].axhline(voltage_threshold, color='#b84432', ls='--', label='User-supplied threshold')
            axes[0].legend(fontsize=8)
        plot(axes[1], series(sections, 'Temperature', 'Temperature'), 'Logger temperature', 'deg C (assumed)', '#a65b17')
        plot(axes[2], derived(sections, 'memory_percent'), 'Storage utilization', 'Used / total (%)', '#237a52')
        plot(axes[3], series(sections, 'GPS', 'Phase Error'), 'GPS synchronization phase', 'Logged phase error')
        save(fig, '01_operations', 'Power, temperature, storage and synchronization',
             'All valid samples are shown as points. No interpolation or smoothing. Memory percentage avoids assuming counter units; phase-error units are unspecified.')
    gps = [s for s in sections if s.family == 'GPS']
    if gps:
        fig, axes = plt.subplots(4, 1, figsize=(8, 8.8), layout='constrained')
        plot(axes[0], series(sections, 'GPS', 'Satellite Number'), 'Satellites reported', 'Count')
        plot(axes[1], derived(sections, 'strength'), 'Mean reported satellite strength', 'Logged units')
        plot(axes[2], series(sections, 'GPS', 'Altitude'), 'GPS altitude', 'm (assumed)', '#237a52')
        plot(axes[3], derived(sections, 'fix_age'), 'Record UTC minus latest-fix UTC', 'Seconds')
        save(fig, '02_gps_quality', 'GPS observations and fix age',
             'Satellite strength is the arithmetic mean of each numeric list. Fix age may be negative when timestamp fields describe different instants. No position outliers are removed.')
        coords = [(number(s.get('Longitude')), number(s.get('Latitude'))) for s in gps]
        coords = [(x, y) for x, y in coords if x is not None and y is not None and -180 <= x <= 180 and -90 <= y <= 90]
        if coords:
            x, y = np.array(coords).T
            fig, axes = plt.subplots(2, 1, figsize=(8, 8.8), layout='constrained')
            for ax in axes:
                ax.scatter(x, y, s=3, alpha=.18, color='#186c9c', rasterized=True)
                ax.scatter([np.median(x)], [np.median(y)], marker='+', s=100, color='#b84432', label='Coordinate medians')
                ax.set_xlabel('Longitude (deg assumed)')
                ax.set_ylabel('Latitude (deg assumed)')
                ax.ticklabel_format(useOffset=False, style='plain')
                ax.grid(alpha=.2)
            axes[0].set_title(f'All valid coordinates ({len(coords):,} records)', loc='left', fontweight='bold')
            axes[0].legend(fontsize=8)
            bounds = [np.quantile(a, [.025, .975]) for a in (x, y)]
            for lim, setter in zip(bounds, (axes[1].set_xlim, axes[1].set_ylim)):
                pad = max(float(lim[1] - lim[0]) * .12, .000001)
                setter(lim[0] - pad, lim[1] + pad)
            axes[1].set_title('Display zoom: 2.5th-97.5th coordinate percentiles', loc='left', fontweight='bold')
            save(fig, '03_position', 'Reported GPS position scatter',
                 'The upper panel includes every coordinate in geographic bounds. The lower panel changes axis limits only. These are degree-coordinate plots, not metric maps; scatter is not proof of movement.')
        fig, axes = plt.subplots(4, 1, figsize=(8, 8.8), layout='constrained')
        for ax, key in zip(axes, ['eCompass North', 'Tilted Angle', 'Roll Angle', 'Pitch Angle']):
            plot(ax, series(sections, 'GPS', key), key, 'deg (assumed)')
        save(fig, '04_orientation', 'Compass and instrument orientation',
             'Angles are plotted exactly as logged. Degrees are assumed; compass reference (magnetic or true north) is unspecified. No compass calibration or unwrapping is applied.')
        fig, axes = plt.subplots(3, 1, figsize=(8, 8.0), layout='constrained')
        plot(axes[0], derived(sections, 'rtc_difference'), 'RTC timestamp minus record UTC', 'Seconds')
        plot(axes[1], series(sections, 'GPS', 'DAC Value'), 'Synchronization DAC', 'Logged DAC value')
        status = Counter(s.get('GPS Status') or '(missing)' for s in gps)
        axes[2].barh(list(status), list(status.values()), color='#186c9c')
        axes[2].set_title('GPS status record counts', loc='left', fontweight='bold')
        axes[2].set_xlabel('Records (not duration or duty cycle)')
        save(fig, '05_timing', 'Timing fields and GPS operating states',
             'RTC-minus-UTC is a comparison of timestamp fields, not a calibrated oscillator-error estimate. Status frequencies count records; they do not measure time spent in each state.')
    extras = sorted({(s.family, k) for s in sections if s.family not in KNOWN
                     for k, v in s.pairs if number(v) is not None})
    for offset in range(0, len(extras), 4):
        fig, axes = plt.subplots(4, 1, figsize=(8, 8.8), layout='constrained')
        for ax, (family, key) in zip(axes, extras[offset:offset + 4]):
            plot(ax, series(sections, family, key), f'{family}: {key}', 'Logged units')
        for ax in axes[len(extras[offset:offset + 4]):]:
            ax.set_visible(False)
        save(fig, f'extra_{offset // 4 + 1:02d}', 'Additional numeric observations',
             'Numeric scalar fields in unfamiliar section families are plotted without assigning physical meanings or units.')
    return figures


def make_pdf(dest: Path, source: Path, sections: list[Section], summary: dict, figures) -> None:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Image
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='SmallBody', fontName='Helvetica', fontSize=9, leading=13, spaceAfter=7))
    styles.add(ParagraphStyle(name='CellText', fontName='Helvetica', fontSize=8, leading=10))
    styles['Title'].textColor = colors.HexColor('#164b6a')
    styles['Heading1'].textColor = colors.HexColor('#164b6a')
    page_w, page_h = A4
    width = page_w - 84
    story = []

    def p(text, style='SmallBody'):
        # Log values are escaped before ReportLab's markup parser.
        return Paragraph(escape(str(text)), styles[style])

    def add(text, style='SmallBody'):
        story.append(p(text, style))

    def table(rows, widths=None):
        cells = [[p(v, 'CellText') for v in row] for row in rows]
        t = Table(cells, colWidths=widths, repeatRows=1, hAlign='LEFT')
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e4eef4')),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f5f7f9')]),
            ('LINEBELOW', (0, 0), (-1, 0), .6, colors.HexColor('#b6c9d5')),
            ('LEFTPADDING', (0, 0), (-1, -1), 6), ('RIGHTPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 5), ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ]))
        story.extend([t, Spacer(1, 10)])

    def fmt(v):
        return f'{v:,.4g}' if isinstance(v, (float, int)) else str(v)

    devices = [s for s in sections if s.family == 'DeviceInfo']
    device = devices[-1] if devices else None
    add('Logger summary', 'Title')
    add(source.name, 'Heading2')
    if device:
        add(f"Project: {device.get('Project Name') or 'unspecified'} | Serial: {device.get('Serial Number') or 'unspecified'}")
        add(f"Device: {device.get('Device Type') or 'unspecified'} | Firmware: {device.get('Firmware Version') or 'unspecified'}")
    add(f"File size: {summary['source_bytes']:,} bytes | Sections: {summary['section_count']:,} | Encoding: {summary['encoding']}")
    add(f"Timed-record UTC coverage: {summary['utc_start'] or 'not available'} to {summary['utc_end'] or 'not available'}")
    if summary['span_days'] is not None:
        add(f"Elapsed span: {summary['span_days']:.3f} days. Coverage describes logged observations and does not prove continuous waveform acquisition.")
    add('Section inventory', 'Heading2')
    table([['Family', 'Records', 'Contents']] + [[f, f'{n:,}', DESCRIPTIONS.get(f, 'Additional section family')]
          for f, n in summary['section_counts'].items()], [100, 55, width - 155])
    add('Observations to review', 'Heading2')
    errors = [e for e in summary['events'] if e['section'].casefold().startswith('error')]
    if errors:
        for e in errors:
            add(f"{e['utc'] or 'untimed'}: " + '; '.join(f'{k} = {v}' for k, v in e['pairs'] if norm(k) != 'utc time'))
    else:
        add('No Error sections found. This does not establish that the device had no faults.')
    for warning in summary['warnings']:
        add(warning)
    story.append(PageBreak())
    add('Measurement statistics and sampling', 'Heading1')
    add('Statistics use valid numeric values with valid record UTC times. First/last follow chronological order. Units are logged or explicitly assumed.')
    rows = [['Metric / unit', 'n', 'Min', 'Median', 'Max', 'First / last']]
    for label, m in summary['metrics'].items():
        if m['count']:
            rows.append([f"{label} ({m['unit']})", f"{m['count']:,}", fmt(m['min']), fmt(m['median']), fmt(m['max']), f"{fmt(m['first'])} / {fmt(m['last'])}"])
    table(rows, [160, 40, 49, 49, 49, width - 347])
    cadence_rows = [['Field', 'Median interval (min)', 'Largest gap (min)', 'Gaps > 3x median']]
    for label in ['Battery.Voltage', 'Temperature.Temperature', 'Memory.Used Memory', 'GPS.Satellite Number']:
        m = summary['metrics'][label]
        if 'median_interval_seconds' in m:
            cadence_rows.append([label, fmt(m['median_interval_seconds'] / 60), fmt(m['max_gap_seconds'] / 60), m['gaps_over_3x_median']])
    table(cadence_rows, [175, 110, 110, width - 395])
    add('Cadence is the median positive interval for the named metric. Gap flags indicate unusually spaced logger observations; they do not establish gaps in DLD waveform data.')
    mem = derived(sections, 'memory_percent')
    if mem:
        add(f'Last valid storage utilization: {mem[-1][1]:.2f}% of total. Absolute counter units are unspecified.')
    for title, figure, caption in figures:
        story.append(PageBreak())
        add(title, 'Heading1')
        add(caption)
        image = Image(str(figure))
        factor = min(width / image.imageWidth, 610 / image.imageHeight)
        image.drawWidth, image.drawHeight = image.imageWidth * factor, image.imageHeight * factor
        story.append(image)
    if devices:
        story.append(PageBreak())
        add('Boot configuration and channel checks', 'Heading1')
        add('Each boot is kept separate. Boot reason codes, gains and test units are preserved without vendor-specific interpretation.')
        keys = ['BootReason', 'Boot RTC', 'GPS Lock Time', 'Start Date', 'Sample Rate', 'Channel Number',
                'GPS Power Mode', 'Voltage Threshold', 'Geophone Test Passed', 'Sensor Type']
        table([['Field', *[s.name for s in devices]]] + [[k, *[s.get(k) or '-' for s in devices]] for k in keys],
              [145] + [(width - 145) / len(devices)] * len(devices))
        for s in devices:
            add(s.name, 'Heading2')
            rows = [['Channel', 'Resistance', 'Resonate Freq', 'Damping', 'Sensitivity', 'RMS Noise']]
            channels = sorted({int(m[1]) for k, _ in s.pairs if (m := re.match(r'Ch(\d+)\s', k, re.I))})
            for ch in channels:
                rows.append([str(ch), *[s.get(f'Ch{ch} {k}') or '-' for k in ['Resistance', 'Resonate Freq', 'Damping', 'Sensitivity', 'RMS Noise']]])
            if len(rows) > 1:
                table(rows, [45, 110, 88, 75, 85, width - 403])
        add('Complete device settings, including spread noise, SD identity and all raw pairs, are available in parsed_log.json and the DeviceInfo CSV.')
    story.append(PageBreak())
    add('Notifications and error log', 'Heading1')
    add('All selected events in source order. Untimed markers retain their section and source line. Acquisition filenames are references; this report does not read the DLD files.')
    rows = [['UTC / section / line', 'Details']]
    for e in summary['events']:
        details = '; '.join(f'{k} = {v}' for k, v in e['pairs'] if norm(k) != 'utc time') or '(empty marker)'
        rows.append([f"{e['utc'] or 'No UTC'} | {e['section']} | line {e['line']}", details])
    if len(rows) > 1:
        table(rows, [190, width - 190])
    else:
        add('No notification, error or power-stop sections found.')
    story.append(PageBreak())
    add('Interpretation and reuse', 'Heading1')
    for decision in summary['decisions']:
        add(decision)
    add('Reproduce this report', 'Heading2')
    add(f'python digisolo_report.py "{source.name}"')
    add('Use --format plots for PNG figures only, --parse-only for dependency-free JSON/CSV export, --output-dir to choose a destination, and --encoding for a known text encoding.')
    add('Use --voltage-threshold only for a threshold you explicitly choose. The raw Voltage Threshold field is not automatically scaled or interpreted.')
    add('For similarly structured logs, new section families and fields are retained. Timed scalar fields in unfamiliar families receive additional plots. Logs with a different grammar need a parser adapter.')
    add('Companion outputs: summary.json contains counts, statistics and warnings; parsed_log.json preserves key/value pairs and unparsed lines; csv/ contains one file per section family; events.csv contains event details; figures/ contains reusable PNG plots.')

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor('#d5dfe6'))
        canvas.line(42, 35, page_w - 42, 35)
        canvas.setFont('Helvetica', 8)
        canvas.setFillColor(colors.HexColor('#526575'))
        canvas.drawString(42, 23, 'Logger summary | record times in UTC')
        canvas.drawRightString(page_w - 42, 23, f'Page {doc.page}')
        canvas.restoreState()
    doc = SimpleDocTemplate(str(dest), pagesize=A4, rightMargin=42, leftMargin=42,
                            topMargin=38, bottomMargin=48, title=f'{source.name} logger summary', author='Logger report script')
    doc.build(story, onFirstPage=footer, onLaterPages=footer)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('log', nargs='?', type=Path, default=Path(__file__).resolve().parent / 'DigiSolo.LOG')
    ap.add_argument('--output-dir', type=Path, help='Default: LOG_PARENT/LOG_STEM_summary')
    ap.add_argument('--format', choices=['both', 'pdf', 'plots'], default='both', help='PDF modes also keep PNG figures for reuse')
    ap.add_argument('--parse-only', action='store_true', help='JSON/CSV only; no external packages required')
    ap.add_argument('--encoding', help='Override UTF-8/BOM detection and cp1252 fallback')
    ap.add_argument('--strict', action='store_true', help='Reject invalid record UTC times, duplicate keys and unparsed section lines')
    ap.add_argument('--voltage-threshold', type=float, help='Explicit voltage threshold; no auto-scaling of configuration values')
    args = ap.parse_args(argv)
    source = args.log.resolve()
    out = args.output_dir.resolve() if args.output_dir else source.parent / f'{source.stem}_summary'
    try:
        if args.voltage_threshold is not None and not math.isfinite(args.voltage_threshold):
            raise ValueError('Voltage threshold must be finite.')
        sections, meta = parse_log(source, args.encoding)
        if args.strict and any('duplicate keys' in w or 'non-key/value' in w or 'invalid UTC' in w for w in meta['warnings']):
            raise ValueError('Strict parsing failed: ' + '; '.join(meta['warnings']))
        summary = summarize(source, sections, meta)
        export_data(out, sections, summary)
        figures = [] if args.parse_only else make_figures(out, sections, args.voltage_threshold)
        if not args.parse_only and args.format != 'plots':
            make_pdf(out / f'{source.stem}_summary.pdf', source, sections, summary, figures)
        print(f"Parsed {len(sections):,} sections from {source.name}")
        print(json.dumps(summary['section_counts'], indent=2))
        print(f"UTC coverage: {summary['utc_start']} to {summary['utc_end']}")
        print(f'Outputs: {out}')
        for warning in summary['warnings']:
            print('REVIEW: ' + warning)
        return 0
    except ImportError as exc:
        print(f'Missing plotting/PDF dependency: {exc}. Run: python -m pip install matplotlib reportlab\nJSON/CSV may already be exported. --parse-only needs no external packages.', file=sys.stderr)
        return 2
    except (OSError, ValueError, LookupError) as exc:
        print(f'Error: {exc}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
