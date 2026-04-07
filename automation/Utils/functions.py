from selenium.webdriver.common.by import By
import os
import re
import time
import logging
import json
import difflib
from typing import List
from dotenv import load_dotenv
from .utils import (
    safe_navigate_to_url, check_element_exists,
    input_element, click_element_by_js, select_by_text,
    get_element_attribute, check_if_attribute_exists
)

# Load environment variables and validate
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

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

        except:
            if attempt < max_retries - 1:
                time.sleep(3)
                continue

    logger.error("Failed to login to Enrollware after all attempts")
    return False


def navigate_to_instructor_records(driver, max_retries: int = 3) -> bool:
    for attempt in range(max_retries):
        try:
            url = "https://www.enrollware.com/admin/tc-user-list.aspx"
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
    # Status phrases and non-name words to remove
    status_patterns = [
        r"\*\*.*?\*\*",  # **Monitoring Complete** etc.
        r"\(.*?\)",  # (Complete and sent to Nathan) etc.
        r"CODEBLUE CPR CLASSES",  # custom status phrase
        r"Completed with Nathan Shell",  # custom status phrase
        r"Complete and sent to Nathan",  # custom status phrase
        r"Needs Monitoring",  # custom status phrase
        r"Monitoring Complete",  # custom status phrase
        r"Complete",  # custom status phrase
        r"sent to Nathan",  # custom status phrase
    ]
    # Remove status phrases
    clean_entry = entry
    for pat in status_patterns:
        clean_entry = re.sub(pat, '', clean_entry, flags=re.IGNORECASE)
    # Split by comma
    parts = [p.strip() for p in clean_entry.split(',')]
    # If only one part, try to split by whitespace for first/last name
    if len(parts) == 1:
        words = [w for w in parts[0].split() if w]
        if len(words) == 2:
            # e.g. 'ZACHARIAS JOSEPH' => 'JOSEPH ZACHARIAS'
            return f"{words[1]} {words[0]}"
        elif len(words) > 2:
            # e.g. 'Williams-Patterson Nickesha' => 'Nickesha Williams-Patterson'
            return f"{words[-1]} {' '.join(words[:-1])}"
        elif len(words) == 1:
            return words[0]
        else:
            return "unknown"
    # Last name logic
    last_name = parts[1]
    last_name_words = [w for w in re.findall(r'[A-Za-z\-]+', last_name) if w]
    last_name_clean = ' '.join(last_name_words) if last_name_words else 'unknown'
    # First name logic
    first_name = parts[0] if len(parts) > 1 else ''
    first_name_words = [w for w in re.findall(r'[A-Za-z\-]+', first_name) if w]
    first_name_clean = ' '.join(first_name_words) if first_name_words else ''
    # If first name is missing, return last name or unknown
    if not first_name_clean:
        return last_name_clean if last_name_clean != 'unknown' else 'unknown'
    return f"{first_name_clean} {last_name_clean}"


def get_element_value(driver, element_id: str) -> str:
    try:
        locator = (By.ID, f"mainContent_{element_id}")
        value = get_element_attribute(driver, locator, "value")
        if value is not None:
            return value
        else:
            logger.warning(f"Element {locator} does not have a 'value' attribute.")
            return ""
    except Exception as e:
        logger.error(f"An error occurred while getting element value: {e}")
        return ""


def get_checkbox_value(driver, element_id: str) -> str:
    try:
        locator = (By.ID, f"mainContent_{element_id}")
        return '1' if check_if_attribute_exists(driver, locator, "checked") else '0'
    except Exception as e:
        logger.error(f"An error occurred while getting checkbox value: {e}")
        return '0'


def get_best_match_id(api_response, target_string):
    # Parse the response if it's passed as a JSON string
    if isinstance(api_response, str):
        try:
            parsed_data = json.loads(api_response)
        except json.JSONDecodeError:
            return None
    else:
        parsed_data = api_response

    # Extract all company names
    companies = parsed_data.get('data', [])
    company_names = [item.get('company_name', '') for item in companies]

    if not company_names:
        return None

    # Find the single best match (cutoff=0.0 ensures it always returns the closest match)
    best_matches = difflib.get_close_matches(target_string, company_names, n=1, cutoff=0.0)

    if best_matches:
        best_match_name = best_matches[0]
        # Return the ID associated with the best matched company name
        for item in companies:
            if item.get('company_name') == best_match_name:
                return item.get('id')

    return None


def instructor_is_valid(data: dict) -> List[str]:
    required_fields = [
        'username',
        'training_site_id',
        'country_id',
        'password',
        'email',
        'first_name',
        'last_name',
        'city',
        'address_line_1',
        'zip_postal_code',
        'state_province_region',
    ]
    return [field for field in required_fields if str(data.get(field, '')).strip() == '']


def extract_instructors_list(response) -> list:
    if isinstance(response, list):
        return response
    if isinstance(response, dict):
        data = response.get("data")
        if isinstance(data, dict):
            instructors_list = data.get("data")
            if isinstance(instructors_list, list):
                return instructors_list
    return []


def extract_document_filenames(documents) -> set:
    """Return normalized remote document file names from instructor documents list."""
    names = set()
    if not isinstance(documents, list):
        return names
    for document in documents:
        if not isinstance(document, dict):
            continue
        document_path = str(document.get("document_path") or "").strip()
        if not document_path:
            continue
        names.add(os.path.basename(document_path).strip().lower())
    return names


def extract_response_message(response) -> str:
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
