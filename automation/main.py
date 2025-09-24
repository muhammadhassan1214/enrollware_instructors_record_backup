import sys
import os
import time
import logging
import requests
import shutil
from selenium.webdriver.common.by import By
from Utils.utils import (
    get_undetected_driver,
    safe_navigate_to_url,
    check_element_exists,
    get_element_attribute,
    get_element_text,
)
from Utils.drive_uploader import (
    authenticate,
    get_folder_id,
    upload_or_update_file
)
from Utils.functions import (
    login_to_enrollware_and_navigate_to_instructor_records,
    clean_username
)

# Ensure the parent directory is in sys.path for reliable imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

logger = logging.getLogger("main")
logging.basicConfig(level=logging.INFO)

class CreateInstructorsBackup:
    def __init__(self):
        self.driver = None

    def initialize(self) -> bool:
        try:
            self.driver = get_undetected_driver()
            if self.driver:
                logger.info("Chrome driver initialized successfully")
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

def main():
    instructors_info = []
    url = "https://www.enrollware.com/admin/tc-user-list.aspx"
    processor = CreateInstructorsBackup()
    try:
        if not processor.initialize():
            return
        if not login_to_enrollware_and_navigate_to_instructor_records(processor.driver):
            return
        # Authenticate Google Drive and get root folder
        drive_service = authenticate()
        root_folder_id = get_folder_id(drive_service, "Instructor records")
        downloads_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "Instructor records")
        if not os.path.exists(downloads_dir):
            os.makedirs(downloads_dir, exist_ok=True)
        all_instructors_urls = processor.driver.find_elements(By.XPATH, "//td/a[contains(@href, 'instructor-record')]")
        all_instructors_usernames = processor.driver.find_elements(By.XPATH, "//td/a[contains(@href, 'mail')]/parent::td")
        logger.info("Fetching all instructors' URLs and usernames...")
        for instructor_url, instructor_username in zip(all_instructors_urls, all_instructors_usernames):
            url = instructor_url.get_attribute("href")
            name = clean_username(instructor_username.text.split('\n')[0].strip())
            if name == "unknown":
                name = f"No username ({instructor_username.text.split('\n')[1].strip()})"
            instructors_info.append((url, name))
        logger.info("Fetched all instructors' URLs and usernames. Starting processing...")
        for user_url, username in instructors_info:
            try:
                safe_navigate_to_url(processor.driver, user_url)
                # Ensure local and Drive folder for user
                owner_folder = os.path.join(downloads_dir, username)
                # Check if owner folder already exists, skip if it does
                if os.path.exists(owner_folder):
                    logger.info(f"Owner folder already exists, skipping: {username}")
                    continue
                if not os.path.exists(owner_folder):
                    os.makedirs(owner_folder, exist_ok=True)
                owner_drive_id = get_folder_id(drive_service, username, root_folder_id)
                no_record_selector = (By.XPATH, "//h3[contains(text(), 'Course "
                                                "Details')]/parent::div/following-sibling::div/div/div[contains(text("
                                                "), 'There are no records found')]")
                no_record_found = check_element_exists(processor.driver, no_record_selector, timeout=1)
                if no_record_found:
                    logger.info(f"No records found for user: {username}")
                    continue
                # Find all records
                all_records_elements = processor.driver.find_elements(By.XPATH, "//td/a[contains(@href, 'ts-class-view')]")
                logger.info(f"Found {len(all_records_elements)} records for user: {username}")
                all_records = []
                for record_element in all_records_elements:
                    record_url = record_element.get_attribute("href")
                    all_records.append(record_url)
                for i, record_url in enumerate(all_records):
                    safe_navigate_to_url(processor.driver, record_url)
                    # Find file link
                    link_selector = (By.XPATH, "//a[@title= 'View']")
                    link = check_element_exists(processor.driver, link_selector, timeout=1)
                    if not link:
                        logger.info(f"No file found for {username}'s record {i + 1}/{len(all_records)}")
                        continue
                    file_url = get_element_attribute(processor.driver, link_selector, "href")
                    file_name = get_element_text(processor.driver, link_selector, timeout=3)
                    if file_url and file_name:
                        local_path = os.path.join(owner_folder, file_name)
                        # Additional check: skip if file already exists locally
                        if os.path.exists(local_path):
                            logger.info(f"File already exists locally, skipping: {username}/{file_name}")
                            continue
                        # Download file immediately
                        try:
                            response = requests.get(file_url, stream=True)
                            if response.status_code == 200:
                                with open(local_path, "wb") as f:
                                    shutil.copyfileobj(response.raw, f)
                                logger.info(f"Downloaded: {username}/{file_name}")
                                # Upload to Google Drive immediately
                                upload_or_update_file(drive_service, owner_drive_id, local_path, file_name)
                            else:
                                logger.error(f"Failed to download {file_url}")
                        except Exception as e:
                            logger.error(f"Exception downloading/uploading {file_url}: {e}")
            except Exception as e:
                safe_navigate_to_url(processor.driver, url)
                time.sleep(2)
        processor.cleanup()
        print("\nAll files processed and backed up locally and to Google Drive.\n")
    except Exception as e:
        logger.error(f"Unexpected error in main: {e}")
    finally:
        if 'processor' in locals():
            processor.cleanup()

if __name__ == "__main__":
    main()
