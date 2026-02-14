# Photo & Video Metadata Updater

This script updates and corrects the **EXIF metadata** and file timestamps for photos and videos, particularly for content exported from **Google Takeout**. It ensures that apps like **Ugreen** or photo managers display files in the correct timeline.

## Features

* Recursively scans all **non-JSON files** in a specified folder.
* Automatically finds the corresponding **Google Takeout JSON metadata** if available.
* Determines the correct file date using the following priority:

  1. **Google JSON metadata (`photoTakenTime`)**
  2. **Date/time in the filename** (e.g., `20230126_203929.MP4`)
  3. **Folder year** (e.g., `Photos from 2023`) as a fallback
* Updates **EXIF metadata fields**: `DateTimeOriginal`, `CreateDate`, `ModifyDate`.
* Optionally updates **filesystem timestamp (`FileModifyDate`)** to match the EXIF date.
* Adds **GPS coordinates** and **description** from JSON if available.
* Handles special cases:

  * Automatically renames **HEIC/JPEG misidentified files** to `.jpg`.
  * Ignores minor errors in videos (`MP4`, `MOV`) with `-ignoreMinorErrors`.
  * Skips certain corrupted JPEG errors but logs them.
* Validates that the EXIF date matches the intended date.
* Provides **real-time logging** for each file:

  * `[UPDATED]` → metadata successfully updated
  * `[SKIPPED]` → could not determine date or skipped due to minor errors
  * `[FAILED]` → failed to update or validation mismatch
* Shows **progress percentage** and prints a **summary** at the end.

## Usage

1. Export your Google Photos from https://takeout.google.com/
2. Install **ExifTool** via [Homebrew](https://brew.sh/) (required to run the script):

```bash
brew install exiftool
```

2. Run the script:

```bash
python3 update_takeout_metadata.py
```

3. Enter the path to your Google Takeout folder when prompted.
