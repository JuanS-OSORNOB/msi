"""
@author: Juan Osorno
@date: 2026-09-23
@description: Summarize miniSEED trace output by reading multiple formatted station logs,
    grouping records by channel, detecting continuous segments and gaps, and
    exporting a compact per-channel summary CSV and a detailed gaps CSV.
@modified: 2026-10-05

"""
import pandas as pd
from pathlib import Path

def format_duration(td):
    total_seconds = int(td.total_seconds())
    days = total_seconds // 86400
    hours = (total_seconds % 86400) // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    return f"{days} days, {hours:02}:{minutes:02}:{seconds:02}"

def summarize_file(input_file):
    """Print coverage and save summary and gaps CSVs beside one input file."""
    #region Parse formatted
    input_path = Path(input_file)
    output_dir = input_path.parent
    print(f'\nProcessing: {input_path}')
    df = pd.read_csv(
        input_path,
        sep=';',
        skiprows=1,
        names=['SourceID', 'Start_sample', 'End_sample', 'Hz', 'Samples']
    )

    if df.empty:
        raise ValueError(f'No trace rows found in {input_path}')

    # Clean/Parse timestamps
    df['Start_sample'] = pd.to_datetime(df['Start_sample'])
    df['End_sample'] = pd.to_datetime(df['End_sample'])

    # Extract channel (e.g., E, N, Z) from the end of SourceID
    df['Channel'] = df['SourceID'].apply(lambda x: x.split('_')[-1])

    # Extract the ID
    df['ID'] = df['SourceID'].str.split('_').str[1].str[-4:]
    print(df['ID'])

    # Sort everything chronologically
    df = df.sort_values(
        ['Channel', 'Start_sample']
    ).reset_index(drop=True)
    #endregion Parse formatted

    #region Segments and gaps
    # ----------------------------------------------------------------------
    # Find continuous segments and gaps
    # ----------------------------------------------------------------------
    segments = []
    gaps = []
    # Process each channel separately
    for channel, group in df.groupby('Channel'):

        group = group.sort_values('Start_sample').reset_index(drop=True)

        # Start first continuous segment
        segment_start = group.loc[0, 'Start_sample']
        segment_end = group.loc[0, 'End_sample']

        segment_samples = group.loc[0, 'Samples']

        segment_num = 1
        gap_num = 1

        for i in range(1, len(group)):

            previous_end = group.loc[i - 1, 'End_sample']
            current_start = group.loc[i, 'Start_sample']

            current_end = group.loc[i, 'End_sample']
            current_samples = group.loc[i, 'Samples']

            # --------------------------------------------------------------
            # Continuous
            # --------------------------------------------------------------

            if current_start <= previous_end:

                # Extend current segment
                segment_end = max(segment_end, current_end)

                segment_samples += current_samples

            # --------------------------------------------------------------
            # Gap
            # --------------------------------------------------------------

            else:

                # Save the continuous segment that just ended
                duration = segment_end - segment_start

                segments.append({
                    'Channel': channel,
                    'Segment': segment_num,
                    'Start': segment_start,
                    'End': segment_end,
                    'Duration': format_duration(duration),
                    'Duration_seconds': duration.total_seconds(),
                    'Samples': segment_samples
                })

                # Save the gap
                gap_duration = current_start - previous_end

                gaps.append({
                    'Channel': channel,
                    'Gap': gap_num,
                    'Start': previous_end,
                    'End': current_start,
                    'Duration': format_duration(gap_duration),
                    'Duration_seconds': gap_duration.total_seconds()
                })

                # Start a new continuous segment
                segment_num += 1
                gap_num += 1

                segment_start = current_start
                segment_end = current_end
                segment_samples = current_samples

        # ------------------------------------------------------------------
        # Save final segment
        # ------------------------------------------------------------------

        duration = segment_end - segment_start

        segments.append({
            'Channel': channel,
            'Segment': segment_num,
            'Start': segment_start,
            'End': segment_end,
            'Duration': format_duration(duration),
            'Duration_seconds': duration.total_seconds(),
            'Samples': segment_samples
        })

    #endregion Segments and gaps


    # ----------------------------------------------------------------------
    # Create summary DataFrames
    # ----------------------------------------------------------------------

    segments_df = pd.DataFrame(segments)
    gaps_df = pd.DataFrame(gaps, columns=[
        'Channel', 'Gap', 'Start', 'End', 'Duration', 'Duration_seconds'
    ])

    #region Summary Segments
    # ----------------------------------------------------------------------
    # Print continuous-segment summary
    # ----------------------------------------------------------------------

    print()
    print("=" * 100)
    print("CONTINUOUS DATA SEGMENTS")
    print("=" * 100)

    print(
        segments_df[
            [
                'Channel',
                'Segment',
                'Start',
                'End',
                'Duration',
                'Samples'
            ]
        ].to_string(index=False)
    )
    #endregion Summary Segments

    #region Summary Gaps
    # ----------------------------------------------------------------------
    # Print gap summary
    # ----------------------------------------------------------------------

    print()
    print("=" * 100)
    print("GAPS")
    print("=" * 100)

    if gaps_df.empty:

        print("No gaps found.")

    else:

        print(
            gaps_df[
                [
                    'Channel',
                    'Gap',
                    'Start',
                    'End',
                    'Duration'
                ]
            ].to_string(index=False)
        )
    # Save detailed gaps alongside the channel summary, including headers when no gaps were found.
    gaps_filename = output_dir / 'gaps_msi.csv'
    gaps_df.to_csv(
        gaps_filename,
        index=False,
        date_format="%Y-%m-%dT%H:%M:%S.%f%z"
    )
    #endregion Summary Gaps

    #region Summary Channels
    # ======================================================================
    # Compact channel summary
    # ======================================================================

    summary = []

    for channel, group in df.groupby('Channel'):

        group = group.sort_values('Start_sample').reset_index(drop=True)

        first_start = group['Start_sample'].min()
        last_end = group['End_sample'].max()

        # Total time covered by the complete time range
        total_time_range = last_end - first_start

        # Calculate gaps
        total_gap = pd.Timedelta(0)
        number_of_gaps = 0

        for i in range(1, len(group)):

            previous_end = group.loc[i - 1, 'End_sample']
            current_start = group.loc[i, 'Start_sample']

            if current_start > previous_end:

                gap = current_start - previous_end

                total_gap += gap
                number_of_gaps += 1

        # Actual data duration = total time range - gaps
        total_data = total_time_range - total_gap

        summary.append({
            'ID': df['ID'][0],
            'Channel': channel,
            'First_Start': first_start,
            'Last_End': last_end,
            'Total_Data': format_duration(total_data),
            'Number_of_Gaps': number_of_gaps,
            'Total_Gap_Time': format_duration(total_gap)
        })


    summary_df = pd.DataFrame(summary)

    # Print compact summary
    print()
    print("=" * 100)
    print("CHANNEL SUMMARY")
    print("=" * 100)

    print(
        summary_df.to_string(index=False)
    )

    # Save summary
    filename = output_dir / 'summarize_msi.csv'
    Path(filename).parent.mkdir(parents=True, exist_ok=True)
    summary_df.to_csv(
        filename,
        index=False,
        date_format="%Y-%m-%dT%H:%M:%S.%f"
    )

    print("\nSummary written to:")
    print(f"  {filename}")
    print("Gaps written to:")
    print(f"  {gaps_filename}")
    #endregion Summary Channels

    return summary_df, gaps_df


# Use the same identifiers as time_msi_script.sh and reformat_program_output.py.
# Change BASEPATH to process another deployment.
BASEPATH = Path(__file__).resolve().parent / 'SPZ' / '2025' / 'DEPLOYMENT_02'
ids = [
    '453039026',
    '453039127',
    '453039016',
    '453039089',
    '453039132',
    '453039024',
    '453039000',
    '453039048',
    '453038994',
    '453038955',
    '453039012',
    '453038995',
    '453039083',
    '453039133'
    ]
input_files = [BASEPATH / identifier / 'program_output_formatted.csv' for identifier in ids]

def main():
    """Process each configured file, reporting invalid inputs and continuing."""
    for input_file in input_files:
        try:
            summarize_file(input_file)
        except (FileNotFoundError, pd.errors.EmptyDataError, ValueError) as error:
            print(f'Skipping {input_file}: {error}')
    print("\nAll files processed.")


if __name__ == '__main__':
    main()
