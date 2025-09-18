#!/usr/bin/env python3
"""
EXIF Renamer - Automated File Naming Tool

This script processes image files and copies them to a new destination,
renaming them based on their EXIF/IPTC metadata.

Author: Edmond Shapiro
Version: 1.0.1
Created: 9 September 2025
Last Modified: 18 September 2025

Dependencies:
    - exiftool (external command-line tool)
    - Python 3.6+ with standard library modules

Usage:
    python exif-renamer.py --directory "2007 Print Quality" --destination "/path/to/destination"
    python exif-renamer.py --current --destination "/path/to/destination"

Version History:
    1.0.0 - Initial release
    1.0.1 - Add Report parameter
"""

__version__ = "1.0.1"
__author__ = "Edmond Shapiro"
__email__ = "eshapiro@gmail.com"
__license__ = "MIT"
__status__ = "Production"

import csv
import os
import re
import json
import argparse
import subprocess
import shutil
from pathlib import Path


# --- FIXED ROOT DIRECTORY ---
#ARCHIVE_ROOT = Path("/Volumes/photo/shapfam/")
ARCHIVE_ROOT = Path("/Users/edmonds/Pictures/")

# --- Define the destination folder for renamed files ---
DEFAULT_DESTINATION = Path("/Users/edmonds/Pictures/to-bb-2/")

# --- Checkpoint filename ---
CHECKPOINT_FILENAME = ".processed_marker"

def get_current_metadata_from_cli(file_path: Path):
    """
    Reads all metadata from a file and its sidecar using a direct subprocess call to exiftool,
    returning a Python dictionary.
    """
    try:
        xmp_file_path = file_path.with_suffix(".xmp")
        files_to_read = [str(file_path)]
        if xmp_file_path.exists():
            files_to_read.append(str(xmp_file_path))

        cmd = ["exiftool", "-j", "-m"] + files_to_read
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)

        metadata_list = json.loads(result.stdout)
        merged_metadata = {}
        for item in metadata_list:
            merged_metadata.update(item)
        return merged_metadata
    except (subprocess.CalledProcessError, json.JSONDecodeError) as e:
        print(f"Error reading metadata from {file_path}: {e}")
        return {}

def meets_renaming_criteria(metadata: dict):
    """
    Checks if a file's metadata meets the requirements for renaming.
    Criteria: must have a valid 'DateTimeOriginal', a non-empty 'Headline', and a non-empty 'Label'.
    """
    datetime_original = metadata.get('DateTimeOriginal')
    
    # Condition 1: Check for a valid DateTimeOriginal.
    date_is_valid = bool(re.match(r'(\d{4}):(\d{2}):(\d{2})', str(datetime_original)))

    # Condition 2: Check for non-empty Headline.
    headline = metadata.get('Headline')
    headline_is_valid = bool(headline and isinstance(headline, str) and headline.strip())
    
    # Condition 3: Check for non-empty Label.
    label = metadata.get('Label')
    label_is_valid = bool(label and isinstance(label, str) and label.strip())
    
    # Combined condition: all checks must pass.
    if date_is_valid and headline_is_valid and label_is_valid:
        return True

    return False

def generate_new_filename(metadata: dict, original_path: Path):
    """
    Generates the new filename based on the specified metadata format.
    Format: [Date]_[Headline]_[File Name]
    """
    datetime_original = metadata.get('DateTimeOriginal', 'unknown_date')
    headline = metadata.get('Headline', 'no_headline')
    original_filename_stem = original_path.stem
    file_suffix = original_path.suffix

    # Sanitize the headline for use in a filename
    sanitized_headline = re.sub(r'[\\/:*?"<>|]', '', headline).replace(' ', '_')

    # Exiftool provides DateTimeOriginal in the format 'YYYY:MM:DD HH:MM:SS'
    # We want to extract only the 'YYYYMMDD' portion for the filename
    match = re.search(r'(\d{4}:\d{2}:\d{2})', datetime_original)
    if match:
        date_only = match.group(1)
        # Remove colons to get 'YYYYMMDD'
        formatted_date = re.sub(r'[:]', '', date_only)
    else:
        # Fallback if the date format is unexpected
        formatted_date = 'unknown_date'

    new_filename = f"{formatted_date}_{sanitized_headline}_{original_filename_stem}{file_suffix}"
    return new_filename

def copy_and_rename_file(source_path: Path, destination_root: Path, new_filename: str):
    """
    Copies a file from the source path to the destination root with the new filename.
    """
    destination_path = destination_root / new_filename

    # Create the destination directory if it doesn't exist
    destination_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        shutil.copy2(source_path, destination_path)
        print(f"Copied and renamed: '{source_path.name}' -> '{destination_path.name}'")
    except shutil.SameFileError:
        print(f"Skipping: Source and destination are the same file: '{source_path}'")
    except Exception as e:
        print(f"Error copying file '{source_path}': {e}")

