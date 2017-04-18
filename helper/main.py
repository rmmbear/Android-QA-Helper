#   Android QA Helper - helping you test Android apps!
#   Copyright (C) 2017  Maciej Mysliwczyk 'rmmbear'
#
#   This program is free software: you can redistribute it and/or modify
#   it under the terms of the GNU General Public License as published by
#   the Free Software Foundation, either version 3 of the License, or
#   (at your option) any later version.
#
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.
#
#   You should have received a copy of the GNU General Public License
#   along with this program. If not, see <http://www.gnu.org/licenses/>.

"""Program for performing common Android operations.
Current functionality includes:
    - Installing apps
    - Pulling dalvik vm stack traces
    - Recording device's screen (Android 4.4+)
    - Cleaning device's storage with customizable cleaning config
"""


import re
import sys
import subprocess
from pathlib import Path
from time import strftime, sleep
from collections import OrderedDict

import helper as helper_

DEVICES = {}

ABI_TO_ARCH = helper_.ABI_TO_ARCH
CLEANER_CONFIG = helper_.CLEANER_CONFIG
COMPRESSION_TYPES = helper_.COMPRESSION_TYPES
ADB = helper_.ADB
AAPT = helper_.AAPT


def adb_execute(*args, return_output=False, check_server=True, as_list=True,
                stdout_=sys.stdout):
    """Execute an ADB command, and return -- or don't -- its result.

    If check_server is true, function will first make sure that an ADB
    server is available before executing the command.
    """
    try:
        if check_server:
            subprocess.run([ADB, "start-server"], stdout=subprocess.PIPE)

        if return_output:
            cmd_out = subprocess.run(
                (ADB,) + args, stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT).stdout.decode("utf-8", "replace")

            if as_list:
                return cmd_out.strip().splitlines()

            return cmd_out.strip()

        if stdout_ != sys.__stdout__:
            cmd_out = subprocess.Popen(
                (ADB,) + args, stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT).stdout.decode("utf-8", "replace")

            last_line = ''
            for line in cmd_out.splitlines():
                if line != last_line:
                    stdout_.write(line)
                    last_line = line
        else:
            subprocess.run((ADB,) + args)

    except FileNotFoundError:
        stdout_.write("".join(["Helper expected ADB to be located in '", ADB,
                               "' but could not find it.\n"]))
        sys.exit("Please make sure the ADB binary is in the specified path.")
    except (PermissionError, OSError):
        stdout_.write(
            " ".join(["Helper could not launch ADB. Please make sure the",
                      "following path is correct and points to an actual ADB",
                      "binary:", ADB, "To fix this issue you may need to edit",
                      "or delete the helper config file, located at:",
                      helper_.CONFIG]))
        sys.exit()


def aapt_execute(*args, return_output=False, as_list=True, stdout_=sys.stdout):
    """Execute an AAPT command, and return -- or don't -- its result."""
    try:
        if return_output:
            cmd_out = subprocess.run(
                (AAPT,) + args, stdout=subprocess.PIPE, encoding="utf-8",
                stderr=subprocess.STDOUT, universal_newlines=True).stdout

            if as_list:
                return cmd_out.strip().splitlines()

            return cmd_out.strip()

        if stdout_ != sys.__stdout__:
            cmd_out = subprocess.Popen(
                (AAPT,) + args, stdout=subprocess.PIPE, encoding="utf-8",
                stderr=subprocess.STDOUT, universal_newlines=True)

            last_line = ''
            for line in cmd_out.stdout:
                if line != last_line:
                    stdout_.write(line)
                    last_line = line
        else:
            subprocess.run((AAPT,) + args)
    except FileNotFoundError:
        stdout_.write("".join(["Helper expected AAPT to be located in '", AAPT,
                               "' but could not find it.\n"]))
        sys.exit("Please make sure the AAPT binary is in the specified path.")
    except (PermissionError, OSError):
        stdout_.write(" ".join(["Helper could not launch AAPT. Please make",
                                "sure the following path is correct and",
                                "points to an actual AAPT binary:", AAPT,
                                "To fix this issue you may need to edit or",
                                "delete the helper config file, located at:",
                                helper_.CONFIG]))
        sys.exit()


def _get_devices(stdout_=sys.stdout):
    """Return a list of tuples with serial number and status, for all
    connected devices.
    """
    device_list = []

    device_specs = adb_execute("devices", return_output=True)
    # Check for unexpected output
    # if such is detected, print it and return an empty list
    if device_specs:
        first_line = device_specs.pop(0)
        if first_line != "List of devices attached":
            stdout_.write(first_line + "\n")
            if device_specs:
                stdout_.write("\n".join(device_specs))
                return []

    for device_line in device_specs:
        device = device_line.split()
        if len(device) != 2:
            stdout_.write(device_line)
            continue
        device_serial = device[0]
        device_status = device[1]
        device_list.append((device_serial.strip(), device_status.strip()))

    return device_list


