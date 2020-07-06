# -*- coding: utf-8 -*-

# Octowire Framework
# Copyright (c) ImmunIT - Jordan Ovrè / Paul Duncan
# License: Apache 2.0
# Paul Duncan / Eresse <pduncan@immunit.ch>
# Jordan Ovrè / Ghecko <jovre@immunit.ch>

import shutil
import time

from beautifultable import BeautifulTable, ALIGN_LEFT

from octowire_framework.module.AModule import AModule
from octowire.gpio import GPIO
from octowire.spi import SPI
from owfmodules.avrisp.device_id import DeviceID


class ReadFuses(AModule):
    def __init__(self, owf_config):
        super(ReadFuses, self).__init__(owf_config)
        self.meta.update({
            'name': 'AVR read fuses and lock bits',
            'version': '1.0.0',
            'description': 'Read the fuses and lock bits of AVR microcontrollers',
            'author': 'Jordan Ovrè / Ghecko <jovre@immunit.ch>, Paul Duncan / Eresse <pduncan@immunit.ch>'
        })
        self.options = {
            "spi_bus": {"Value": "", "Required": True, "Type": "int",
                        "Description": "SPI bus (0=SPI0 or 1=SPI1)", "Default": 0},
            "reset_line": {"Value": "", "Required": True, "Type": "int",
                           "Description": "GPIO used as the Reset line", "Default": 0},
            "spi_baudrate": {"Value": "", "Required": True, "Type": "int",
                             "Description": "SPI frequency (1000000 = 1MHz) maximum = 50MHz", "Default": 1000000},
        }
        self.dependencies.append("owfmodules.avrisp.device_id>=1.0.0")

    @staticmethod
    def count_trailing_zero(x):
        count = 0
        while (x & 1) == 0:
            x = x >> 1
            count += 1
        return count

    @staticmethod
    def print_table(data, headers):
        t_width, _ = shutil.get_terminal_size()
        if t_width >= 95:
            table = BeautifulTable(max_width=95, default_alignment=ALIGN_LEFT)
        else:
            table = BeautifulTable(max_width=t_width, default_alignment=ALIGN_LEFT)

        table.column_headers = headers

        # Convert dictionary data to list
        for fuse, details in data.items():
            row = ["{}\n({})".format(fuse, details["descr"]), details["value_descr"], details["value"], details["mask"]]
            table.append_row(row)

        # change table style
        table.set_style(BeautifulTable.STYLE_BOX_ROUNDED)
        table.header_separator_char = '═'
        table.intersect_header_left = '╞'
        table.intersect_header_mid = '╪'
        table.intersect_header_right = '╡'

        # Print table
        print("{}\n".format(table))

    def get_device_id(self, spi_bus, reset_line, spi_baudrate):
        device_id_module = DeviceID(owf_config=self.config)
        # Set DeviceID module options
        device_id_module.options["spi_bus"]["Value"] = spi_bus
        device_id_module.options["reset_line"]["Value"] = reset_line
        device_id_module.options["spi_baudrate"]["Value"] = spi_baudrate
        device_id_module.owf_serial = self.owf_serial
        device_id = device_id_module.run(return_value=True)
        return device_id

    def parse_fuse(self, fuse_dict, fuse_value):
        output = {}
        for fuse_name, values in fuse_dict.items():
            mask = int(fuse_dict[fuse_name]["mask"], 16)
            result = fuse_value & mask
            if len(fuse_dict[fuse_name]["values"]) > 0:
                trailing_zero = self.count_trailing_zero(mask)
                for name, descr in fuse_dict[fuse_name]["values"].items():
                    if int(descr["value"], 16) == result >> trailing_zero:
                        output[fuse_name] = {"descr": fuse_dict[fuse_name]["caption"], "value_descr": descr["caption"],
                                             "value": descr["value"], "mask": fuse_dict[fuse_name]["mask"]}
                        break
                else:
                    self.logger.handle("Invalid value for {} ==> got: {}".format(
                        fuse_name, hex(result >> trailing_zero)), self.logger.ERROR)
            else:
                if result & mask == mask:
                    output[fuse_name] = {"descr": fuse_dict[fuse_name]["caption"], "value_descr": "Unprogrammed",
                                         "value": 1, "mask": fuse_dict[fuse_name]["mask"]}
                else:
                    output[fuse_name] = {"descr": fuse_dict[fuse_name]["caption"], "value_descr": "Programmed",
                                         "value": 0, "mask": fuse_dict[fuse_name]["mask"]}
        return output

    def read_fuses(self, spi_interface, device):
        read_low_fuse = b'\x50\x00\x00'
        read_high_fuse = b'\x58\x08\x00'
        read_extended_fuse = b'\x50\x08\x00'

        if len(device["fuse_low"]) > 0:
            spi_interface.transmit(read_low_fuse)
            low_fuse = spi_interface.receive(1)[0]
            self.logger.handle("Low fuse settings (Byte value: {})".format(hex(low_fuse)), self.logger.RESULT)
            self.print_table(self.parse_fuse(device["fuse_low"], low_fuse), ["Fuse name", "Status", "Value", "Mask"])

        if len(device["fuse_high"]) > 0:
            spi_interface.transmit(read_high_fuse)
            high_fuse = spi_interface.receive(1)[0]
            self.logger.handle("High fuse settings (Byte value: {})".format(hex(high_fuse)), self.logger.RESULT)
            self.print_table(self.parse_fuse(device["fuse_high"], high_fuse), ["Fuse name", "Status", "Value", "Mask"])

        if len(device["fuse_extended"]) > 0:
            spi_interface.transmit(read_extended_fuse)
            extended_fuse = spi_interface.receive(1)[0]
            self.logger.handle("Extended fuse settings (Byte value: {})".format(hex(extended_fuse)), self.logger.RESULT)
            self.print_table(self.parse_fuse(device["fuse_extended"], extended_fuse),
                             ["Fuse name", "Status", "Value", "Mask"])

    def read_lockbits(self, spi_interface, device):
        read_lockbits = b'\x58\x00\x00'

        if len(device["lock_bits"]) > 0:
            spi_interface.transmit(read_lockbits)
            lock_bits = spi_interface.receive(1)[0]
            self.logger.handle("Lock bits settings (Byte value: {})".format(hex(lock_bits)), self.logger.RESULT)
            self.print_table(self.parse_fuse(device["lock_bits"], lock_bits),
                             ["Lock bit name", "Status", "Value", "Mask"])

    def process(self):
        enable_mem_access_cmd = b'\xac\x53\x00\x00'
        spi_bus = self.options["spi_bus"]["Value"]
        reset_line = self.options["reset_line"]["Value"]
        spi_baudrate = self.options["spi_baudrate"]["Value"]

        device = self.get_device_id(spi_bus, reset_line, spi_baudrate)

        if device is not None:
            spi_interface = SPI(serial_instance=self.owf_serial, bus_id=spi_bus)
            reset = GPIO(serial_instance=self.owf_serial, gpio_pin=reset_line)
            reset.direction = GPIO.OUTPUT

            # Reset is active-low
            reset.status = 1

            # Configure SPI with default phase and polarity
            spi_interface.configure(baudrate=spi_baudrate)
            self.logger.handle("Enable Memory Access...", self.logger.INFO)

            # Drive reset low
            reset.status = 0

            # Enable Memory Access
            spi_interface.transmit(enable_mem_access_cmd)
            time.sleep(0.5)

            # Read fuses
            self.read_fuses(spi_interface, device)

            # Read lock bits
            self.read_lockbits(spi_interface, device)

            # Drive reset high
            reset.status = 1

    def run(self):
        """
        Main function.
        Get fuses and lock bits.
        :return: Nothing.
        """
        # If detect_octowire is True then detect and connect to the Octowire hardware. Else, connect to the Octowire
        # using the parameters that were configured. This sets the self.owf_serial variable if the hardware is found.
        self.connect()
        if not self.owf_serial:
            return
        try:
            self.process()
        except ValueError as err:
            self.logger.handle(err, self.logger.ERROR)
        except Exception as err:
            self.logger.handle("{}: {}".format(type(err).__name__, err), self.logger.ERROR)
