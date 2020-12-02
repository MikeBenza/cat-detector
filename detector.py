#!/usr/bin/env python
from __future__ import print_function
import argparse
import binascii
from collections import deque
from dataclasses import dataclass, field
import os
import sys
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

@dataclass
class Beacon:
    name: str
    max_rssi: int
    recovery_rssi: int
    token_description: str
    recent: deque = field(default_factory=lambda:deque([-1000], maxlen=MOVING_AVERAGE_SIZE), init=False)
    too_close: bool = field(default=False, init=False)

    def __post_init__(self):
        if self.recovery_rssi >= self.max_rssi:
            raise Exception("Recovery RSSI must be less than Max RSSI")

    @property
    def recent_moving_average(self):
        return sum(self.recent) / len(self.recent)
    def add_recent(self, value):
        self.recent.append(value)
        print(f"Appending {value} to {self.name}")
        if self.too_close and self.recent_moving_average <= self.recovery_rssi:
            self.too_close = False
        elif not self.too_close and self.recent_moving_average >= self.max_rssi:
            self.too_close = True

BEACONS = {
    '80:e4:da:71:1b:75': Beacon('Minidou', -68, -71, 'Flic button'),
    'fb:ca:63:b8:c7:2b': Beacon('Rigatoni', -80, -85, 'Fitbit')
}

class ScanPrint(btle.DefaultDelegate):

    def __init__(self):
        btle.DefaultDelegate.__init__(self)

    def handleDiscovery(self, dev, isNewDev, isNewData):
        if  dev.addr != '80:e4:da:71:1b:75':
            return

        if isNewDev:
            status = "new"
        elif isNewData:
            status = "update"
        else:
            status = "old"

        print ('    Device (%s): %s, %d dBm' %
               (status,
                   ANSI_WHITE + dev.addr + ANSI_OFF,
                   dev.rssi
               ))

def main():
    scanner = btle.Scanner(0)

    print (ANSI_RED + "Scanning for devices..." + ANSI_OFF)
    while True:
        devices = scanner.scan(1)
        devices = filter(lambda dev: dev.addr in BEACONS, devices)
        for device in devices:
            beacon = BEACONS[device.addr]
            beacon.add_recent(device.rssi)

        for beacon in BEACONS.values():
            if beacon.too_close:
                print(ANSI_RED + f"{beacon.name} is too close ({beacon.recent_moving_average})!" + ANSI_OFF)
            else:
                print(ANSI_GREEN + f"{beacon.name} is far enough away ({beacon.recent_moving_average})" + ANSI_OFF)



if __name__ == "__main__":
    main()