def get_devices(stdout_=sys.stdout):
    """Return a list of currently connected devices, as announced by
    ADB.

    Also update the internal 'DEVICES' tracker with newly connected
    devices. The function will update status of devices, as announced by
    ADB. Objects for devices that were disconnected, will remain in the
    last known status until reconnected and this function is called, or
    until their 'status' property is retrieved manually.
    """
    device_list = []

    for device_serial, device_status in _get_devices(stdout_):
        if device_status != "device":
            # device suddenly disconnected or usb debugging not authorized

            unreachable = "{} - {} - Could not be reached! Got status '{}'.\n"

            if device_serial in DEVICES:
                device = DEVICES[device_serial]
                if device.initialized:
                    manuf = device.info["Product"]["Manufacturer"]
                    model = device.info["Product"]["Model"]
                    stdout_.write(unreachable.format(manuf, model,
                                                     device_status))
                    continue

            stdout_.write(unreachable.format(device_serial, "UNKNOWN DEVICE",
                                             device_status))
            continue

        if device_serial not in DEVICES:
            stdout_.write("".join(["Device with serial id '", device_serial,
                                   "' connected\n"]))
            device = Device(device_serial, device_status)
            DEVICES[device_serial] = device
        else:
            DEVICES[device_serial].status = device_status
            device = DEVICES[device_serial]
        device_list.append(device)

    if not device_list:
        stdout_.write(
            "ERROR: No devices found! Check USB connection and try again.\n")
    return device_list


def pick_device(stdout_=sys.stdout):
    """Ask the user to pick a device from list of currently connected
    devices. If there are no devices to choose from, it will return the
    sole connected device or None, if there are no devices at all.
    """
    device_list = get_devices()

    if not device_list:
        return None

    if len(device_list) == 1:
        return device_list[0]

    while True:
        stdout_.write("Multiple devices detected!\n")
        stdout_.write(
            "Please choose which of devices below you want to work with.\n")
        for counter, device in enumerate(device_list):
            stdout_.write(" ".join([counter, ":",
                                    device.get_basic_info_string(), "\n"]))

        stdout_.write("Enter your choice: ")
        user_choice = input().strip()
        if not user_choice.isnumeric():
            stdout_.write("The answer must be a number!\n")
            continue
        user_choice = int(user_choice)
        if user_choice < 0  or user_choice >= len(device_list):
            stdout_.write("Answer must be one of the above numbers!\n")
            continue

        return device_list[user_choice]


