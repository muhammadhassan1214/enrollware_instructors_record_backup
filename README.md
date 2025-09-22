# Enrollware Instructors Record Backup

## Overview
This project automates the backup of instructor records from Enrollware, downloading files locally and synchronizing them to Google Drive. It uses Selenium for browser automation and the Google Drive API for cloud storage.

## Features
- Automated login to Enrollware using environment credentials
- Scrapes instructor URLs and usernames, cleans messy data
- Downloads instructor record files locally
- Uploads and syncs files to Google Drive, organized by instructor
- Robust error handling and logging

## Prerequisites
- Python 3.8+
- Google Chrome browser
- ChromeDriver (compatible with your Chrome version)
- Enrollware admin credentials
- Google Cloud project with Drive API enabled
- `credentials.json` for Google OAuth (download from Google Cloud Console)

## Installation
1. **Clone the repository:**
   ```sh
   git clone <https://github.com/muhammadhassan1214/enrollware_instructors_record_backup.git>
   cd enrollware_instructors_record_backup
   ```
2. **Install dependencies:**
   ```sh
   pip install -r requirements.txt
   ```
3. **Set up environment variables:**
   - Copy `Example env.env` to `.env` and fill in your Enrollware credentials.
   - Place your `credentials.json` in `automation/Utils/`.

## Usage
1. **Run the main script:**
   ```sh
   python automation/main.py
   ```
2. **What happens:**
   - The script logs into Enrollware, navigates to instructor records, and fetches all instructor URLs and usernames.
   - It downloads each instructor's files to `Instructor records/` locally.
   - Files are uploaded to Google Drive in folders named after each instructor.

## File Structure
```
├── automation/
│   ├── main.py                # Main workflow script
│   ├── Utils/
│   │   ├── functions.py       # Core logic (login, username cleaning)
│   │   ├── drive_uploader.py  # Google Drive helpers
│   │   ├── utils.py           # Selenium helpers
│   │   ├── credentials.json   # Google OAuth credentials
│   │   ├── token.json         # Generated after first Google login
│   └── downloads/             # Downloaded files (if used)
├── Instructor records/        # Local backup of instructor files
├── README.md                  # This guide
├── Example env.env            # Example environment file
```

## Customization
- **Google Drive Folder Name:** Change in `main.py` and `drive_uploader.py` if needed.

## Troubleshooting
- **Login Issues:** Ensure credentials in `.env` are correct and ChromeDriver matches your browser.
- **Google Drive Errors:** Check `credentials.json` and API access.
- **File Not Downloading:** Inspect logs for missing links or network issues.

## Contributing
Pull requests and suggestions are welcome! Please open an issue for bugs or feature requests.

## License
MIT License

---
**Contact:** For help, reach out to the project maintainer or open an issue on GitHub.

