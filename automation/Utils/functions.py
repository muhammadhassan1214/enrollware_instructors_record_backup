from selenium.webdriver.common.by import By
from .utils import safe_navigate_to_url, check_element_exists, input_element, click_element_by_js, select_by_text, logger
import os
import re
import time
from dotenv import load_dotenv

# Load environment variables and validate
load_dotenv()

# Validate required environment variables
REQUIRED_ENV_VARS = ["ENROLLWARE_USERNAME", "ENROLLWARE_PASSWORD"]

def validate_environment_variables() -> bool:
    missing_vars = [var for var in REQUIRED_ENV_VARS if not os.getenv(var)]
    if missing_vars:
        logger.error(f"Missing required environment variables: {missing_vars}")
        return False
    return True

def login_to_enrollware_and_navigate_to_instructor_records(driver, max_retries: int = 3) -> bool:
    if not validate_environment_variables():
        return False

    for attempt in range(max_retries):
        try:
            if not safe_navigate_to_url(driver, "https://enrollware.com/admin"):
                continue

            time.sleep(3)

            # Check if already logged in
            validation_button = check_element_exists(driver, (By.ID, "loginButton"), timeout=5)

            if validation_button:
                # Input credentials with validation
                if not input_element(driver, (By.ID, "username"), os.getenv("ENROLLWARE_USERNAME")):
                    logger.error("Failed to input username")
                    continue

                if not input_element(driver, (By.ID, "password"), os.getenv("ENROLLWARE_PASSWORD")):
                    logger.error("Failed to input password")
                    continue

                # Optional remember me checkbox
                click_element_by_js(driver, (By.ID, "rememberMe"))
                time.sleep(1)

                if not click_element_by_js(driver, (By.ID, "loginButton")):
                    logger.error("Failed to click login button")
                    continue

                # Wait for login to complete
                time.sleep(20)

                # Verify login success
                if "admin" in driver.current_url.lower():
                    logger.info("Successfully logged into Enrollware")
                else:
                    logger.warning("Login may have failed, checking current URL")
                    continue

            return navigate_to_instructor_records(driver)

        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(3)
                continue

    logger.error("Failed to login to Enrollware after all attempts")
    return False


def navigate_to_instructor_records(driver, max_retries: int = 3) -> bool:
    for attempt in range(max_retries):
        try:
            url = "https://www.enrollware.com/admin/instructor-list.aspx"
            if safe_navigate_to_url(driver, url):
                logger.info("Successfully navigated to Instructor Records")
                # apply all filters
                select_by_text(driver, (By.XPATH, "//div[@class='dataTables_length']//select"), 'All')
                return True
        except Exception as e:
            logger.error(f"Navigation attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                time.sleep(2)
                continue

    logger.error("Failed to navigate to Instructor Records after all attempts")
    return False

def clean_username(entry: str) -> str:
    stop_words = {'monitoring', 'complete', 'needs'}
    parts = [p.strip() for p in entry.split(',')]
    # Extract all valid words before comma
    candidates = re.findall(r'[A-Za-z\-]+', parts[0])
    # Filter out stop words (case-insensitive)
    last_name_clean = 'unknown'
    for word in reversed(candidates):
        if word.lower() not in stop_words:
            last_name_clean = word
            break
    first_name = parts[1] if len(parts) > 1 else ''
    first_name_clean = re.sub(r'[^A-Za-z\- ]', '', first_name).strip()
    if first_name_clean:
        return f"{first_name_clean} {last_name_clean}"
    return last_name_clean