class Device:
    """Object used in all helper functions."""

    def __init__(self, serial, status=None):

        self.serial = serial

        self.anr_trace_path = None
        self.available_commands = None
        self.ext_storage = None
        self.info = OrderedDict()

        info = [
            ("Product", ["Model",
                         "Name",
                         "Manufacturer",
                         "Brand",
                         "Device"]),
            ("OS",      ["Version",
                         "API Level",
                         "Build ID",
                         "Build Fingerprint"]),
            ("RAM",     ["Total"]),
            ("CPU",     ["Chipset",
                         "Processor",
                         "Cores",
                         "Architecture",
                         "Max Frequency",
                         "Available ABIs"]),
            ("GPU",     ["Model",
                         "GL Version",
                         "GL Extensions"]),
            ("Display", ["Resolution",
                         "Refresh-rate",
                         "V-Sync",
                         "Soft V-Sync",
                         "Density",
                         "X-DPI",
                         "Y-DPI"])
            ]

        for pair in info:
            props = OrderedDict()

            for prop in pair[1]:
                props[prop] = None

            self.info[pair[0]] = props

        self.initialized = False

        if not status:
            self._status = "offline"
        else:
            self.status = status


    def adb_command(self, *args, **kwargs):
        """Same as adb_execute(*args), but specific to the given device.
        """

        return adb_execute("-s", self.serial, *args, **kwargs)


    def shell_command(self, *args, **kwargs):
        """Same as adb_execute(["shell", *args]), but specific to the
        given device.
        """

        return adb_execute("-s", self.serial, "shell", *args, **kwargs)


    @property
    def status(self):
        """Device's current state, as announced by adb. Return offline
        if device was not found by adb.
        """
        for device_specs in _get_devices():
            if self.serial not in device_specs:
                continue

            self._status = device_specs[1]
            self._device_init()

            return self._status

        self._status = "Offline"
        return self._status


    @status.setter
    def status(self, status):

        self._status = status
        self._device_init()


    def _device_init(self):
        """Gather all the information."""
        if self._status == "device" and not self.initialized:
            self.available_commands = []
            for command in self.shell_command("ls", "/system/bin",
                                              return_output=True):
                command = command.strip()
                if command:
                    self.available_commands.append(command)

            self._get_surfaceflinger_info()
            self._get_prop_info()
            self._get_cpu_info()
            self._get_shell_env()

            ram = self.shell_command(
                "cat", "/proc/meminfo", return_output=True)
            if ram:
                ram = ram[0].split(":", maxsplit=1)[-1].strip()
                try:
                    ram = str(int(int(ram.split(" ")[0]) /1024)) + " MB"
                except ValueError:
                    ram = None
            else:
                ram = None
            self.info["RAM"]["Total"] = ram

            if "wm" in self.available_commands:
                wm_out = self.shell_command(
                    "wm", "size", return_output=True, as_list=False)
                resolution = re.search(
                    "(?<=^Physical size:)[^\n]*", wm_out, re.MULTILINE)
                if resolution:
                    resolution = resolution.group().strip()
                    self.info["Display"]["Resolution"] = resolution

                if not self.info["Display"]["Density"]:
                    wm_out = self.shell_command(
                        "wm", "density", return_output=True, as_list=False)
                    density = re.search(
                        "(?<=^Physical density:)[^\n]*", wm_out, re.MULTILINE)
                    if density:
                        density = density.group().strip()
                        self.info["Display"]["Resolution"] = density

            self.initialized = True


    def _get_prop_info(self):
        """Extract all manner of different info from Android's property
        list.
        """
        prop_dump = self.shell_command("getprop", return_output=True)
        prop_dict = {}

        for prop_pair in prop_dump:
            if not prop_pair.strip():
                continue

            props = prop_pair.split(":", maxsplit=1)
            if len(props) != 2:
                continue

            if not props[1].strip()[1:-1]:
                continue

            prop_dict[props[0].strip()] = props[1].strip()[1:-1]

        info = {"Product":{"Model"            :"[ro.product.model]",
                           "Name"             :"[ro.product.name]",
                           "Manufacturer"     :"[ro.product.manufacturer]",
                           "Brand"            :"[ro.product.brand]",
                           "Device"           :"[ro.product.device]"},
                "OS"     :{"Version"          :"[ro.build.version.release]",
                           "API Level"        :"[ro.build.version.sdk]",
                           "Build ID"         :"[ro.build.id]",
                           "Build Fingerprint":"[ro.build.fingerprint]"},
                "Display":{"Density"          :"[ro.sf.lcd_density]"}
               }

        for info_category in info:
            for info_key, prop_name in info[info_category].items():
                if prop_name not in prop_dict:
                    continue

                self.info[info_category][info_key] = prop_dict[prop_name]

        self.anr_trace_path = None
        board = None
        main_abi = None

        if "[dalvik.vm.stack-trace-file]" in prop_dict:
            self.anr_trace_path = prop_dict["[dalvik.vm.stack-trace-file]"]

        if "[ro.board.platform]" in prop_dict:
            board = prop_dict["[ro.board.platform]"]

        if not board and "[ro.mediatek.platform]" in prop_dict:
            board = prop_dict["[ro.mediatek.platform]"]

        if board and not board.isalpha():
            self.info["CPU"]["Chipset"] = board

        if "[ro.product.cpu.abi]" in prop_dict:
            main_abi = prop_dict["[ro.product.cpu.abi]"]
            if main_abi in ABI_TO_ARCH:
                self.info["CPU"]["Architecture"] = ABI_TO_ARCH[main_abi]
            else:
                self.info["CPU"]["Architecture"] = "UNRECOGNIZED"

        possible_abi_prop_names = ["[ro.product.cpu.abi]",
                                   "[ro.product.cpu.abi2]",
                                   "[ro.product.cpu.abilist]",
                                   "[ro.product.cpu.abilist32]",
                                   "[ro.product.cpu.abilist64]",
                                  ]
        abi_list = []
        for prop_name in possible_abi_prop_names:
            if prop_name in prop_dict:
                abi_list.append(prop_dict[prop_name])

        abis = ",".join(abi_list)
        abis = set(abis.split(","))
        abis = ", ".join(abis)
        self.info["CPU"]["Available ABIs"] = abis


    def _get_cpu_info(self):
        """Extract info about CPU and its chipset."""
        freq_file = "/sys/devices/system/cpu/cpu0/cpufreq/cpuinfo_max_freq"
        max_freq = self.shell_command("cat", freq_file, return_output=True,
                                      as_list=False).strip()

        cpuinfo = self.shell_command("cat", "/proc/cpuinfo",
                                     return_output=True, as_list=False)

        processor = re.search("(?<=^model name)[^\n]*", cpuinfo, re.MULTILINE)
        if not processor:
            processor = re.search(
                "(?<=^Processor)[^\n]*", cpuinfo, re.MULTILINE)

        if processor:
            processor = processor.group().split(":", maxsplit=1)[-1].strip()

            self.info["CPU"]["Processor"] = processor

        hardware = re.search("(?<=^Hardware)[^\n]*", cpuinfo, re.MULTILINE)
        if hardware:
            hardware = hardware.group().split(":", maxsplit=1)[-1].strip()

            if not self.info["CPU"]["Chipset"]:
                self.info["CPU"]["Chipset"] = hardware
            elif not self.info["CPU"]["Chipset"] == hardware:
                if self.info["CPU"]["Chipset"] in hardware:
                    self.info["CPU"]["Chipset"] = hardware
                elif hardware in self.info["CPU"]["Chipset"]:
                    pass
                else:
                    self.info["CPU"]["Chipset"] += (" (" + hardware + ")")

        core_dump = self.shell_command(
            "cat", "/sys/devices/system/cpu/present", return_output=True,
            as_list=False).strip()
        cores = core_dump.split("-")[-1]

        if cores and cores.isnumeric():
            cores = str(int(cores) + 1)
            self.info["CPU"]["Cores"] = cores

        if max_freq and max_freq.isnumeric():
            frequency = str(int(max_freq) / 1000) + " MHz"
            self.info["CPU"]["Max Frequency"] = frequency


    def _get_surfaceflinger_info(self):
        """Extract information from "SufraceFlinger" service dump."""
        dump = self.shell_command("dumpsys", "SurfaceFlinger",
                                  return_output=True, as_list=False)
        gpu_model = None
        gl_version = None

        gles = re.search("(?<=GLES: )[^\n]*", dump)
        if gles:
            gpu_type, gpu_model, gl_version = gles.group().split(", ")
            gpu_model = " ".join([gpu_type, gpu_model])

        refresh_rate = re.search("(?<=refresh-rate)[^\n]*", dump)
        if refresh_rate:
            refresh_rate = refresh_rate.group()
            refresh_rate = refresh_rate.split(":", maxsplit=1)[-1].strip()

        x_dpi = re.search("(?<=x-dpi)[^\n]*", dump)
        if x_dpi:
            x_dpi = x_dpi.group().split(":", maxsplit=1)[-1].strip()

        y_dpi = re.search("(?<=y-dpi)[^\n]*", dump)
        if y_dpi:
            y_dpi = y_dpi.group().split(":", maxsplit=1)[-1].strip()

        vsync = re.search("(?<=VSYNC state:)[^\n]*", dump)
        if vsync:
            vsync = vsync.group().strip()

        vsync_soft = re.search("(?<=soft-vsync:)[^\n]*", dump)
        if vsync_soft:
            vsync_soft = vsync_soft.group().strip()

        self.info["GPU"]["Model"] = gpu_model
        self.info["GPU"]["GL Version"] = gl_version
        self.info["Display"]["Refresh-rate"] = refresh_rate
        self.info["Display"]["V-Sync"] = vsync
        self.info["Display"]["Soft V-Sync"] = vsync_soft
        self.info["Display"]["X-DPI"] = x_dpi
        self.info["Display"]["Y-DPI"] = y_dpi

        compressions = []
        for identifier, name in COMPRESSION_TYPES.items():
            if identifier in dump:
                compressions.append(name.strip())

        if not self.info["GPU"]["GL Extensions"]:
            self.info["GPU"]["GL Extensions"] = OrderedDict()

        self.info["GPU"]["GL Extensions"] = ", ".join(compressions)


    def _get_shell_env(self):
        """Extract information from Android's shell environment"""
        #TODO: Extract information from Android shell
        shell_env = self.shell_command("printenv", return_output=True,
                                       as_list=False)

        env_dict = {}
        for line in shell_env:
            line = line.split("=", maxsplit=1)
            if len(line) == 1:
                continue
            env_dict[line[0]] = line[1]

        # find the path of the primary storage
        primary_storage = None
        if "EXTERNAL_STORAGE" in env_dict:
            if self.is_dir(env_dict["EXTERNAL_STORAGE"]):
                primary_storage = env_dict["EXTERNAL_STORAGE"]

        # external storage not found (can that even happen?) try to brute-force
        if not primary_storage:
            primary_storage_paths = [
                "/mnt/sdcard",          # this is a safe bet (in my experience)
                "/storage/sdcard0",
                "/storage/emulated",    # older androids don't have this one
                "/storage/emulated0",
                "/mnt/emmc"]            # are you a time traveler?

            for storage_path in primary_storage_paths:
                if self.is_dir(storage_path):
                    primary_storage = storage_path

        self.ext_storage = primary_storage
        # TODO: search for secondary storage path
        # TODO: search for hostname


    def is_file(self, file_path, symlink_ok=False, read=True, write=True,
                execute=False):
        """Check whether a path points to an existing file."""
        if not file_path:
            return False

        permissions = ""
        if read:
            permissions += "r"
        if write:
            permissions += "w"
        if execute:
            permissions += "x"

        out = self.shell_command('if [ -f "{}" ];'.format(file_path),
                                 "then echo 0;", "else echo 1;", "fi",
                                 return_output=True, as_list=False)

        if out == '0':
            for permission in permissions:
                out = self.shell_command(
                    'if [ -{} "{}" ];'.format(permission, file_path),
                    "then echo 0;", "else echo 1;", "fi", return_output=True,
                    as_list=False)
                if out == '0':
                    continue
                elif out == '1':
                    return False
                else:
                    print("Got unexpected output:")
                    print(out)
                    return False

            return True
        elif out == '1':
            return False
        else:
            print("Got unexpected output:")
            print(out)
            return False


    def is_dir(self, dir_path, symlink_ok=False, read=True, write=True,
                execute=False):
        """Check whether a path points to an existing directory."""
        if not dir_path:
            return False

        permissions = ""
        if read:
            permissions += "r"
        if write:
            permissions += "w"
        if execute:
            permissions += "x"

        out = self.shell_command('if [ -d "{}" ];'.format(dir_path),
                                 "then echo 0;", "else echo 1;", "fi",
                                 return_output=True, as_list=False)

        if out == '0':
            for permission in permissions:
                out = self.shell_command(
                    'if [ -{} "{}" ];'.format(permission, dir_path),
                    "then echo 0;", "else echo 1;", "fi", return_output=True,
                    as_list=False)
                if out == '0':
                    continue
                elif out == '1':
                    return False
                else:
                    print("Got unexpected output:")
                    print(out)
                    return False

            return True
        elif out == '1':
            return False
        else:
            print("Got unexpected output:")
            print(out)
            return False


    def get_full_info_string(self, indent=4):
        """Return a formatted string containing all device info"""

        info_string = []

        for info_category in self.info:
            info_string.append(info_category + ": ")

            for info_name, prop in self.info[info_category].items():
                if prop is None:
                    prop = "Unknown"
                info_string.append(indent*" " + info_name + ": " + prop)

        return "\n".join(info_string)


    def print_full_info(self, stdout_=sys.stdout):
        """Print all information from device.info onto screen."""
        stdout_.write(self.get_full_info_string() + "\n")


    def print_basic_info(self, stdout_=sys.stdout):
        """Print basic device information to console.
        Prints: manufacturer, model, OS version and available texture
        GL Extensions.
        """
        model = self.info["Product"]["Model"]
        if model is None:
            model = "Unknown model"
        manufacturer = self.info["Product"]["Manufacturer"]
        if manufacturer is None:
            manufacturer = "Unknown manufacturer"
        os_ver = self.info["OS"]["Android Version"]
        if os_ver is None:
            os_ver = "Unknown OS version"

        line1 = " - ".join([manufacturer, model, os_ver]) + "\n"
        line2 = ("GL Extensions: "
                 + str(self.info["GPU"]["GL Extensions"])
                 + "\n")

        stdout_.write(line1)
        stdout_.write(line2)


