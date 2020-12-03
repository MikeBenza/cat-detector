import binascii
from collections import deque
from dataclasses import dataclass, field
import json
import logging
import statistics
import time
from bluepy import btle

ANSI_CSI = "\033["
ANSI_RED = ANSI_CSI + '31m'
ANSI_GREEN = ANSI_CSI + '32m'
ANSI_YELLOW = ANSI_CSI + '33m'
ANSI_CYAN = ANSI_CSI + '36m'
ANSI_WHITE = ANSI_CSI + '37m'
ANSI_OFF = ANSI_CSI + '0m'

MOVING_AVERAGE_SIZE = 5
MISSING_FACTOR = 3

@dataclass
class Beacon:
    name: str
    max_rssi: int
    recovery_rssi: int
    token_description: str
    recent: deque = field(default_factory=lambda:deque([], maxlen=MOVING_AVERAGE_SIZE), init=False)
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
        print(f"Appending {value} to {self.name}")
    def mark_missing(self):
        self.missing -= 1
        if self.missing == 0:
            self.missing = MISSING_FACTOR
            if self.recent:
                self.recent.popleft()

BEACONS = {
    '80:e4:da:71:1b:75': Beacon('Minidou', -65, -69, 'Flic button'),
#    'fb:ca:63:b8:c7:2b': Beacon('Rigatoni', -72, -74, 'Fitbit')
}

def main():
    scanner = btle.Scanner(0)

    print (ANSI_RED + "Scanning for devices..." + ANSI_OFF)
    with open('scan.log', 'w+') as log:
        while True:
            devices = scanner.scan(1.25)
            devices = filter(lambda dev: dev.addr in BEACONS, devices)
            beacons_missing = set(BEACONS.keys())
            for device in devices:
                beacon = BEACONS[device.addr]
                beacon.add_recent(device.rssi)
                log.write(json.dumps({'event_type': 'beacon_detection', 'time': time.time(), 'beacon_name': beacon.name, 'rssi': device.rssi}) + "\n")
                beacons_missing.remove(device.addr)

            for mac in beacons_missing:
                beacon = BEACONS[mac]
                beacon.mark_missing()

            for beacon in BEACONS.values():
                if beacon.is_too_close:
                    print(ANSI_RED + f"{beacon.name} is too close ({beacon.recent_moving_average} ({beacon.stdev}))!" + ANSI_OFF)
                else:
                    print(ANSI_GREEN + f"{beacon.name} is far enough away ({beacon.recent_moving_average} ({beacon.stdev}))" + ANSI_OFF)



if __name__ == "__main__":
    main()
