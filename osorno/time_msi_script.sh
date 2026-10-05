#!/bin/bash


#author: Juan Osorno
#date: 2026-10-05
#description: Run miniSEED Inspector (msi -T) for each listed identifier using
# matching files from a conversion directory.
#Measure CPU time, elapsed time, memory usage, and I/O with /usr/bin/time -v.
# Save trace listings to /osorno/program_output_<id>.log and timing reports
# plus any MSI diagnostics to /osorno/runtime_<id>.log.
# Run from the MSI repository root; /osorno must exist and be writable.
#modified: 2026-10-05

#Steps to run it: Always from the root of the repository.
# chmod +x time_msi_script.sh
# ./osorno/time_msi_script.sh

ids=(453039071 453039006 453038958 453038978 453038983 453038956 453039009 453039118 453040077 453039011 453039005 453038979 453038969 453039078)

for id in "${ids[@]}"; do
    echo "Running MSI for $id..."
    mkdir -p "./osorno/SPZ/2026/DEPLOYMENT_01/${id}" || exit 1

    /usr/bin/time -v \
      ./msi -T \
      /mnt/e/SOLODATA/SPZ/2026/DEPLOYMENT_01/${id}* \
      > "./osorno/SPZ/2026/DEPLOYMENT_01/${id}/program_output.log" \
      2> "./osorno/SPZ/2026/DEPLOYMENT_01/${id}/program_runtime.log"

    echo "Finished $id"
done
