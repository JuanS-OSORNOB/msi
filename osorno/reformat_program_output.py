"""
@author: Juan Osorno
@date: 2026-09-23
@description: Python script to reformat the output of a program into a semicolon-separated values (CSV) format.
The script reads a log file, skips blank lines and the "Total:" summary footer, and writes the remaining data to a new file with a "_formatted" suffix.
The header is added manually, and each line of data is split on whitespace and joined with semicolons for proper CSV formatting.
@modified: 2026-10-05
"""
import re, os

def reformat_file(input_file = "yourfile.log"):
    output_file = os.path.splitext(input_file)[0] + "_formatted.csv"
    with open(input_file, "r", encoding="utf-8") as f:
        lines = f.readlines()

    with open(output_file, "w", encoding="utf-8") as f:
        # Write the header manually
        f.write("SourceID;Start_sample;End_sample;Hz;Samples\n")

        # Process the data lines
        for line in lines[1:]:
            line = line.strip()

            # Skip the summary by content, regardless of trailing newlines.
            if not line or line.startswith("Total:"):
                continue

            # Split on whitespace
            columns = re.split(r"\s+", line)

            # Write as semicolon-separated values
            f.write(";".join(columns) + "\n")


input_files = ["/home/manip/GitHub/msi/osorno/453039071/program_output.log",
               "/home/manip/GitHub/msi/osorno/453039006/program_output.log",
               "/home/manip/GitHub/msi/osorno/453038958/program_output.log",
               "/home/manip/GitHub/msi/osorno/453038978/program_output.log",
               "/home/manip/GitHub/msi/osorno/453038983/program_output.log",
               "/home/manip/GitHub/msi/osorno/453038956/program_output.log",
               "/home/manip/GitHub/msi/osorno/453039009/program_output.log",
               "/home/manip/GitHub/msi/osorno/453039118/program_output.log",
               "/home/manip/GitHub/msi/osorno/453040077/program_output.log",
               "/home/manip/GitHub/msi/osorno/453039011/program_output.log",
               "/home/manip/GitHub/msi/osorno/453039005/program_output.log",
               "/home/manip/GitHub/msi/osorno/453038979/program_output.log",
               "/home/manip/GitHub/msi/osorno/453038969/program_output.log",
               "/home/manip/GitHub/msi/osorno/453039078/program_output.log"]
for file in input_files:
    reformat_file(file)