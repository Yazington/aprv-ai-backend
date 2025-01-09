import pyautogui
import time

print("Move your mouse to the Cline input field and wait 5 seconds...")
time.sleep(5)
cline_input = pyautogui.position()
print(f"Cline input coordinates: {cline_input}")

print("Move your mouse to the Start New Task button and wait 5 seconds...")
time.sleep(5)
start_button = pyautogui.position()
print(f"Start New Task coordinates: {start_button}")

print("Move your mouse to the area where 'Success' appears and wait 5 seconds...")
time.sleep(5)
success_area = pyautogui.position()
print(f"Success area top-left: {success_area}")
print("Move your mouse to the bottom-right of the success area and wait 5 seconds...")
time.sleep(5)
success_area2 = pyautogui.position()
print(f"Success area coordinates: ({success_area.x}, {success_area.y}, {success_area2.x}, {success_area2.y})")