def get_app_name(apk_file, stdout_=sys.stdout):
    """Extract app name of the provided apk, from its manifest file.
    Return name if it is found, an empty string otherwise.
    """
    app_dump = aapt_execute(
        "dump", "badging", apk_file, return_output=True, as_list=False)
    app_name = re.search("(?<=name=')[^']*", app_dump)

    if app_name:
        return app_name.group()

    app_name = "UNKNOWN APP NAME (" + Path(apk_file).name + ")"
    stdout_.write("ERROR: Unknown app name\n")
    stdout_.write(
        " ".join(["Could not extract app name from the provided apk file:\n"]))
    stdout_.write(apk_file + "\n")
    stdout_.write("It may not be a valid apk archive.\n")
    return app_name


def install(device, *items, stdout_=sys.stdout):
    """Install apps.
    Accepts either a list of apk files, or list with one apk and as many
    obb files as you like.
    """
    app_list = []
    obb_list = []

    for item in items:
        if item[-3:].lower() == "apk":
            app_list.append(item)

        if item[-3:].lower() == "obb":
            obb_list.append(item)

    if len(app_list) > 1 and obb_list:
        stdout_.write(" ".join(["APK ambiguity! Only one apk file can be",
                                "installed when also pushing obb files!\n"]))
        return False

    if not app_list:
        stdout_.write("No APK found among provided files, aborting!\n")
        return False

    if not obb_list:
        app_failure = []
        for app in app_list:
            app_name = get_app_name(app, stdout_)
            stdout_.write(" ".join(["\nINSTALLING:", app_name, "\n"]))
            stdout_.write("Your device may ask you to confirm this!\n")

            if not install_apk(device, app, app_name, stdout_=stdout_):
                app_failure.append(app_name)

        stdout_.write(" ".join(["\nInstalled",
                                str(len(app_list) - len(app_failure)),
                                "out of", str(len(app_list)),
                                "provided apks.\n"]))
        if app_failure:
            stdout_.write("The following apks could not be installed:\n")
            for app_name in app_failure:
                stdout_.write("".join([app_name, "\n"]))
    else:
        app = app_list[0]
        app_name = get_app_name(app, stdout_)

        stdout_.write(" ".join(["\n", "INSTALLING:", app_name, "\n"]))
        stdout_.write("Your device may ask you to confirm this!\n")

        if not install_apk(device, app, app_name, stdout_=stdout_):
            return False

        stdout_.write(" ".join(["\nCOPYING OBB FILES FOR:", app_name, "\n"]))
        prepare_obb_dir(device, app_name)
        for obb_file in obb_list:
            if not push_obb(device, obb_file, app_name, stdout_=stdout_):
                stdout_.write("ERROR: Failed to copy " + obb_file + "\n")
                return False
        stdout_.write("\nSuccesfully installed {}!\n".format(app_name))


