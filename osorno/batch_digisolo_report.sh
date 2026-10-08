#!/usr/bin/env bash

shopt -s nullglob
echo "Started at $(date '+%H:%M:%S')"

logfiles=(/mnt/e/DCCDATA/SPZ/2025/DEPLOYMENT_02/*/*/DigiSolo.log)
total=${#logfiles[@]}
counter=0

for logfile in  "${logfiles[@]}"; do
    counter=$((counter + 1))
    timestamp_dir=$(dirname "$logfile")
    identifier=$(basename "$(dirname "$timestamp_dir")")
    
    echo
    echo "[$counter / $total] Processing $identifier: $logfile"
    output_dir="/home/manip/GitHub/msi/osorno/SPZ/2025/DEPLOYMENT_02/$identifier/DigiSolo_summary"
    mkdir -p "$output_dir" || exit 1

    python osorno/digisolo_report.py "$logfile" \
        --output-dir "$output_dir"
    echo "Finished $identifier"
done
echo
echo "Finished at $(date '+%H:%M:%S')"
elapsed=$SECONDS
printf 'Elapsed: %02d:%02d:%02d\n' \
    "$((elapsed / 3600))" \
    "$(((elapsed % 3600) / 60))" \
    "$((elapsed % 60))"