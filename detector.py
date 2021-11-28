import binascii
from collections import deque
from dataclasses import dataclass, field
import json
import logging
import statistics
import time
import pygame
import random
import requests
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

@dataclass
class Alert:
    filename: str
    volume: float
    max_time: int = 1000
    sound: pygame.mixer.Sound = field(default=None, init=False)

    def play(self):
        #if not self.sound:
        #    self.sound = pygame.mixer.Sound(self.filename)
        #    self.sound.set_volume(self.volume)
        #self.sound.play(maxtime=self.max_time)
        pass

BEACONS = {
    '80:e4:da:71:1b:75': Beacon('Rigatoni', -62, -66, 'Flic button'),
    'e9:dc:3c:66:5d:8b': Beacon('Minidou', -60, -64, 'Beacon 2'),
#    'f8:7e:79:c9:06:d7': Beacon('Henry', -49, -53, 'Beacon 1')
}

ALERTS = [
    Alert('sounds/breaking-glass.wav', 1, 1000),
    Alert('sounds/clap.wav', 1, 1500),
    Alert('sounds/gong.wav', 1, 2000),
    Alert('sounds/hiss.wav', 1, 3000),
    Alert('sounds/hf-1.wav', 1, 2000),
    Alert('sounds/monster.wav', 1, 1000),
    Alert('sounds/chirp-tone.wav', 3000),
]

def alert(log):
    alert = random.choice(ALERTS)
    requests.post('http://cat-air-sprayer.local/pulse', params={'t': '500'})
    print(ANSI_CYAN + f"Playing {alert.filename}" + ANSI_OFF)
    log.write(json.dumps({'event_type': 'alert', 'time': time.time(), 'alert_filename': alert.filename}) + "\n")
    alert.play()

def main():
    scanner = btle.Scanner(0)

    print (ANSI_RED + "Scanning for devices..." + ANSI_OFF)
    with open('scan.log', 'a+') as log:
        while True:
            devices = scanner.scan(1.25)
            devices = filter(lambda dev: dev.addr in BEACONS, devices)
            beacons_missing = set(BEACONS.keys())
            for device in devices:
                beacon = BEACONS[device.addr]
                beacon.add_recent(device.rssi)
                log.write(json.dumps({'event_type': 'beacon_detection', 'time': time.time(), 'beacon_name': beacon.name, 'rssi': device.rssi}) + "\n")
                log.flush()
                beacons_missing.remove(device.addr)

            for mac in beacons_missing:
                beacon = BEACONS[mac]
                beacon.mark_missing()

            for beacon in BEACONS.values():
                if beacon.is_too_close:
                    print(ANSI_RED + f"{beacon.name} is too close ({beacon.recent_moving_average} ({beacon.stdev}))!" + ANSI_OFF)
                    alert(log)
                else:
                    print(ANSI_GREEN + f"{beacon.name} is far enough away ({beacon.recent_moving_average} ({beacon.stdev}))" + ANSI_OFF)



if __name__ == "__main__":
    pygame.init()
    main()