def install_apk(device, apk_file, app_name, stdout_=sys.stdout):
    """Install an app on specified device."""
    preinstall_log = device.shell_command(
        "pm", "list", "packages", return_output=True, as_list=False)

    if app_name in preinstall_log:
        stdout_.write(" ".join(["WARNING: Different version of the app",
                                "already installed\n"]))
        result = _clean_uninstall(
            device, target=app_name, app_name=True, check_packages=False)
        if not result:
            return False

    device.adb_command("install", "-r", "-i", "com.android.vending",
                       apk_file, stdout_=stdout_)
    postinstall_log = device.shell_command("pm", "list", "packages",
                                           return_output=True)
    for log_line in postinstall_log:
        if app_name in log_line:
            return True

    if device.status != "device":
        stdout_.write("ERROR: Device has been suddenly disconnected!\n")
    else:
        if app_name.startswith("UNKNOWN APP NAME"):
            stdout_.write(
                "ERROR: No app name, cannot verify installation outcome\n")
        else:
            stdout_.write(
                "ERROR: Installed app was not found by package manager\n")
            stdout_.write(app_name + " could not be installed!\n")
            stdout_.write(
                "Please make sure that your device meets app's criteria\n")
    return False


def prepare_obb_dir(device, app_name):
    """Prepare the obb directory for installation."""
    # pipe the stdout to suppress unnecessary errors
    obb_folder = device.ext_storage + "/Android/obb"
    device.shell_command("mkdir", obb_folder, return_output=True)
    device.shell_command(
        "rm", "-r", obb_folder + "/" + app_name, return_output=True)
    device.shell_command(
        "mkdir", obb_folder + "/" + app_name, return_output=True)


