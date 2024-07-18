import os
import time
import logging
from mss import mss
from opcua import Client, ua
from threading import Timer

# Setup logging
IMPORTANT = 25
logging.addLevelName(IMPORTANT, "IMPORTANT")
logging.Logger.important = lambda self, message, *args, **kws: self._log(IMPORTANT, message, args, **kws) if self.isEnabledFor(IMPORTANT) else None
logging.basicConfig(level=IMPORTANT, format='%(asctime)s - %(levelname)s - %(message)s')

# Environment variables
OPC_SERVER_URL = os.getenv('OPC_SERVER_URL', 'opc.tcp://10.15.160.149:49312')
TAG_NAME = os.getenv('TAG_NAME', 'ns=2;s=SODA_TEMPLATE.FILTRACAO.RASP_PASSO')
PRODUCT_TAG_NAME = os.getenv('PRODUCT_TAG_NAME', 'ns=2;s=BRASSAGEM.PLC1.WHIRLPOOL.SORBA.PROGNO')
EQUIPMENT = os.getenv('EQUIPMENT', 'DECANTADOR')
VALID_STEPS = os.getenv('VALID_STEPS', "1;0;1,2;0;1,3;0;1,4;0;1,5;0;1,6;0;1,12;30;2")
NUMBER_OF_PICTURES = int(os.getenv('NUMBER_OF_PICTURES', 10))
BASE_IMAGE_SAVE_PATH = './data'

def ensure_directory(path):
    if not os.path.exists(path):
        os.makedirs(path)

def take_screenshots(step, is_product_change=False):
    directory_suffix = "CIP" if is_product_change else step
    directory_path = os.path.join(BASE_IMAGE_SAVE_PATH, EQUIPMENT, directory_suffix)
    ensure_directory(directory_path)

    with mss() as sct:
        try:
            for i in range(NUMBER_OF_PICTURES):
                image_path = f'{directory_path}/{time.strftime("%d.%m.%Y_%H.%M.%S")}_{i}.png'
                # Use the first monitor directly, monitor index is 1
                sct.shot(mon=1, output=image_path)
                logging.getLogger().important(f"Screenshot successfully saved: {image_path}")
                time.sleep(1)
        except Exception as e:
            logging.getLogger().important(f"Failed to save screenshot: {e}")

def parse_valid_steps(config):
    steps = {}
    entries = config.split(',')
    for entry in entries:
        parts = entry.split(';')
        step = f"{float(parts[0]):.1f}"  # Format with one decimal place
        delay = float(parts[1])
        strategy = int(parts[2])
        steps[step] = {'delay': delay, 'strategy': strategy}
    return steps

valid_steps = parse_valid_steps(VALID_STEPS)
print("Valid steps loaded:", valid_steps)

class SubHandler(object):
    def __init__(self):
        self.last_value = None
        self.last_product_value = None
        self.active_timer = None
        self.last_strategy = None
        self.initial_step_change = False
        self.initial_product_change = False

    def handle_value_change(self, new_value):
        print("Handling value change for:", new_value)
        if self.active_timer:
            self.active_timer.cancel()
            self.active_timer = None
            logging.getLogger().important("Cancelled previous timer due to new valid step.")

        step_key = f"{float(new_value):.1f}"
        step_info = valid_steps.get(step_key)
        print("Step info:", step_info)

        if not self.initial_step_change:
            self.initial_step_change = True  # Mark the first change
            self.last_value = new_value
            self.last_strategy = step_info['strategy'] if step_info else None
            return  # Skip processing for the first change

        # Check if exiting from Strategy 2
        if self.last_strategy == 2:
            if not step_info or step_info['strategy'] != 2:
                take_screenshots(str(self.last_value))
            elif step_info['strategy'] == 2 and step_key != f"{float(self.last_value):.1f}":
                # Additional condition to handle transition between different Strategy 2 steps
                take_screenshots(str(self.last_value))

        if step_info:
            strategy = step_info['strategy']
            delay = step_info['delay']
            if strategy == 1:
                if delay > 0:
                    self.active_timer = Timer(delay, lambda: take_screenshots(step_key))
                    self.active_timer.start()
                else:
                    take_screenshots(step_key)
            elif strategy == 2:
                # Setup or placeholder for specific action when entering a Strategy 2 step
                # No action needed here if not entering from another Strategy 2 step
                pass
            elif strategy == 3:
                self.start_continuous_capture(step_key, delay)

        self.last_value = new_value
        self.last_strategy = step_info['strategy'] if step_info else None

    def start_continuous_capture(self, step, interval):
        def capture():
            print(self.last_value)
            print(step)
            #if self.last_value == step:  # Continue capturing if the step hasn't changed
            take_screenshots(step)
            self.active_timer = Timer(interval, capture)
            self.active_timer.start()

        capture()

    def handle_product_change(self, product_value):
        if not self.initial_product_change:  # Check if it's the first product change
            self.initial_product_change = True
            self.last_product_value = product_value  # Set initial product value
            return  # Skip further processing until the next product change

        # Now handle changes only if last_product_value is not None
        if self.last_product_value is not None and product_value >= 0 and self.last_product_value < 0:
            take_screenshots("any_value", is_product_change=True)

        self.last_product_value = product_value  # Update last_product_value for next change

    def datachange_notification(self, node, val, data):
        new_value = round(float(val), 1)
        if str(node) == PRODUCT_TAG_NAME:
            self.handle_product_change(new_value)
        else:
            logging.getLogger().important(f"Data change on {node}: New value = {new_value}")
            self.handle_value_change(new_value)

def connect_to_opcua():
    while True:

        client = Client(OPC_SERVER_URL)
        try:
            client.connect()
            logging.getLogger().important(f"Connected to {OPC_SERVER_URL}")
            tag_node = client.get_node(TAG_NAME)
            product_node = client.get_node(PRODUCT_TAG_NAME)
            handler = SubHandler()
            sub = client.create_subscription(500, handler)
            sub.subscribe_data_change(tag_node)
            sub.subscribe_data_change(product_node)
            logging.getLogger().important("Subscription created, waiting for events...")
            
        # Infinite loop to keep script running
            while True:
                try:
                    # Test the connection by reading a value
                    tag_node.get_value()
                    time.sleep(1)
                except ua.UaStatusCodeError:
                    logging.error("Lost connection to OPA UA server. Trying to reconect...")
                    break
        except Exception as e:
            logging.exception(f"An error occurred")
            time.sleep(15) #wait for 15 seconds before trying to reconect
        finally:
            try:
                client.disconnect()
                logging.getLogger().important("Client disconnected.")
            except:
                pass

def main():
    connect_to_opcua()
    
if __name__ == '__main__':
    main()