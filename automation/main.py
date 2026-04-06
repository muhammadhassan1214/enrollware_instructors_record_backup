import os
import csv
import sys
import time
import shutil
import logging
import requests
import mimetypes
from typing import Optional
from selenium.webdriver.common.by import By
from enroll_nationwide_api.api_client import APIClient
from enroll_nationwide_api.api_endpoints import APIEndpoints
from Utils.utils import get_undetected_driver, get_element_text
from Utils.functions import (
    login_to_enrollware_and_navigate_to_instructor_records,
    clean_username, get_element_value, get_checkbox_value,
    instructor_is_valid, get_best_match_id
)

# Ensure the parent directory is in sys.path for reliable imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

logger = logging.getLogger("main")
logging.basicConfig(level=logging.INFO)


def get_ts_id(api_client, training_site_text) -> Optional[str]:
    if training_site_text == "TS68082 Code Blue CPR Services, LLC (AHA ACCOUNT)":
        return "3"
    ts_data = api_client.get(APIEndpoints.TRAINING_SITES_LIST)
    return get_best_match_id(ts_data, training_site_text)


def build_instructor_payload(driver, api_client) -> dict:
    """Template payload builder for the instructors/store endpoint."""
    address1 = get_element_value(driver, "address1")
    city = get_element_value(driver, "city")
    state = get_element_value(driver, "stateprovince")
    zip_code = get_element_value(driver, "zip")
    phone = get_element_value(driver, "txtPhone")
    ts_locator = (By.XPATH, "//select[@id='mainContent_trainingSite']/option[@selected='selected']")
    training_site_text = get_element_text(driver, ts_locator)

    isAdmin = "2" if get_checkbox_value(driver, "adminCk") == "1" else "0"
    isInstructor = "3" if get_checkbox_value(driver, "instructorCk") == "1" else "0"
    isInstructorAssistant = "4" if get_checkbox_value(driver, "assistantCk") == "1" else "0"

    # 1. Build the base payload
    payload = {
        # Core identity fields
        "username": get_element_value(driver, "username"),
        "training_site_id": get_ts_id(api_client, training_site_text),
        "first_name": get_element_value(driver, "fname"),
        "last_name": get_element_value(driver, "lname"),
        "address_line_1": "123 Main St" if not address1 else address1,
        "address_line_2": get_element_value(driver, "address2"),
        "city": "Anytown" if not city else city,
        "state_province_region": "State" if not state else state,
        "country_id": "184",
        "mobile_phone": "999-999-9999" if not phone else phone,
        "email": get_element_value(driver, "Email"),
        "zip_postal_code": "00000" if not zip_code else zip_code,
        "name_to_print_on_card": get_element_value(driver, "nameOnCard"),
        "aha_instructor_id": get_element_value(driver, "ahaInstructorId"),
        "hsi_instructor_id": get_element_value(driver, "ashiInstructorId"),
        "rclc_username": get_element_value(driver, "redCrossId"),
        "password": "12345678",
        "active_user": get_checkbox_value(driver, "ActiveUser"),
        "read_only_user": get_checkbox_value(driver, "isReadOnly"),
        "allow_bid_on_open_classes": "0",
    }

    # 2. Conditionally build the roles list
    roles = []
    if isAdmin != "0":
        roles.append(2)
    if isInstructor != "0":
        roles.append(3)
    if isInstructorAssistant != "0":
        roles.append(4)

    # 3. Add the roles key to the dictionary only if the list isn't empty
    if roles:
        payload["roles[]"] = roles

    return payload


def _extract_response_message(response) -> str:
    if isinstance(response, dict):
        message = response.get("message")
        if message:
            return str(message)
        data = response.get("data")
        if isinstance(data, dict):
            nested_message = data.get("message")
            if nested_message:
                return str(nested_message)
    return ""


def create_instructor(api_client: APIClient, payload: dict) -> str:
    """Create instructor without files; returns: created, exists, or failed."""
    username = payload.get("username", "")
    duplicate_msg = "The username has already been taken."
    try:
        response = api_client.post(APIEndpoints.INSTRUCTOR_CREATE, payload=payload)
        message = _extract_response_message(response)
        if duplicate_msg in message:
            logger.info(f"Skipping existing instructor {username}: {duplicate_msg}")
            return "exists"
        logger.info(f"Created instructor in API: {username}")
        return "created"
    except Exception as exc:
        error_text = str(exc)
        if duplicate_msg in error_text:
            logger.info(f"Skipping existing instructor {username}: {duplicate_msg}")
            return "exists"
        logger.error(f"Failed to create instructor {username}: {exc}")
        return "failed"


