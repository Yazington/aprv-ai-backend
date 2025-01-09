import pyautogui
import time
from PIL import ImageGrab
import pytesseract

# Configuration
CHECK_INTERVAL = 1  # seconds between checks
TEXT_SEARCH_REGION = (86, 984, 621, 1837)  # area to search for "Success"
CLINE_INPUT_POS = (273, 2010)  # Cline input field coordinates
START_NEW_TASK_TEXT_POSTION = (105, 1901, 620, 1953)  # Start New Task text position
START_TASK_BUTTON_POS = (336, 1927)  # Start New Task button coordinates


def check_for_success():
    """Check if 'Success' appears in the defined region"""
    screenshot = ImageGrab.grab(bbox=TEXT_SEARCH_REGION)
    text = pytesseract.image_to_string(screenshot)
    return "Success" in text or "Task Completed" in text


def automate_cline():
    while True:
        # Check a1.txt
        pyautogui.click(CLINE_INPUT_POS)
        pyautogui.write("Check a1.txt", interval=0.1)
        pyautogui.press("enter")

        # Wait for Success
        while not check_for_success():
            time.sleep(CHECK_INTERVAL)

        # Check for "Start New Task" before clicking
        while True:
            screenshot = ImageGrab.grab(bbox=START_NEW_TASK_TEXT_POSTION)
            text = pytesseract.image_to_string(screenshot)
            if "Start New Task" in text:
                pyautogui.click(START_TASK_BUTTON_POS)
                time.sleep(1)
                break
            time.sleep(CHECK_INTERVAL)

        # Check a2.txt
        pyautogui.click(CLINE_INPUT_POS)
        pyautogui.write("Check a2.txt", interval=0.1)
        pyautogui.press("enter")

        # Wait for Success
        while not check_for_success():
            time.sleep(CHECK_INTERVAL)

        # Check for "Start New Task" before clicking
        while True:
            screenshot = ImageGrab.grab(bbox=START_NEW_TASK_TEXT_POSTION)
            text = pytesseract.image_to_string(screenshot)
            if "Start New Task" in text:
                pyautogui.click(START_TASK_BUTTON_POS)
                time.sleep(1)
                break
            time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    # Add safety feature - move mouse to corner to abort
    pyautogui.FAILSAFE = True
    automate_cline()
