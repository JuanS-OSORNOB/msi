#!/bin/bash


#author: Juan Osorno
#date: 2026-10-05
#description: Run miniSEED Inspector (msi -T) for each listed identifier using
# matching files from a conversion directory.
#Measure CPU time, elapsed time, memory usage, and I/O with /usr/bin/time -v.
# Save trace listings to /osorno/program_output_<id>.log and timing reports
# plus any MSI diagnostics to /osorno/runtime_<id>.log.
# Run from the MSI repository root; /osorno must exist and be writable.
# [ENZ] matches one character—E, N, or Z—so it excludes .ENZ.miniseed.
#modified: 2026-10-05

#Steps to run it: Always from the root of the repository.
# chmod +x osorno/time_msi_script.sh
# ./osorno/time_msi_script.sh

ids=(453039026 453039127 453039016 453039089 453039132 453039024 453039000 453039048 453038994 453038955 453039012 453038995 453039083 453039133)

batch_start_seconds=$SECONDS
counter=0
echo "Starting MSI batch for ${#ids[@]} identifiers..."

for id in "${ids[@]}"; do
    counter=$((counter + 1))
    echo
    echo "[$counter/${#ids[@]}] Running MSI for $id..."
    mkdir -p "./osorno/SPZ/2025/DEPLOYMENT_02/${id}" || exit 1

    /usr/bin/time -v \
      ./msi -T \
      /mnt/e/SOLODATA/SPZ/2025/DEPLOYMENT_02/${id}*.[ENZ].miniseed \
      > "./osorno/SPZ/2025/DEPLOYMENT_02/${id}/program_output.log" \
      2> "./osorno/SPZ/2025/DEPLOYMENT_02/${id}/program_runtime.log"

    echo "[$counter/${#ids[@]}] Finished $id"
done

batch_elapsed_seconds=$((SECONDS - batch_start_seconds))
printf 'Total batch runtime: %02d:%02d:%02d (hours:minutes:seconds; %d seconds)\n' \
    "$((batch_elapsed_seconds / 3600))" \
    "$((batch_elapsed_seconds % 3600 / 60))" \
    "$((batch_elapsed_seconds % 60))" \
    "$batch_elapsed_seconds"