# Enrollware Instructor Backup -> Enroll Nationwide Sync

This project automates instructor migration from Enrollware to Enroll Nationwide.

It does the following:

1. Logs into Enrollware with Selenium.
2. Opens each instructor record.
3. Builds an instructor payload and creates the instructor in Enroll Nationwide (`instructors/store`).
4. Fetches instructor list from Enroll Nationwide (`instructors`) to get the instructor ID and existing documents.
5. Downloads only missing Enrollware files (based on filename match against remote `document_path`).
6. Uploads files one-by-one to Enroll Nationwide (`documents/store`).
7. Logs skipped/failed cases into CSV for retry.

---

## Project Layout

- `automation/main.py` - main workflow
- `automation/Utils/functions.py` - login, data extraction, validation, helper parsing
- `automation/Utils/utils.py` - Selenium/browser utility helpers
- `automation/enroll_nationwide_api/api_client.py` - API client wrapper
- `automation/enroll_nationwide_api/api_endpoints.py` - endpoint constants
- `automation/enroll_nationwide_api/api_headers.py` - API headers (uses `AUTH_TOKEN`)
- `Instructor records/` - downloaded files and run artifacts

---

## Requirements

- Windows machine
- Python 3.10+ (3.12 works in this repo)
- Google Chrome installed
- Valid Enrollware credentials
- Valid Enroll Nationwide API bearer token

Install dependencies:

```powershell
python -m pip install -r requirements.txt
```

> Note: `requirements.txt` appears to be UTF-16 encoded in this workspace. If pip has trouble reading it, re-save the file as UTF-8 and run install again.

---

## Configuration

Create a `.env` file in the project root:

```env
ENROLLWARE_USERNAME=your_enrollware_username
ENROLLWARE_PASSWORD=your_enrollware_password
AUTH_TOKEN=your_enroll_nationwide_bearer_token
```

### Important

- `ENROLLWARE_USERNAME` and `ENROLLWARE_PASSWORD` are required by `login_to_enrollware_and_navigate_to_instructor_records`.
- `AUTH_TOKEN` is required for all Enroll Nationwide API calls.
- Do not commit `.env`, tokens, or secrets to git.

---

## How to Run

From project root:

```powershell
python automation/main.py
```

What happens during a run:

- Browser opens (headless mode is enabled in code).
- Script navigates to Enrollware instructor list.
- Each instructor URL is processed once.
- Processed URLs are written to `Instructor records/done_urls.txt`.

---

## Output Files

Inside `Instructor records/`:

- `done_urls.txt` - URLs already processed (prevents duplicate re-processing)
- `instructors_skipped.csv` - skipped/failed records and reason
- downloaded files (temporary, deleted after upload attempt)

CSV columns:

- `name`
- `email`
- `username`
- `files`
- `reason`

Common `reason` values:

- `missing fields: ...`
- `creation_failed`
- `not_found_in_list`
- `no_instructor_id`
- `no_files_found`
- `all_files_already_present`
- `no_files_to_upload`
- `failed_uploads`

---

## File Matching Logic (Current Flow)

When deciding what to upload:

1. Fetch `documents` from the matched instructor in Enroll Nationwide.
2. Extract filename from each `document_path`.
3. Compare each Enrollware file name (case-insensitive) to the remote filename set.
4. Skip files that already exist remotely.
5. Download/upload only missing files.

This avoids duplicate uploads and supports partial sync.

---

## Troubleshooting

### 1) "Target machine actively refused it" / WinError 10061

Usually means the browser session/driver connection was interrupted.

Check:

- Chrome and ChromeDriver compatibility
- local firewall/AV blocking localhost WebDriver port
- stale Chrome profile lock in `automation/Utils/chrome-dir/`

Quick actions:

1. Close all Chrome/chromedriver processes.
2. Retry run.
3. If needed, clear `automation/Utils/chrome-dir/` lock artifacts.

### 2) API auth errors (401/403)

- Verify `AUTH_TOKEN` is valid and not expired.
- Ensure `.env` is loaded in the runtime context.

### 3) Files fail with 413

- The script logs: `file size is too large` for status 413.
- Reduce file size or upload manually for oversized files.

### 4) Instructor not found after create

- API list call can lag; script already includes a short delay.
- Re-run to pick up records that were created but not immediately visible.

### 5) "No files uploaded" but local files exist

- Check filename mismatch between Enrollware and remote `document_path`.
- Validate file download links are still accessible in Enrollware UI session.

---

## Operational Notes

- The script deletes local downloaded files after each upload attempt (success or failure).
- Existing instructors are skipped on create if API message contains: `The username has already been taken.`
- If instructor exists but has missing docs remotely, missing files are still uploaded.

---

## Safe Retry Strategy

If a run fails midway:

1. Fix the root cause (token, connectivity, driver, file issue).
2. Re-run `python automation/main.py`.
3. `done_urls.txt` prevents reprocessing completed URLs.
4. Use `instructors_skipped.csv` to inspect unresolved records.

---

## Developer Tips

- Main entry point: `automation/main.py`
- To change payload mapping: edit `build_instructor_payload` in `automation/main.py`
- To adjust required validation fields: edit `instructor_is_valid` in `automation/Utils/functions.py`
- To change browser behavior (headless/user-data): edit `get_undetected_driver` in `automation/Utils/utils.py`

---

## Disclaimer

Use this automation only with approved access to Enrollware and Enroll Nationwide data.
Handle credentials and instructor documents according to your organization security policy.