def _extract_instructors_list(response) -> list:
    if isinstance(response, list):
        return response
    if isinstance(response, dict):
        data = response.get("data")
        if isinstance(data, dict):
            instructors_list = data.get("data")
            if isinstance(instructors_list, list):
                return instructors_list
    return []


def find_instructor_by_email(api_client: APIClient, email: str) -> Optional[dict]:
    time.sleep(0.5)
    target = (email or "").strip().lower()
    try:
        response = api_client.get(APIEndpoints.INSTRUCTOR_LIST)
        for entry in _extract_instructors_list(response):
            if not isinstance(entry, dict):
                continue
            entry_username = str(entry.get("email", "")).strip().lower()
            if entry_username == target:
                return entry
        logger.info(f"Instructor {email} not found in instructors list")
        return None
    except Exception as exc:
        logger.error(f"Error fetching instructors list: {exc}")
        return None


def upload_document(api_client: APIClient, instructor_id: str, file_path: str) -> bool:
    if not os.path.exists(file_path):
        logger.warning(f"File missing before upload, skipping: {file_path}")
        return False
    mime_type = mimetypes.guess_type(file_path)[0] or "application/octet-stream"
    try:
        with open(file_path, "rb") as fh:
            files = [("document_path", (os.path.basename(file_path), fh, mime_type))]
            api_client.post(APIEndpoints.INSTUCTOR_DOCUMENT_CREATE, payload={"instructor_id": instructor_id}, files=files)
        logger.info(f"Uploaded document for instructor {instructor_id}: {file_path}")
        return True
    except Exception as exc:
        cause = getattr(exc, "__cause__", None)
        response = getattr(cause, "response", None)
        if response is not None and getattr(response, "status_code", None) == 413:
            logger.error("API respond with an error, Error: file size is too large")
            return False
        logger.error(f"Failed to upload document {file_path} for instructor {instructor_id}: {exc}")
        return False


class CreateInstructorsBackup:
    def __init__(self):
        self.driver = None

    def initialize(self) -> bool:
        try:
            headless = True
            self.driver = get_undetected_driver(headless=headless)
            if self.driver:
                logger.info(f"Chrome driver initialized successfully, mode: {'headless' if headless else 'headed'}")
                return True
            else:
                logger.error("Failed to initialize Chrome driver")
                return False
        except Exception as e:
            logger.error(f"Initialization failed: {e}")
            return False

    def cleanup(self):
        if self.driver:
            try:
                self.driver.quit()
                logger.info("Resources cleaned up successfully")
            except Exception as e:
                logger.error(f"Error during cleanup: {e}")


