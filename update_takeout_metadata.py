#!/usr/bin/env python3
import os
import json
import subprocess
from pathlib import Path
import re
import datetime
import shutil

# If True, the script will also update the file's last modified timestamp
# to match the EXIF DateTimeOriginal. Set to False if you want to preserve
# the original file modification time.
UPDATE_FILE_TIMESTAMP = True

MONTHS = {
    "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4,
    "May": 5, "Jun": 6, "Jul": 7, "Aug": 8,
    "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12
}


def parse_google_formatted(date_str):
    try:
        parts = date_str.strip().split()
        if len(parts) < 4:
            return None
        day = int(parts[0])
        month = MONTHS.get(parts[1], 0)
        year = int(parts[2])
        hour, minute, second = map(int, parts[3].split(":"))
        dt = datetime.datetime(year, month, day, hour, minute, second)
        return dt.strftime("%Y:%m:%d %H:%M:%S")
    except Exception:
        return None


def extract_date_from_folder(file_path):
    folder_name = file_path.parent.name
    match = re.search(r"(19|20)\d{2}", folder_name)
    if match:
        return f"{match.group(0)}:01:01 12:00:00"
    return None


def extract_date_from_filename(file_path):
    """
    Looks for patterns like 20230126_203929 in the filename.
    Returns EXIF-formatted date if found.
    """
    match = re.search(r"(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})", file_path.stem)
    if match:
        year, month, day, hour, minute, second = map(int, match.groups())
        return f"{year:04d}:{month:02d}:{day:02d} {hour:02d}:{minute:02d}:{second:02d}"
    return None


def resolve_date(json_data, file_path):
    # 1️⃣ Google JSON metadata first
    if json_data and "photoTakenTime" in json_data:
        pt = json_data["photoTakenTime"]
        if "formatted" in pt and pt["formatted"]:
            exif_date = parse_google_formatted(pt["formatted"])
            if exif_date:
                return exif_date
        if "timestamp" in pt and pt["timestamp"]:
            dt = datetime.datetime.utcfromtimestamp(int(pt["timestamp"]))
            return dt.strftime("%Y:%m:%d %H:%M:%S")

    # 2️⃣ Filename date/time second
    date_from_filename = extract_date_from_filename(file_path)
    if date_from_filename:
        return date_from_filename

    # 3️⃣ Folder fallback
    return extract_date_from_folder(file_path)


def find_matching_json(file_path):
    """
    Finds any JSON file in the same folder that starts with the file name.
    Returns the first match.
    """
    base_name = file_path.name.strip().lower()
    for f in file_path.parent.glob("*.json"):
        if f.name.lower().startswith(base_name):
            return f
    return None


def update_exif(file_path, json_data):
    date_str = resolve_date(json_data, file_path)
    if not date_str:
        return "SKIPPED", None, "No date available"

    cmd = [
        "exiftool",
        "-overwrite_original",
        "-ignoreMinorErrors",
        f"-DateTimeOriginal={date_str}",
        f"-CreateDate={date_str}",
        f"-ModifyDate={date_str}"
    ]

    if UPDATE_FILE_TIMESTAMP:
        cmd.append(f"-FileModifyDate={date_str}")

    if json_data:
        geo = json_data.get("geoDataExif") or json_data.get("geoData")
        if geo:
            lat = geo.get("latitude")
            lon = geo.get("longitude")
            if lat and lon:
                cmd.append(f"-GPSLatitude={lat}")
                cmd.append(f"-GPSLongitude={lon}")

        if "description" in json_data and json_data["description"]:
            cmd.append(f"-ImageDescription={json_data['description']}")

    cmd.append(str(file_path))
    result = subprocess.run(cmd, capture_output=True, text=True)
    stderr = result.stderr.strip()

    # Handle HEIC/JPEG misidentified
    if "Not a valid HEIC" in stderr or "Not a valid JPEG" in stderr:
        new_file = file_path.with_suffix(".jpg")
        shutil.move(file_path, new_file)
        if json_data:
            old_json = find_matching_json(file_path)
            if old_json:
                new_json = new_file.parent / (new_file.stem + old_json.suffix)
                shutil.move(old_json, new_json)
        return update_exif(new_file, json_data)

    # Handle OtherImageStart errors by skipping
    if "OtherImageStart" in stderr:
        return "SKIPPED", date_str, stderr

    if result.returncode != 0:
        return "FAILED", date_str, stderr or "Exiftool failed"

    # Validate
    validate = subprocess.run(
        ["exiftool", "-ignoreMinorErrors", "-DateTimeOriginal", "-s3", str(file_path)],
        capture_output=True, text=True
    )
    actual = validate.stdout.strip()
    if actual != date_str:
        return "FAILED", date_str, f"Validation mismatch (read {actual})"

    return "UPDATED", date_str, None


def main():
    root = Path(input("Enter path to Takeout folder: ").strip()).expanduser()
    if not root.exists():
        print("❌ Path does not exist")
        return

    # Loop through all non-JSON files
    all_files = [f for f in root.rglob("*") if f.is_file() and not f.name.lower().endswith(".json")]
    total = len(all_files)
    print(f"\nFound {total} non-JSON files to check\n")

    updated = skipped = failed = 0

    for idx, file_path in enumerate(all_files, start=1):
        try:
            json_file = find_matching_json(file_path)
            json_data = None
            if json_file:
                try:
                    with open(json_file, "r", encoding="utf-8") as f:
                        json_data = json.load(f)
                except Exception as e:
                    failed += 1
                    print(f"[FAILED] {json_file} → {e}")
                    continue

            status, date_used, error = update_exif(file_path, json_data)
            if status == "UPDATED":
                updated += 1
            elif status == "FAILED":
                failed += 1
                print(f"[FAILED] {file_path} → {error}")
            else:  # SKIPPED
                skipped += 1
                print(f"[SKIPPED] {file_path} → {error}")

        except Exception as e:
            failed += 1
            print(f"[FAILED] {file_path} → {e}")

        percent = (idx / total) * 100
        print(f"Progress: {idx}/{total} ({percent:.1f}%)", end="\r")

    print("\n\n✅ Done")
    print(f"Updated: {updated}")
    print(f"Skipped: {skipped}")
    print(f"Failed:  {failed}")
    print(f"Total:   {total}")


if __name__ == "__main__":
    main()
