#!/usr/bin/env python
from __future__ import print_function
import argparse
import binascii
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
    scanner = btle.Scanner(0).withDelegate(ScanPrint())

    print (ANSI_RED + "Scanning for devices..." + ANSI_OFF)
    while True:
        devices = scanner.scan(1)

if __name__ == "__main__":
    main()
