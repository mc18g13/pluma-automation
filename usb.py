#!/usr/bin/env python3

import sys
import os
import time
from pprint import pprint as pp
import subprocess as sp
import pyudev
import board

bind_path = "/sys/bus/usb/drivers/usb/bind"
unbind_path = "/sys/bus/usb/drivers/usb/unbind"


class NoPartitions(Exception):
    pass


class NoDisks(Exception):
    pass


class NoDevice(Exception):
    pass


class USB():
    def __init__(self, device):
        self.puctx = pyudev.Context()
        self.device = device
        self._dev = self._get_dev()

    def __repr__(self):
        return "\n[USB: device={}]".format(self.device)

    def _get_dev(self):
        #print("Looking for device {}".format(self.device))
        try:
            for _ in range(20):
                d = pyudev.Devices.from_path(
                    self.puctx, '/bus/usb/devices/{}'.format(self.device))
                if d is not None:
                    break
                time.sleep(1)
        except:
            raise NoDevice("No device for [{}]".format(self.device))
        return d

    def unbind(self):
        try:
            #print("unbinding {}".format( self.device ) )
            device = self.get_device()
            if device is None:
                return
            d = os.path.basename(device['DEVPATH'])
            unbind_fd = open(unbind_path, 'w')
            unbind_fd.write(d)
            unbind_fd.close()
        except:
            #print("No device to unbind, lets carry on")
            pass
        time.sleep(1)

    def bind(self):
        #print("binding {}".format( self.device )
        d = os.path.basename(self._dev['DEVPATH'])
        bind_fd = open(bind_path, 'w')
        bind_fd.write(d)
        bind_fd.close()
        time.sleep(1)

    def rebind(self):
        self.unbind(self.device)
        self.bind(self.device)

    def get_devnode(self, subsys, devtype=None, dev_id=None):
        for _ in range(20):
            if devtype is not None:
                devices = self.puctx.list_devices(
                    subsystem=subsys, DEVTYPE=devtype, parent=self._dev)
            else:
                devices = self.puctx.list_devices(
                    subsystem=subsys, parent=self._dev)
            for m in devices:
                if dev_id is not None:
                    if m.get('ID_VENDOR') is None:
                        continue
                    if m['ID_VENDOR'] == dev_id:
                        return m.device_node
                else:
                    return m.device_node
            time.sleep(1)
        raise IOError('No {} {} devices with id {}'.format(
            subsys, devtype, dev_id))

    # Return the device node and the sysname for the usb parent for use with the bind/unbind
    def get_block(self):
        #print("Searching for block devicces on [{}]".format( self.device ))
        for _ in range(20):
            blks = self.puctx.list_devices(
                subsystem='block',  DEVTYPE='disk', parent=self._dev)
            for m in blks:
                if int(m.attributes.get('size')) == 0:
                    continue
                #print("Block device {} has size {:4.2f}MB".format(
                #    m.device_node,
                #    int(m.attributes.get('size')) / 1024 / 1024 ))
                usbp = m.find_parent('usb', device_type='self.device')
                #print(" Parent is: {} , {}".format( usbp.sys_name, usbp.device_type ))
                return(m.device_node, usbp.sys_name)
            time.sleep(2)
        raise NoDisks('No block devices on {}'.format(self.device))

    # Get first partition name for block device
    def get_part(self):
        #print("Searching for block devicces on [{}]".format( self.device ))
        for _ in range(5):
            blks = self.puctx.list_devices(
                subsystem='block',  DEVTYPE='partition', parent=self._dev)
            for m in blks:
                if int(m.attributes.get('size')) == 0: continue
                #print("Block device {} has size {:4.2f}MB".format(
                #    m.device_node,
                #    int(m.attributes.get('size')) / 1024 / 1024 ))
                #usbp = m.find_parent('usb', device_type='self.device')
                #print(" Parent is: {} , {}".format( usbp.sys_name, usbp.device_type ))
                return m.device_node
            time.sleep(2)
        raise NoPartitions('No partitions on {}'.format(self.device))

    def show_ancestry(self):
        d = self._dev

        while d.parent:
            p = d.parent
            print(dir(p))
            print(p.driver, p.subsystem, p.sys_name, p.device_path, p.sys_path)
            sp.run(['ls', "{}/driver".format(p.sys_path)])
            d = p

    def rebind_host(self):
        d = self._dev

        # Keep going until we find no more parents
        while d.parent:
            d = d.parent

        driver_path = "{}/driver".format(d.sys_path)
        driver_path = os.path.realpath(driver_path)

        print("WARN: Rebinding HOST {} at {}".format(d.sys_name, driver_path))

        sp.run(['sudo', 'chmod', 'a+w', driver_path + "/unbind"])
        sp.run(['sudo', 'chmod', 'a+w', driver_path + "/bind"])

        with open("{}/unbind".format(driver_path), 'w') as f:
            f.write(d.sys_name)

        time.sleep(2)
        with open("{}/bind".format(driver_path), 'w') as f:
            f.write(d.sys_name)

    def show_info(self):
        for m in self.puctx.list_devices(
                subsystem='block', DEVTYPE='disk', parent=self._dev):
            if int(m.attributes.get('size')) == 0:
                continue
            print("Block device {} has size {:4.2f}MB".format(
                m.device_node,
                int(m.attributes.get('size')) / (1024 * 1024)))
            usbp = m.find_parent('usb', device_type='device')
            if usbp is not None:
                print("Parent is: {}, {}".format(
                    usbp.sys_name, usbp.device_type))
        for m in self.puctx.list_devices(subsystem='tty', parent=self._dev):
            print(m.device_node, m['ID_VENDOR'])

#find_block( device )
#find_serial( device )
