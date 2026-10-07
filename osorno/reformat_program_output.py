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

input_files = ["/home/manip/GitHub/msi/osorno/OESCHIBACH/2026/DEPLOYMENT_01/453039046/program_output.log",
               "/home/manip/GitHub/msi/osorno/OESCHIBACH/2026/DEPLOYMENT_01/453039124/program_output.log",
               "/home/manip/GitHub/msi/osorno/OESCHIBACH/2026/DEPLOYMENT_01/453039008/program_output.log",
               "/home/manip/GitHub/msi/osorno/OESCHIBACH/2026/DEPLOYMENT_01/453039107/program_output.log",
               "/home/manip/GitHub/msi/osorno/OESCHIBACH/2026/DEPLOYMENT_01/453038975/program_output.log",
               "/home/manip/GitHub/msi/osorno/OESCHIBACH/2026/DEPLOYMENT_01/453039121/program_output.log",
               "/home/manip/GitHub/msi/osorno/OESCHIBACH/2026/DEPLOYMENT_01/453039094/program_output.log",
               "/home/manip/GitHub/msi/osorno/OESCHIBACH/2026/DEPLOYMENT_01/453039042/program_output.log",
               "/home/manip/GitHub/msi/osorno/OESCHIBACH/2026/DEPLOYMENT_01/453039062/program_output.log",
               "/home/manip/GitHub/msi/osorno/OESCHIBACH/2026/DEPLOYMENT_01/453039018/program_output.log",
               "/home/manip/GitHub/msi/osorno/OESCHIBACH/2026/DEPLOYMENT_01/453039109/program_output.log",
               "/home/manip/GitHub/msi/osorno/OESCHIBACH/2026/DEPLOYMENT_01/453039045/program_output.log",
               "/home/manip/GitHub/msi/osorno/OESCHIBACH/2026/DEPLOYMENT_01/453039069/program_output.log",
               "/home/manip/GitHub/msi/osorno/OESCHIBACH/2026/DEPLOYMENT_01/453039122/program_output.log",
               "/home/manip/GitHub/msi/osorno/OESCHIBACH/2026/DEPLOYMENT_01/453038998/program_output.log",
               "/home/manip/GitHub/msi/osorno/OESCHIBACH/2026/DEPLOYMENT_01/453039022/program_output.log",
               "/home/manip/GitHub/msi/osorno/OESCHIBACH/2026/DEPLOYMENT_01/453039041/program_output.log",
               "/home/manip/GitHub/msi/osorno/OESCHIBACH/2026/DEPLOYMENT_01/453039129/program_output.log",
               "/home/manip/GitHub/msi/osorno/OESCHIBACH/2026/DEPLOYMENT_01/453039086/program_output.log",
               "/home/manip/GitHub/msi/osorno/OESCHIBACH/2026/DEPLOYMENT_01/453038986/program_output.log",
               "/home/manip/GitHub/msi/osorno/OESCHIBACH/2026/DEPLOYMENT_01/453039097/program_output.log",
               "/home/manip/GitHub/msi/osorno/OESCHIBACH/2026/DEPLOYMENT_01/453039113/program_output.log",
               "/home/manip/GitHub/msi/osorno/OESCHIBACH/2026/DEPLOYMENT_01/453039073/program_output.log",
               "/home/manip/GitHub/msi/osorno/OESCHIBACH/2026/DEPLOYMENT_01/453039150/program_output.log",
               "/home/manip/GitHub/msi/osorno/OESCHIBACH/2026/DEPLOYMENT_01/453039037/program_output.log",
               "/home/manip/GitHub/msi/osorno/OESCHIBACH/2026/DEPLOYMENT_01/453039141/program_output.log",
               "/home/manip/GitHub/msi/osorno/OESCHIBACH/2026/DEPLOYMENT_01/453039065/program_output.log"
               ]
for file in input_files:
    reformat_file(file)
print("Reformatting completed for all files.")