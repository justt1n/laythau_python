import codecs
import json
import logging
import os
import platform
import time
from datetime import datetime
from telnetlib import EC

import gspread
from dotenv import load_dotenv
from oauth2client.service_account import ServiceAccountCredentials
from selenium import webdriver
from selenium.common.exceptions import StaleElementReferenceException
from selenium.common.exceptions import WebDriverException
from selenium.webdriver import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

### SETUP ###
load_dotenv('settings.env')

## GLOBAL VARIABLES ##
gsp = None
driver = None
HOST_DATA = None
BLACKLIST = None


def setup_logging():
    # Load environment variables at the beginning of the script
    load_dotenv('settings.env')

    # Configure logging from environment variables
    log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
    log_format = os.getenv('LOG_FORMAT', '%(asctime)s - %(message)s')

    # Create log file based on the current date in the logs/ directory
    log_dir = 'logs'
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, f"{datetime.now().strftime('%Y-%m-%d')}_function_calls.log")

    logging.basicConfig(filename=log_file, level=log_level, format=log_format)


def print_function_name(func):
    def wrapper(*args, **kwargs):
        try:
            log_message = f"Calling function: {func.__name__} with args: {args} and kwargs: {kwargs}"
            logging.info(log_message)
            return func(*args, **kwargs)
        except Exception as e:
            logging.error(f"Error in function {func.__name__}: {e}")
            raise

    return wrapper


### SELENIUM RETRY FUNCTIONS ###


def get_cell_text(cell, retries=3):
    for _ in range(retries):
        try:
            return cell.text
        except StaleElementReferenceException:
            time.sleep(0.25)
    raise StaleElementReferenceException("Failed to get cell text after retries")


def get_row_elements(row, retries=3):
    while retries > 0:
        try:
            return row.find_elements(By.TAG_NAME, 'td')
        except StaleElementReferenceException:
            retries -= 1
            if retries == 0:
                raise
            time.sleep(0.25)


def find_link_element(cell, retries=3):
    for _ in range(retries):
        try:
            return cell.find_elements(By.TAG_NAME, 'a')[1]
        except StaleElementReferenceException:
            time.sleep(0.25)
    raise StaleElementReferenceException("Failed to find link element after retries")


def get_link_attribute(link_element, attribute='href', retries=3):
    for _ in range(retries):
        try:
            return link_element.get_attribute(attribute)
        except StaleElementReferenceException:
            time.sleep(0.25)
    raise StaleElementReferenceException(f"Failed to get attribute '{attribute}' after retries")


def get_row_elements_with_retries(row, retries=3):
    for _ in range(retries):
        try:
            return row.find_elements(By.TAG_NAME, 'td')
        except StaleElementReferenceException:
            time.sleep(0.25)
    raise StaleElementReferenceException("Failed to find row elements after retries")


def find_elements_with_retries(parent_element, by, value, retries=3):
    for _ in range(retries):
        try:
            return parent_element.find_elements(by, value)
        except StaleElementReferenceException:
            time.sleep(0.25)
    raise StaleElementReferenceException(f"Failed to find elements by {by}='{value}' after retries")


### MAIN ###

def get_gspread(keypath="key.json"):
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name(keypath, scope)
    client = gspread.authorize(creds)
    return client


def check_system():
    system = platform.system().lower()
    supported_systems = ["linux", "windows", "darwin"]
    if system not in supported_systems:
        print("System not supported")
        exit(1)
    return system


def get_drive():
    system = check_system()
    print(f"Downloading driver for {system}...")
    return ChromeDriverManager().install()


def clear_screen():
    system = check_system()
    if system == "linux" or system == "darwin":
        os.system('clear')
    elif system == "windows":
        os.system('cls')


def read_data_from_sheet(sheet_name):
    def append_index_to_sheet_data(sheet_data):
        for index, row in enumerate(sheet_data):
            row.append(index + 1 + 1)
        return sheet_data

    spread_sheet = gsp.open_by_url(os.getenv('SPREAD_SHEET_URL')).worksheet(sheet_name)
    data = spread_sheet.get_all_values()
    data = data[1:]
    data = append_index_to_sheet_data(data)
    return data


def read_file_with_encoding(file_path, encoding='utf-8'):
    try:
        with codecs.open(file_path, 'r', encoding=encoding) as file:
            content = json.load(file)
        return content
    except UnicodeDecodeError as e:
        print(f"Error decoding file: {e}")
        return None


def open_driver_with_retries(retries=3):
    chrome_options = Options()
    # chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_service = Service(executable_path=driver_path)

    for _ in range(retries):
        try:
            driver = webdriver.Chrome(service=chrome_service, options=chrome_options)
            driver.get(os.getenv('DEFAULT_URL'))
            return driver
        except WebDriverException:
            time.sleep(0.25)
    raise WebDriverException("Failed to open driver and navigate to URL after retries")


def do_payload(payload):
    pass


def do_payload_with_retries(payload, retries=3):
    for _ in range(retries):
        try:
            return do_payload(payload)
        except (StaleElementReferenceException, WebDriverException) as e:
            logging.error(f"Error in do_payload: {e}")
            time.sleep(1)
    raise Exception("Failed to execute do_payload after retries")


### LOGIC ###

def search_phase(driver, search_term):
    try:
        #click to element with id popup-close
        driver.find_element(By.ID, "popup-close").click()
        # Locate the search input field
        search_input = driver.find_element(By.NAME, "keyword")

        # Input a search term
        search_input.send_keys(search_term)

        # Simulate pressing Enter to search
        search_input.send_keys(Keys.ENTER)
        time.sleep(3)
    except Exception as e:
        print(f"Error during search phase: {e}")


# Phase 2: Select
def select_phase(driver):
    # find and click into a element with class name content__body__left__item__infor
    try:
        #wait for the page to load
        time.sleep(3)
        elements = driver.find_elements(By.CLASS_NAME, "content__body__left__item__infor")
        elements[0].click()
    except Exception as e:
        print(f"Error during select phase: {e}")

@print_function_name
def process(msmt):
    SEARCH_TERM = "IB2400338031"

    search_phase(driver, SEARCH_TERM)
    print("Search phase completed")
    select_phase(driver)
    print("Select phase completed")

    # Optionally, wait for results to load
    time.sleep(3)



@print_function_name
def multi_process():
    sheets = os.getenv('SHEET_NAMES').split(',')
    for sheet in sheets:
        try:
            process(sheet)
        except Exception as e:
            logging.error(f"Error in process: {e}")
            driver.refresh()


def write_data_to_sheet(data, line_number, sheet_name):
    pass


if __name__ == "__main__":
    # load_dotenv('settings.env')
    driver_path = get_drive()
    gsp = get_gspread(os.getenv('KEY_PATH'))

    driver = open_driver_with_retries(retries=int(os.getenv('RETRIES_TIME')))

    while (True):
        clear_screen()
        # multi_process()
        process("IB2400338031")
        time.sleep(int(os.getenv('REFRESH_TIME')))
