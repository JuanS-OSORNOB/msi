import obspy
filepath = "/mnt/c/SOLODATA/Roya/setup_2026-02-24/test_friday/453039008.0001.2026.02.20.10.16.08.000.Z.miniseed"
st = obspy.read(filepath)
tr = st[0]
fig = tr.plot()
fig.savefig("/mnt/c/Users/manip/Documents/trace_plot_Z.png")