def push_obb(device, obb_file, app_name, stdout_=sys.stdout):
    """Push <obb_file> to /mnt/sdcard/Android/obb/<your.app.name> on
    <Device>.

    File is copied to primary storage, and from there to the obb folder.
    This is done in two steps because attempts to 'adb push' it directly
    into obb folder may fail on some devices.
    """
    obb_name = str(Path(obb_file).name)
    obb_target = "".join([device.ext_storage, "/Android/obb/", app_name, "/",
                          obb_name])

    #pushing obb in two steps to circumvent write protection
    device.adb_command("push", obb_file, device.ext_storage + "/" + obb_name)
    device.shell_command("mv", "".join(['"', device.ext_storage, "/",
                                        obb_name, '"']),
                         "".join(['"', obb_target, '"']))
    push_log = device.shell_command("ls", "".join(['"', obb_target, '"']),
                                    return_output=True, as_list=False)
    if push_log == obb_target:
        return True

    if device.status != "device":
        stdout_.write("ERROR: Device has been suddenly disconnected!\n")
    else:
        stdout_.write(
            "ERROR: Pushed obb file was not found in destination folder.\n")
    return False


def record_start(device, name=None, stdout_=sys.stdout):
    """Start recording on specified device. Path of the created clip
    is returned after the recording has stopped.

    If a name is not given, generate a name from current date and time.
    """
    filename = "screenrecord_" + strftime("%Y.%m.%d_%H.%M.%S") + ".mp4"
    if name:
        filename = name
    remote_recording = device.ext_storage + "/" + filename

    try:
        device.shell_command("screenrecord", "--verbose", remote_recording,
                             return_output=False, stdout_=stdout_)
    except KeyboardInterrupt:
        pass
    stdout_.write("\nRecording stopped.\n")
    # for some reason on Windows the try block above is not enough
    # an odd fix for an odd error
    try:
        # we're waiting for the clip to be fully saved to device's storage
        # there must be a better way of doing this...
        sleep(1)
    except KeyboardInterrupt:
        sleep(1)
    return remote_recording


def record_copy(device, remote_recording, output, stdout_=sys.stdout):
    """Start copying recorded clip from device's storage to disk.
    """
    recording_log = device.shell_command("ls", remote_recording,
                                         return_output=True, as_list=False)
    if recording_log != remote_recording:
        if device.status != "device":
            stdout_.write("ERROR: Device has been suddenly disconnected!\n")
        else:
            stdout_.write("ERROR: The file was not found on device!\n")
        return False

    filename = Path(remote_recording).name
    filename = device.info["Product"]["Model"] + "_" + filename
    output = str(Path(Path(output).resolve(), filename))

    device.adb_command("pull", remote_recording, output, return_output=False,
                       stdout_=stdout_)
    if Path(output).is_file():
        return output

    return False