def traverse_and_rename(archive_dir, destination_dir, debug: bool = False, report_filename=None):
    """Walk through archive and rename/copy files as needed."""
    report_rows = []
    for root, dirs, files in os.walk(archive_dir):
        root_path = Path(root)
        try:
            relative_path = root_path.relative_to(archive_dir)
        except ValueError:
            relative_path = Path(".") # Handles case where archive_dir is the current directory.

        # Check for checkpoint file before processing
        if is_directory_completed(relative_path, archive_dir):
            if debug:
                print(f"[SKIP] Already processed: {relative_path}")
            dirs[:] = []  # Prevents descending further into this directory
            continue
        
        # New: Skip "received" directories
        if "received" in str(relative_path).lower():
            print(f"Skipping subdirectory '{root}' due to 'received' keyword.")
            dirs[:] = []
            continue

        for file in files:
            # Check for common image/video file extensions.
            if file.lower().endswith((
                ".nef", ".cr3", ".psd", ".jpg", ".jpeg", ".png", ".tif", ".tiff",
                ".heic", ".heif", ".dng", ".avif", ".mov", ".mp4"
            )):
                file_path = root_path / file
                
                # Get the metadata for the current file.
                metadata = get_current_metadata_from_cli(file_path)
                
                # Check if the file meets the criteria for renaming.
                if meets_renaming_criteria(metadata):
                    # Generate the new filename.
                    new_filename = generate_new_filename(metadata, file_path)
                    
                    if debug:
                        print(f"[DEBUG] Would rename '{file_path.name}' to '{new_filename}'")
                    if report:
                        # Populate report row:
                        report_rows.append([
                            file_path.name,
                            str(file_path),
                            new_filename,
                            str(destination_dir / new_filename)
                        ])
                    else:
                        # Copy and rename the main file.
                        copy_and_rename_file(file_path, destination_dir, new_filename)

                        # Check for and copy the XMP sidecar file
                        xmp_path = file_path.with_suffix('.xmp')
                        if xmp_path.exists():
                            new_xmp_filename = Path(new_filename).with_suffix('.xmp')
                            copy_and_rename_file(xmp_path, destination_dir, new_xmp_filename)

                elif debug:
                    print(f"[DEBUG] Skipping '{file_path.name}' - does not meet renaming criteria.")

        # Mark directory as completed after all files in it are processed
        if relative_path != Path("."):
            mark_directory_completed(relative_path, archive_dir)

    # After traversing, if report is enabled write CSV file
    if report_filename and report_rows:
        csv_path = destination_dir / report_filename
        with open(csv_path, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(["Current Filename", "Current Full Path", "Expected New Filename", "Future Full Path"])
            writer.writerows(report_rows)
        print(f"[INFO] Report written to {csv_path}")


def is_directory_completed(relative_path: Path, root: Path) -> bool:
    """
    Returns True if the checkpoint file exists in the directory.
    """
    marker_path = root / relative_path / CHECKPOINT_FILENAME
    return marker_path.exists()

def mark_directory_completed(relative_path: Path, root: Path):
    """
    Creates a marker file in the given directory to indicate processing is done.
    """
    marker_path = root / relative_path / CHECKPOINT_FILENAME
    with open(marker_path, "w") as f:
        f.write("processed\n")
    print(f"[INFO] Marked completed: {relative_path}")

def cleanup_checkpoints(root_directory: Path):
    """
    Recursively deletes all checkpoint files under the given root directory.
    """
    removed = 0
    for marker_path in root_directory.rglob(CHECKPOINT_FILENAME):
        try:
            marker_path.unlink()
            removed += 1
        except FileNotFoundError:
            continue
    print(f"[INFO] Removed {removed} checkpoint files under {root_directory}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Rename image files based on their metadata.",
        epilog=f"EXIF Renamer v{__version__} - Automated File Naming Tool"
    )

    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}"
    )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--directory",
        help="Subdirectory under /Volumes/photo/shapfam/ to process (e.g., '2007 Print Quality')."
    )
    group.add_argument(
        "--current",
        action="store_true",
        help="Use the current working directory as the root."
    )

    # Add report argument to parser:
    parser.add_argument(
        "--report",
        action="store_true",
        help="Generate CSV report of files to be renamed instead of copying them."
    )


    # The destination is no longer a required parameter.
    parser.add_argument(
        "--destination",
        help="The destination directory for the renamed files. Defaults to DEFAULT_DESTINATION if not provided."
    )

    parser.add_argument("--debug", action="store_true", help="Enable debug mode (print changes, don't write).")
    args = parser.parse_args()

    if args.current:
        target_dir = Path.cwd()
    else:
        target_dir = ARCHIVE_ROOT / args.directory

    if not target_dir.exists():
        print(f"Error: Source directory '{target_dir}' does not exist.")
        exit(1)

    # --- New Logic: Determine the final destination directory ---
    # First, determine the base destination root.
    if args.destination:
        # If a destination is provided, use it.
        destination_root = Path(args.destination)
    else:
        # Otherwise, use the predefined default.
        destination_root = DEFAULT_DESTINATION

    # Second, check if a subdirectory name needs to be appended.
    if args.directory:
        directory_name = Path(args.directory).name
        # Append the directory name to the destination root.
        destination_dir = destination_root / directory_name
    else:
        # If no --directory is specified, use the destination root as the final destination.
        destination_dir = destination_root
    
    report_filename = None    
    if args.report:
        base_name = args.directory if args.directory else "rename_report"
        report_filename = f"{base_name}_report.csv"
        
    # Ensure the final destination directory exists.
    destination_dir.mkdir(parents=True, exist_ok=True)
    
    # --- End New Logic ---

    print(f"Processing directory: {target_dir}")
    print(f"Destination directory: {destination_dir}")

    traverse_and_rename(target_dir, destination_dir, debug=args.debug, report_filename=report_filename)

    cleanup_checkpoints(target_dir)