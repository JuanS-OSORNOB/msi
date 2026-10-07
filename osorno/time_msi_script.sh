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

ids=(453039046 453039124 453039008 453039107 453038975 453039121 453039094 453039042 453039062 453039018 453039109 453039045 453039069 453039122 453038998 453039022 453039041 453039129 453039086 453038986 453039097 453039113 453039073 453039150 453039037 453039141 453039065)

batch_start_seconds=$SECONDS
counter=0
echo "Starting MSI batch for ${#ids[@]} identifiers..."

for id in "${ids[@]}"; do
    counter=$((counter + 1))
    echo "[$counter/${#ids[@]}] Running MSI for $id..."
    mkdir -p "./osorno/OESCHIBACH/2026/DEPLOYMENT_01/${id}" || exit 1

    /usr/bin/time -v \
      ./msi -T \
      /mnt/e/SOLODATA/OESCHIBACH/2026/DEPLOYMENT_01/${id}*.[ENZ].miniseed \
      > "./osorno/OESCHIBACH/2026/DEPLOYMENT_01/${id}/program_output.log" \
      2> "./osorno/OESCHIBACH/2026/DEPLOYMENT_01/${id}/program_runtime.log"

    echo "[$counter/${#ids[@]}] Finished $id"
done

batch_elapsed_seconds=$((SECONDS - batch_start_seconds))
printf 'Total batch runtime: %02d:%02d:%02d (hours:minutes:seconds; %d seconds)\n' \
    "$((batch_elapsed_seconds / 3600))" \
    "$((batch_elapsed_seconds % 3600 / 60))" \
    "$((batch_elapsed_seconds % 60))" \
    "$batch_elapsed_seconds"