def record(device, output=None, force=False, stdout_=sys.stdout):
    """Start recording device's screen.
    Recording can be stopped by either reaching the time limit, or
    pressing ctrl+c. After the recording has stopped, the helper
    confirms that the recording has been saved to device's storage and
    copies it to drive.
    """
    # existence of "screenrecord" is dependent on Android version, but let's
    # look for command instead, just to be safe
    if not "screenrecord" in device.available_commands:
        android_ver = device.info["OS"]["Android Version"]
        api_level = device.info["OS"]["Android API Level"]
        stdout_.write(
            " ".join(["This device's shell does not have the 'screenrecord'",
                      "command. It is available on all devices with Android",
                      "4.4 or higher (API level 19 or higher). Your device",
                      "has Android", android_ver, "API level", api_level,
                      "\n"]))
        return False

    if not output:
        output = str(Path().resolve())
    else:
        output = str(Path(output).resolve())

    if not force:
        stdout_.write(
            "".join(["Helper will record your device's screen (audio is not ",
                     "captured). The recording will stop after pressing ",
                     "'ctrl+c', or if 3 minutes have elapsed. Recording will ",
                     "be then saved to:\n", output, "\n"]))
        try:
            input("Press enter whenever you are ready to record.\n")
        except KeyboardInterrupt:
            stdout_.write("\nRecording canceled!\n")
            return False

    remote_recording = record_start(device, stdout_=stdout_)
    if not remote_recording:
        stdout_.write("ERROR: Unexpected error! Could not record\n")
        return False

    copied = record_copy(device, remote_recording, output, stdout_)
    if not copied:
        stdout_.write("ERROR: Could not copy recorded clip!\n")
        return False

    return copied


def pull_traces(device, output=None, stdout_=sys.stdout):
    """Copy the 'traces' file to the specified folder."""
    if output is None:
        output = Path().resolve()
    else:
        output = Path(output).resolve()

    anr_filename = "".join([device.info["Product"]["Model"], "_anr_",
                            strftime("%Y.%m.%d_%H.%M.%S"), ".txt"])
    remote_anr_file = "".join([device.ext_storage, "/", anr_filename])
    device.shell_command("cat", device.anr_trace_path, ">", remote_anr_file)

    cat_log = device.shell_command("ls", remote_anr_file, return_output=True,
                                   as_list=False)
    if cat_log != remote_anr_file:
        if device.status != "device":
            stdout_.write("ERROR: Device has been suddenly disconnected!\n")
        else:
            stdout_.write("ERROR: The file was not found on device!\n")
        return False

    device.adb_command("pull", remote_anr_file, str(output / anr_filename),
                       stdout_=stdout_)

    if (output / anr_filename).is_file():
        return str((output / anr_filename).resolve())
    if device.status != "device":
        stdout_.write("ERROR: Device has been suddenly disconnected\n!")
    else:
        stdout_.write("ERROR: The file was not copied!\n")
    return False


def _clean_uninstall(device, target, app_name=False, check_packages=True,
                     stdout_=sys.stdout):
    """Uninstall an app from specified device. Target can be an app name
    or a path to apk file -- by default it will check if target is a
    file, and if so it will attempt to extract app name from it.
    To disable that, set "app_name" to True.
    """
    if Path(target).is_file() and not app_name:
        target = get_app_name(target, stdout_)

    stdout_.write(" ".join(["Uninstalling", target, "... "]))
    if check_packages:
        preinstall_log = device.shell_command(
            "pm", "list", "packages", return_output=True, as_list=False)
        if target not in preinstall_log:
            stdout_.write("ERROR: App was not found\n")
            return False

    uninstall_log = device.adb_command("uninstall", target, return_output=True)
    if uninstall_log[-1] != "Success":
        if device.status != "device":
            stdout_.write("ERROR: Device has been suddenly disconnected!\n")
            return False
        else:
            stdout_.write("Unexpected error!\n")
            stdout_.write(
                " ".join(["ERROR:", target, "could not be uninstalled!\n"]))
            return False

    stdout_.write("Done!\n")
    return True


def _clean_remove(device, target, recursive=False, stdout_=sys.stdout):
    """Remove a file from device."""
    command = "rm"
    if recursive:
        command += " -r"
    if " " in target:
        target = '"{}"'.format(target)

    stdout_.write(" ".join(["Removing", target, "... "]))
    result = device.shell_command(command, target, return_output=True,
                                  as_list=False).strip()
    if not result:
        if device.status != "device":
            stdout_.write("ERROR: Device has been suddenly disconnected!\n")
            return False

        stdout_.write("Done!\n")
        return True
    elif result.lower().endswith("no such file or directory"):
        stdout_.write("File not found\n")
        return False
    elif result.lower().endswith("permission denied"):
        stdout_.write("Permission denied\n")
        return -1
    else:
        stdout_.write("Unexpected error, got:\n")
        stdout_.write("".join(["ERROR: ", result, "\n"]))
        return -2


