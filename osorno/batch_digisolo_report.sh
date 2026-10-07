#!/usr/bin/env bash

shopt -s nullglob
echo "Started at $(date '+%H:%M:%S')"

for logfile in /mnt/e/DCCDATA/OESCHIBACH/2026/*/*/DigiSolo.log; do
    timestamp_dir=$(dirname "$logfile")
    identifier=$(basename "$(dirname "$timestamp_dir")")
    
    echo
    echo "Processing $identifier: $logfile"

    python osorno/digisolo_report.py "$logfile" \
        --output-dir "/home/manip/GitHub/msi/osorno/OESCHIBACH/2026/DEPLOYMENT_01/$identifier/DigiSolo_summary"
done
echo
echo "Finished at $(date '+%H:%M:%S')"
echo "Elapsed: ${SECONDS}s"