def append_to_csv(csv_path: str, row: dict) -> None:
    """Append a row to the CSV log, creating headers if the file is new."""
    headers = ["name", "email", "username", "files", "reason"]
    file_exists = os.path.exists(csv_path)
    with open(csv_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        if not file_exists:
            writer.writeheader()
        writer.writerow({
            "name": row.get("name", ""),
            "email": row.get("email", ""),
            "username": row.get("username", ""),
            "files": row.get("files", ""),
            "reason": row.get("reason", ""),
        })


def generate_record(name, payload, reason, _files = "") -> dict:
    record = {
        "name": name,
        "email": payload.get("email", ""),
        "username": payload.get("username", ""),
        "files": _files,
        "reason": reason,
    }
    return record


def main():
    keep_instructors_files = int(input("\nDo you want to keep instructor' data locally?\nIf Yes enter 1 If No enter 0: "))
    all_instructors_urls = []
    url = "https://www.enrollware.com/admin/tc-user-list.aspx"
    processor = CreateInstructorsBackup()
    api_client = APIClient()
    try:
        if not processor.initialize():
            return
        if not login_to_enrollware_and_navigate_to_instructor_records(processor.driver):
            return

        downloads_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "Instructor records")
        if not os.path.exists(downloads_dir):
            os.makedirs(downloads_dir, exist_ok=True)
        csv_log_path = os.path.join(downloads_dir, "instructors_skipped.csv")

        instructor_urls = processor.driver.find_elements(By.XPATH, "//td/a[contains(@href, 'user-edit')]")
        for instructor_url in instructor_urls:
            _url = instructor_url.get_attribute("href")
            all_instructors_urls.append(_url)

        for url in all_instructors_urls:
            # Check if the instructor's URL has already been processed to avoid duplicates
            done_urls_path = os.path.join(downloads_dir, "done_urls.txt")
            if os.path.exists(done_urls_path):
                with open(done_urls_path, "r", encoding="utf-8") as f:
                    done_urls = set(line.strip() for line in f)
                if url in done_urls:
                    logger.info(f"Skipping already processed URL: {url}")
                    continue
            processor.driver.get(url)
            payload = build_instructor_payload(processor.driver, api_client)
            full_name = payload.get("first_name", "") + " " + payload.get("last_name", "")
            email_hint = payload.get("email", "")

            name = clean_username(full_name)
            if name == "unknown":
                name = f"No username ({email_hint})" if email_hint else "No username"
                name = name.replace('"Rex"', "")


            # check if the instructor's folder already exists
            owner_folder = os.path.join(downloads_dir, name)
            if os.path.exists(owner_folder):
                logger.info(f"Owner folder already exists, skipping: {name}")
                continue

            # create a local directory for saving instructor's files
            os.makedirs(owner_folder, exist_ok=True)
            all_files = processor.driver.find_elements(By.XPATH, "//a[@title= 'View']")
            if not all_files:
                logger.info(f"No files found for instructor: {name}")
                record = generate_record(name, payload, "no_files")
                append_to_csv(csv_log_path, record)
                continue

            # Download instructor's files from Enrollware and save to local directory
            file_paths = []
            for file_link in all_files:
                file_url = file_link.get_attribute("href")
                file_name = str(file_link.text.strip()) or "unknown_file"
                local_path = os.path.join(owner_folder, file_name)
                if os.path.exists(local_path):
                    logger.info(f"File already exists, skipping download: {file_name}")
                    file_paths.append(local_path)
                    continue
                try:
                    response = requests.get(file_url, stream=True)
                    if response.status_code == 200:
                        with open(local_path, "wb") as f:
                            shutil.copyfileobj(response.raw, f)
                        logger.info(f"Downloaded: {file_name}")
                        file_paths.append(local_path)
                    else:
                        logger.error(f"Failed to download {file_url} for instructor {name}")
                except Exception as e:
                    logger.error(f"Exception downloading {file_url} for instructor {name}: {e}")

            # Validate instructor data before attempting API creation
            missing_fields = instructor_is_valid(payload)
            if missing_fields:
                missing_reason = f"missing fields: {', '.join(missing_fields)}"
                logger.warning(f"Incomplete data for instructor {name}, skipping API create ({missing_reason})")
                record = generate_record(name, payload, missing_reason)
                append_to_csv(csv_log_path, record)
                continue

            # Create instructor / Pass if already exist
            create_status = create_instructor(api_client, payload)
            if create_status != "created":
                if create_status == "exists":
                    pass
                else:
                    record = generate_record(name, payload, "creation_failed")
                    append_to_csv(csv_log_path, record)
                    continue

            # Find instructor using email for making another API call for uploading documents
            instructor_entry = find_instructor_by_email(api_client, payload.get("email", ""))
            if not instructor_entry:
                record = generate_record(name, payload, "not_found_in_list")
                append_to_csv(csv_log_path, record)
                continue

            # Extract instructor Enroll Nationwide ID for uploading documents; if not found, log and skip uploads
            instructor_id = str(instructor_entry.get("id") or "").strip()
            if not instructor_id:
                record = generate_record(name, payload, "no_instructor_id")
                append_to_csv(csv_log_path, record)
                continue

            # Check if the instructor's documents are already uploaded
            documents = instructor_entry.get("documents")
            has_remote_documents = isinstance(documents, list) and len(documents) > 0
            if create_status == "exists" and has_remote_documents:
                logger.info(f"Skipping uploads for existing instructor {name}: documents already exist")
                continue

            if not file_paths:
                record = generate_record(name, payload, "no_files_to_upload")
                append_to_csv(csv_log_path, record)
                continue

            # Upload documents to enrollnationwide API; if any upload fails, log the failed files and reason
            failed_uploads = []
            for path in file_paths:
                if not upload_document(api_client, instructor_id, path):
                    failed_uploads.append(os.path.basename(path))
                    continue

            if failed_uploads:
                record = generate_record(name, payload, "failed_uploads", _files="; ".join(failed_uploads))
                append_to_csv(csv_log_path, record)

            # add url to done_urls.txt for avoiding re-processing
            with open(done_urls_path, "a", encoding="utf-8") as f:
                f.write(url + "\n")

        processor.cleanup()
        print("\nAll files processed and sent to enrollnationwide API.\n")


    except Exception as e:
        logger.error(f"Unexpected error in main: {e}")
    finally:
        if 'processor' in locals():
            processor.cleanup()


if __name__ == "__main__":
    main()
