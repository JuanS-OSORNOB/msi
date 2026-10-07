import matplotlib
matplotlib.use("Agg")  # Set before importing ObsPy.

import obspy
from pathlib import Path

filepath = Path(
    "/mnt/e/SOLODATA/SPZ/2026/DEPLOYMENT_01/"
    "453038969.0015.2026.07.16.00.00.00.000.ENZ.miniseed"
)

if filepath.stat().st_size == 0:
    raise ValueError(f"Empty file: {filepath}")

st = obspy.read(str(filepath), format="MSEED")
print(st)

output = Path(__file__).resolve().parent / "trace_plot_ENZ.png"
fig = st[0].plot(show=False)
fig.savefig(output)
print(f"Plot saved to: {output}")