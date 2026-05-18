import pyautogui
import time
# Wait for 5 seconds before starting
time.sleep(5)
# Move the mouse to x=100, y=100 over 2 seconds
pyautogui.moveTo(100, 100, duration=2)
# Move mouse relative to its current position
pyautogui.moveRel(200, 0, duration=2)
