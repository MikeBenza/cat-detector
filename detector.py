import argparse
import json
import os.path
import statistics
import time
from collections import deque
from dataclasses import dataclass, field

import requests

try:
    import RPi.GPIO as GPIO
except ModuleNotFoundError:
    print("Couldn't find RPi.GPIO.  Pulses will not work.")
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

ANSI_CSI = "\033["
ANSI_RED = ANSI_CSI + '31m'
ANSI_GREEN = ANSI_CSI + '32m'
ANSI_YELLOW = ANSI_CSI + '33m'
ANSI_CYAN = ANSI_CSI + '36m'
ANSI_WHITE = ANSI_CSI + '37m'
ANSI_OFF = ANSI_CSI + '0m'

MOVING_AVERAGE_SIZE = 3
MISSING_FACTOR = 3
RELAY_1_GPIO = 4
PULSE_TIME = 0.250
SCAN_TIME = 1.25

BEACONS = {}


class BluetoothScanner:
    def __init__(self, id):
        from bluepy import btle
        self.scanner = btle.Scanner(id)

    def scan(self, length):
        return self.scanner.scan(length)


class MockBluetoothScanner:
    @dataclass
    class Device:
        addr: str
        rssi: int

    def __init__(self, beacons):
        self.devices = [MockBluetoothScanner.Device(addr, beacons[addr].max_rssi) for addr in beacons]
        self.find_index = -1

    def scan(self, length):
        time.sleep(length)
        if 0 <= self.find_index < len(self.devices):
            return [self.devices[self.find_index]]
        return []


@dataclass
class Beacon:
    name: str
    max_rssi: int
    recovery_rssi: int
    token_description: str
    recent: deque = field(default_factory=lambda: deque([], maxlen=MOVING_AVERAGE_SIZE), init=False)
    too_close: bool = field(default=False, init=False)
    missing: int = MISSING_FACTOR

    def __post_init__(self):
        if self.recovery_rssi >= self.max_rssi:
            raise Exception("Recovery RSSI must be less than Max RSSI")

    @property
    def recent_moving_average(self):
        if len(self.recent):
            return sum(self.recent) / len(self.recent)
        else:
            return None

    @property
    def stdev(self):
        if len(self.recent) >= 2:
            return statistics.stdev(self.recent)
        return None

    @property
    def is_too_close(self):
        if not self.recent:
            return False
        if self.too_close and self.recent_moving_average <= self.recovery_rssi:
            self.too_close = False
        elif not self.too_close and self.recent_moving_average >= self.max_rssi:
            self.too_close = True
        return self.too_close

    def add_recent(self, value):
        self.recent.append(value)
        print(f"Appending {value} to {self.name}.  RMA: {int(self.recent_moving_average)}. "
              f"{self.max_rssi} — {self.recovery_rssi}")

    def mark_missing(self):
        self.missing -= 1
        if self.missing == 0:
            self.missing = MISSING_FACTOR
            if self.recent:
                self.recent.popleft()


def alert(log):
    requests.post('http://cat-air-sprayer.local/pulse', params={'t': '500'})
    log.write(json.dumps({'event_type': 'alert', 'time': time.time(), 'alert_filename': alert.filename}) + "\n")


def setup_gpio(pin):
    try:
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(pin, GPIO.OUT)
    except NameError:
        print("Cannot set GPIO mode")


def pulse(t):
    try:
        GPIO.output(RELAY_1_GPIO, GPIO.HIGH)
        time.sleep(t)
        GPIO.output(RELAY_1_GPIO, GPIO.LOW)
    except NameError:
        print(f"Mock pulsing for {t} seconds")


def main(scanner):
    print(ANSI_RED + "Scanning for devices..." + ANSI_OFF)
    with open('scan.log', 'a+') as log:
        while True:
            devices = scanner.scan(SCAN_TIME)
            devices = filter(lambda dev: dev.addr in BEACONS, devices)
            beacons_missing = set(BEACONS.keys())
            for device in devices:
                beacon = BEACONS[device.addr]
                beacon.add_recent(device.rssi)
                log.write(json.dumps(
                    {'event_type': 'beacon_detection', 'time': time.time(), 'beacon_name': beacon.name,
                     'rssi': device.rssi}) + "\n")
                log.flush()
                beacons_missing.remove(device.addr)

            for mac in beacons_missing:
                beacon = BEACONS[mac]
                beacon.mark_missing()

            for beacon in BEACONS.values():
                if beacon.is_too_close:
                    print(ANSI_RED + f"{beacon.name} is too close ({beacon.recent_moving_average} "
                                     f"({beacon.stdev}))!" + ANSI_OFF)
                    alert(log)
                else:
                    print(ANSI_GREEN + f"{beacon.name} is far enough away ({beacon.recent_moving_average} "
                                       f"({beacon.stdev}))" + ANSI_OFF)


def get_argparser():
    parser = argparse.ArgumentParser('Cat detector')
    parser.add_argument('mode', choices=['ble', 'mock'])
    parser.add_argument('--config', '-c', required=True, type=str)
    return parser


def load_config(path):
    global PULSE_TIME, MISSING_FACTOR, MOVING_AVERAGE_SIZE, SCAN_TIME
    with open(path, 'r') as f:
        # TODO: Validation
        config = json.load(f)
        new_beacons = {b['addr']: Beacon(b['name'], b['max_rssi'], b['recovery_rssi'], b['description'])
                       for b in config['beacons']}
        BEACONS.clear()
        BEACONS.update(new_beacons)
        PULSE_TIME = float(config.get('pulse_time') or PULSE_TIME)
        MISSING_FACTOR = int(config.get('missing_factor') or MISSING_FACTOR)
        MOVING_AVERAGE_SIZE = int(config.get('moving_average_size') or MOVING_AVERAGE_SIZE)
        SCAN_TIME = float(config.get('scan_time') or 1.25)

        print(f"Config loaded.\n{BEACONS=}\n{PULSE_TIME=}\n{MISSING_FACTOR=}\n{MOVING_AVERAGE_SIZE=}\n{SCAN_TIME=}")


def add_watcher(fp):
    abspath = os.path.abspath(fp)

    class Watcher(FileSystemEventHandler):
        def on_moved(self, event):
            if os.path.abspath(event.src_path) == abspath:
                print(f"File change: {event}")
                load_config(abspath)

    handler = Watcher()
    observer = Observer()
    observer.schedule(handler, os.path.dirname(abspath), recursive=False)
    observer.start()


if __name__ == "__main__":
    parser = get_argparser()
    args = parser.parse_args()
    if args.mode == 'ble':
        scanner = BluetoothScanner(0)
        setup_gpio(RELAY_1_GPIO)
    elif args.mode == 'mock':
        scanner = MockBluetoothScanner(BEACONS)
    else:
        raise Exception(f"Unexpected mode: {args.mode}")
    load_config(args.config)
    add_watcher(args.config)
    main(scanner)
