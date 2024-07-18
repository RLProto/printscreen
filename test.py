import os
from mss import mss
import time

def ensure_directory(path):
    """ Ensure directory exists, if not, create it. """
    if not os.path.exists(path):
        os.makedirs(path)

def take_screenshot():
    """ Take a screenshot and save it to the specified path. """
    directory_path = './screenshots'
    ensure_directory(directory_path)  # Make sure the directory exists
    
    with mss() as sct:
        timestamp = time.strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"{directory_path}/screenshot_{timestamp}.png"
        # Use the first monitor, monitor index directly is 1 (second element, as index 0 is for all monitors combined)
        sct.shot(mon=1, output=filename)
        print(f"Screenshot successfully saved: {filename}")

if __name__ == '__main__':
    take_screenshot()