def _clean_replace(device, remote, local, stdout_=sys.stdout):
    """Replace file on device (remote) with the a local one."""
    result = _clean_remove(device, remote)
    if int(result) < 0:
        stdout_.write(
            " ".join(["Cannot replace", remote, "due to unexpected error\n"]))
        return False

    stdout_.write(" ".join(["Placing", local, "in its place\n"]))
    device.adb_command("push", local, remote)

    _remote = remote
    if " " in _remote:
        _remote = '"{}"'.format(remote)
    push_log = device.shell_command("ls", _remote, return_output=True,
                                    as_list=False)
    if push_log != remote:
        if device.status != "device":
            stdout_.write("ERROR: Device has been suddenly disconnected!\n")
        else:
            stdout_.write("ERROR: The file was not found on device!\n")
        return False
    stdout_.write("Done!\n")
    return True


### CLEANER OPTIONS SPECIFICATION
#1 - name of the function in cleaner_config file
#2 - name of the internal function
#3 - number of required user args
#4 - additional args required by internal function
# Note: Device object is required for all functions as the first argument

                  #1                   #2                 #3  #4
CLEANER_OPTIONS = {"remove"           :(_clean_remove,     1, [False]),
                   "remove_recursive" :(_clean_remove,     1, [True]),
                   "replace"          :(_clean_replace,    2, []),
                   "uninstall"        :(_clean_uninstall,  1, [])
                  }


def parse_cleaner_config(config=CLEANER_CONFIG):
    """Parse the provided cleaner_config file. If no file is provided,
    parse the default config file.

    Return tuple containing parsed config (dict) and bad config (list).
    The former can be passed to clean().
    """
    parsed_config = {}
    bad_config = []

    for count, line in enumerate(open(config, mode="r").readlines()):
        if line.strip().startswith("#") or not line.strip():
            continue

        count += 1

        pair = line.split(":", maxsplit=1)
        if len(pair) != 2:
            bad_config.append(" ".join(["Line", str(count), ": No value"]))
            continue

        key = pair[0].strip()
        value = pair[1].strip()

        if key not in CLEANER_OPTIONS:
            bad_config.append(
                " ".join(["Line", str(count), ": Unknown command"]))
            continue

        if not value:
            bad_config.append(" ".join(["Line", str(count), ": No value"]))
            continue

        if key not in parsed_config:
            parsed_config[key] = []

        items = []
        for item in value.split(";"):
            item = item.strip()
            if not item:
                continue

            items.append(item)

        if CLEANER_OPTIONS[key][1] != len(items):
            expected = str(CLEANER_OPTIONS[key][1])
            got = str(len(items))
            plural = "s"
            if expected == "1":
                plural = ""
            bad_config.append(
                " ".join(["Line", str(count), ": Expected", expected,
                          "argument{} but got".format(plural), got]))
            continue

        parsed_config[key].append(items)

    if bad_config:
        bad_config.append("")
    return (parsed_config, "\n".join(bad_config))


def clean(device, config=None, parsed_config=None, force=False,
          stdout_=sys.stdout):
    """Clean the specified device using instructions contained in
    cleaner_config file.
    """
    # TODO: Count the number of removed files / apps
    bad_config = ""

    if config is None:
        config = CLEANER_CONFIG

    if not parsed_config:
        parsed_config, bad_config = parse_cleaner_config(config=config)

    if bad_config:
        stdout_.write("".join(["Errors encountered in the config file (",
                               config, "):\n"]))
        stdout_.write(bad_config)
        stdout_.write("Aborting cleaning!\n")
        return False
    if not parsed_config:
        stdout_.write("Empty config! Cannot clean!\n")
        return False
    # Ask user to confirm cleaning
    if not force:
        stdout_.write("The following actions will be performed:\n")
        indent = 4
        for key, action in [("remove", "remove"),
                            ("remove_recursive", "remove"),
                            ("uninstall", "uninstall")]:

            if key not in parsed_config:
                continue
            for item in parsed_config[key]:
                stdout_.write(str(action) + " : " + str(item[0]) + "\n")

        if "replace" in parsed_config:
            for pair in parsed_config["replace"]:
                stdout_.write("\nThe file: " + pair[0] + "\n")
                stdout_.write(indent * " " + "will be replaced with:" + "\n")
                stdout_.write(indent * 2 * " " + pair[1] + "\n")

        stdout_.write("\nContinue?\n")

        while True:
            usr_choice = input("Y/N : ").strip().upper()
            if usr_choice == "N":
                stdout_.write("Cleaning canceled!\n")
                return False
            elif usr_choice == "Y":
                break

    for option, items in parsed_config.items():
        for value in items:
            CLEANER_OPTIONS[option][0].__call__(device, *value,
                                                *CLEANER_OPTIONS[option][2],
                                                stdout_)
