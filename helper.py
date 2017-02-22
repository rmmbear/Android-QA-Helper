#         Android QA Helper - helping you test Android apps!
#          Copyright (C) 2017  rmmbear
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

"""Program for performing common ADB operations automatically.

Work in progress, bless this mess.
"""

import argparse
import inspect
import os
import re
import subprocess
import sys
from collections import OrderedDict
from pathlib import Path
from time import strftime, sleep


VERSION = "0.9"
VERSION_DATE = "17-02-2017"
GITHUB_SOURCE = "https://github.com/rmmbear/Android-QA-Helper"
VERSION_STRING = " ".join(["Android QA Helper ver", VERSION, ":",
                           VERSION_DATE, ": Copyright (c) 2017 rmmbear"]
                         )
SOURCE_STRING = "Check the source code at " + GITHUB_SOURCE

ABI_TO_ARCH = {"armeabi"    :"32bit (ARM)",
               "armeabi-v7a":"32bit (ARM)",
               "arm64-v8a"  :"64bit (ARM64)",
               "x86"        :"32bit (Intel x86)",
               "x86_64"     :"64bit (Intel x86_64)",
               "mips"       :"32bit (Mips)",
               "mips64"     :"64bit (Mips64)",
              }


def get_script_dir():
    """
    """

    if getattr(sys, 'frozen', False):
        path = os.path.abspath(sys.executable)
    else:
        path = inspect.getabsfile(get_script_dir)

    path = os.path.realpath(path)
    return os.path.dirname(path)


BASE = get_script_dir()
ADB = BASE + "/adb"
AAPT = BASE + "/build_tools/aapt"
CLEANER_CONFIG = BASE + "/cleaner_config"
DEVICES = {}
COMPRESSION_EXTENSIONS = {}


for line in open(BASE + "/compression_identifiers", mode="r", encoding="utf-8").read().splitlines():
    if not line:
        continue

    comp_id, comp_name = line.split(",")
    COMPRESSION_EXTENSIONS[comp_id] = comp_name

HELP_STR = """Launching without arguments enters the interactive helper loop.
"""
PARSER = argparse.ArgumentParser(prog="helper",
                                 usage="%(prog)s [-d <serial>] [options]",
                                 description=HELP_STR)
HELP_STR = """Specify a device you want to work with. Option must be used
alongside other option to be effective. If a device is not specified, helper
will let you pick a device from the list of currently connected device, so this
option is not needed for every command."""
PARSER.add_argument("-d", "--device", nargs=1, dest="device", help=HELP_STR,
                    metavar="serial_no")
PARSER_GROUP = PARSER.add_mutually_exclusive_group()
HELP_STR = """Install an app. Can install a single apk, single apk and
accompanying obb file, or a series of apk files."""
PARSER_GROUP.add_argument("-i", "--install", nargs="+", dest="install",
                          help=HELP_STR, metavar="file")
HELP_STR = """Record the screen of your device. Helper will ask you for
confirmation before starting the recording, and a countdown will be shown. Once
the recording has started, it will stop on its own after the time limit has
elapsed (3 minutes), or if you press 'ctrl+c'. After the recording has been
stopped, helper will copy the file to specified location. If a location was not
specified, the file will be copied to wherever helper is located on your
drive. NOTE: Sound is not, and cannot be recorded."""
PARSER_GROUP.add_argument("-r", "--record", nargs="?", const=".", default=None,
                          dest="record", help=HELP_STR, metavar="destination")
HELP_STR = """Pull the dalvik vm stack traces / anr log file to specified
location. If a location was not specified, the file will be copied to wherever
helper is located on your drive."""
PARSER_GROUP.add_argument("-t", "--pull_traces", nargs="?", const=".",
                          default=None, dest="pull_traces", help=HELP_STR,
                          metavar="destination")
HELP_STR = """Clean your device, as specified in cleaner_config file. You can
tell helper to delete files or directories, uninstall apps and replace files on
device with ones from your drive. See the contents of '{}' for info on how to
add items to the list.""".format(CLEANER_CONFIG)
PARSER_GROUP.add_argument("-c", "--clean", nargs="?", const=CLEANER_CONFIG,
                          default=None, dest="clean", help=HELP_STR,
                          metavar="config")
HELP_STR = """Show info for all connected devices. If --device was specified,
information only for that device will be shown."""
PARSER_GROUP.add_argument("-n", "--info", action="store_true", dest="info",
                          help=HELP_STR)
HELP_STR = "Show version information."
PARSER_GROUP.add_argument("-v", "--version", action="store_true",
                          dest="version", help=HELP_STR)

NO_ARGS = PARSER.parse_args([])


def adb_execute(*args, return_output=False, check_server=True, as_list=True):
    """Execute an ADB command, and return -- or don't -- its result.

    If check_server is true, function will first make sure that an ADB
    server is available before executing the command.
    """

    try:
        if check_server:
            subprocess.run([ADB, "start-server"], stdout=subprocess.PIPE)

        if return_output:
            cmd_out = subprocess.run((ADB,) + args, stdout=subprocess.PIPE,
                                     universal_newlines=True, encoding="utf-8"
                                    ).stdout.strip()

            if as_list:
                return cmd_out.splitlines()

            return cmd_out

        subprocess.run((ADB,) + args)
    except FileNotFoundError:
        print("Helper expected ADB to be located in '", ADB,
              "' but could not find it.", sep="")
        sys.exit("Please make sure the ADB binary is in the specified path.")


def aapt_execute(*args, return_output=False, as_list=True):
    """Execute an AAPT command, and return -- or don't -- its result.
    """

    try:
        if return_output:
            cmd_out = subprocess.run((AAPT,) + args, stdout=subprocess.PIPE,
                                     universal_newlines=True, encoding="utf-8"
                                    ).stdout.strip()

            if as_list:
                return cmd_out.splitlines()

            return cmd_out

        subprocess.run((AAPT,) + args)
    except FileNotFoundError:
        print("Helper expected AAPT to be located in '", AAPT,
              "' but could not find it.", sep="")
        sys.exit("Please make sure the AAPT binary is in the specified path.")


def _get_devices():
    """Return a list of tuples with serial number and status, for all
    connected devices.
    """
    device_list = []

    device_specs = adb_execute("devices", return_output=True)
    device_specs = device_specs

    # Skip the first line, which is always "list of devices attached"
    # if nothing breaks, that is
    for device_line in device_specs[1:]:
        device_serial, device_status = device_line.split()

        device_list.append((device_serial.strip(), device_status.strip()))

    return device_list


def get_devices():
    """Returns a list of currently connected devices, as announced by
    ADB.

    Also updates the internal 'DEVICES' tracker with newly connected
    devices. The function will update status of devices, as announced by
    ADB. Objects for devices that were disconnected, will remain in the
    last known status until reconnected and this function is called, or
    until their 'status' property is retrieved manually.
    """
    device_list = []

    for device_serial, device_status in _get_devices():
        if device_serial not in DEVICES:
            device = Device(device_serial, device_status)
            DEVICES[device_serial] = device
        else:
            DEVICES[device_serial].status = device_status
            device = DEVICES[device_serial]


        if device_status != "device":
            # device was suddenly disconnected or user did not authorize
            # usb debugging

            unreachable = "{} - {} - Could not be reached! Got status '{}'."

            if device.initialized:
                print(unreachable.format(device.info["Product"]["Manufacturer"],
                                         device.info["Product"]["Model"],
                                         device_status))
            else:
                print(unreachable.format(device_serial, "UNKNOWN DEVICE",
                                         device_status))
        else:
            device_list.append(device)

    if not device_list:
        print("ERROR: No devices found! Check your USB connection and try again.")

    return device_list


def pick_device():
    """Asks the user to pick which device they want to use. If there are
    no devices to choose from it will return the sole connected device
    or None.
    """

    device_list = get_devices()

    if not device_list:
        return None

    if len(device_list) == 1:
        return device_list[0]

    while True:
        print("Multiple devices detected!")
        print("Please choose which of devices below you want to work with.")
        print()
        for counter, device in enumerate(device_list):
            print(counter, end=": ")
            device.print_basic_info()
            print()

        user_choice = input("Enter your choice: ").strip()
        if not user_choice.isnumeric():
            print("The answer must be a number!")
            continue

        user_choice = int(user_choice)

        if user_choice < 0  or user_choice >= len(device_list):
            print("Answer must be one of the above numbers!")
            continue

        return device_list[user_choice]


class Device:
    """Container for
    """

    def __init__(self, serial, status=None):

        self.serial = serial

        self.anr_trace_path = None
        self.available_commands = None
        self.info = OrderedDict()

        info = [
            ("Product", ["Model",
                         "Name",
                         "Manufacturer",
                         "Brand",
                         "Device"]),
            ("OS",      ["Android Version",
                         "Android API Level",
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
                         "Compression Types"]),
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


    def adb_command(self, *args, return_output=False, check_server=True,
                    as_list=True):
        """
        """

        return adb_execute("-s", self.serial, *args,
                           return_output=return_output, as_list=as_list,
                           check_server=check_server)


    def shell_command(self, *args, return_output=False, check_server=True,
                      as_list=True):
        """
        """

        return adb_execute("-s", self.serial, "shell", *args,
                           return_output=return_output, as_list=as_list,
                           check_server=check_server)


    @property
    def status(self):
        """Device's current state, as announced by adb.
        Returns offline if device was not found by adb.
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
        """
        """

        self._status = status
        self._device_init()


    def _device_init(self):
        """Gather all the information.
        """

        if self._status == "device" and not self.initialized:
            self.available_commands = []
            for command in self.shell_command("ls", "/system/bin", return_output=True):
                command = command.strip()
                if command:
                    self.available_commands.append(command)

            self._get_surfaceflinger_info()
            self._get_prop_info()
            self._get_cpu_info()

            ram = self.shell_command("cat", "/proc/meminfo",
                                     return_output=True)[0]
            ram = ram.split(":", maxsplit=1)[-1].strip()

            if ram:
                ram = str(int(int(ram.split(" ")[0]) /1024)) + " MB"

            self.info["RAM"]["Total"] = ram

            if "wm" in self.available_commands:
                wm_out = self.shell_command("wm", "size", return_output=True,
                                            as_list=False)

                resolution = re.search("(?<=^Physical size:)[^\n]*", wm_out,
                                       re.MULTILINE)
                if resolution:
                    self.info["Display"]["Resolution"] = resolution.group().strip()

                if not self.info["Display"]["Density"]:
                    wm_out = self.shell_command("wm", "density",
                                                return_output=True,
                                                as_list=False)

                    density = re.search("(?<=^Physical density:)[^\n]*",
                                        wm_out, re.MULTILINE)
                    if density:
                        self.info["Display"]["Resolution"] = density.group().strip()

            self.initialized = True

        return self.initialized


    def _get_prop_info(self):
        """Extract all manner of different info from Android's property list.
        """

        prop_dump = self.shell_command("getprop", return_output=True)
        prop_dict = {}

        for prop_pair in prop_dump:
            if not prop_pair.strip():
                continue

            prop_name, prop_val = prop_pair.split(":", maxsplit=1)
            prop_dict[prop_name.strip()] = prop_val.strip()[1:-1]


        info = {"Product":{"Model"            :"[ro.product.model]",
                           "Name"             :"[ro.product.name]",
                           "Manufacturer"     :"[ro.product.manufacturer]",
                           "Brand"            :"[ro.product.brand]",
                           "Device"           :"[ro.product.device]"},
                "OS"     :{"Android Version"  :"[ro.build.version.release]",
                           "Android API Level":"[ro.build.version.sdk]",
                           "Build ID"         :"[ro.build.id]",
                           "Build Fingerprint":"[ro.build.fingerprint]"},
                "Display":{"Density"          :"[ro.sf.lcd_density]"}
               }

        for info_category in info:
            for info_key, prop_name in info[info_category].items():
                if prop_name not in prop_dict:
                    continue

                self.info[info_category][info_key] = prop_dict[prop_name]


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
            self.info["CPU"]["Architecture"] = ABI_TO_ARCH[main_abi]

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

        abis = ",".join(set(abi_list))
        abis = abis.replace(",", ", ")

        self.info["CPU"]["Available ABIs"] = abis


    def _get_cpu_info(self):
        """Extract info about CPU and its chipset.
        """

        freq_file = "/sys/devices/system/cpu/cpu0/cpufreq/cpuinfo_max_freq"
        max_freq = self.shell_command("cat", freq_file, return_output=True,
                                      as_list=False).strip()

        cpuinfo = self.shell_command("cat", "/proc/cpuinfo",
                                     return_output=True, as_list=False)


        processor = re.search("(?<=^model name)[^\n]*", cpuinfo, re.MULTILINE)
        if not processor:
            processor = re.search("(?<=^Processor)[^\n]*", cpuinfo, re.MULTILINE)

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

        core_dump = self.shell_command("cat", "/sys/devices/system/cpu/present",
                                       return_output=True, as_list=False).strip()
        cores = core_dump.split("-")[-1]

        if cores and cores.isnumeric():
            cores = str(int(cores) + 1)
            self.info["CPU"]["Cores"] = cores

        if max_freq and max_freq.isnumeric():
            self.info["CPU"]["Max Frequency"] = str(int(max_freq) / 1000) + " MHz"


    def _get_surfaceflinger_info(self):
        """Extract information from "SufraceFlinger" service dump.
        """

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
            refresh_rate = refresh_rate.group().split(":", maxsplit=1)[-1].strip()

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
        for identifier, name in COMPRESSION_EXTENSIONS.items():
            if identifier in dump:
                compressions.append(name.strip())

        if not self.info["GPU"]["Compression Types"]:
            self.info["GPU"]["Compression Types"] = OrderedDict()

        self.info["GPU"]["Compression Types"] = ", ".join(compressions)


    def print_full_info(self):
        """
        """

        indent = 4

        for info_category in self.info:
            print(info_category, ":", sep="")

            for info_name, prop in self.info[info_category].items():
                if prop is None:
                    prop = "Unknown"
                print(indent*" ", info_name, ": ", prop, sep="")


    def print_basic_info(self):
        """Print basic device information to console.
        prints: manufacturer, model, OS version and available texture
        compression types.
        """

        print(self.info["Product"]["Manufacturer"], end=" - ")
        print(self.info["Product"]["Model"], end=" - ")
        print(self.info["OS"]["Android Version"])
        print("Compression Types: ", self.info["GPU"]["Compression Types"])


def install(device, items):
    """Installs apps.
    Accepts either a list of apk paths, or list with one apk and one obb
    path.
    """

    app_list = []
    obb = None

    for item in items:
        if item[-3:].lower() == "apk":
            app_list.append(item)

        if item[-3:].lower() == "obb":
            if obb:
                print("OBB ambiguity!",
                      "Only one obb file can be pushed at a time!")
                return False

            obb = item

    if len(app_list) > 1 and obb:
        print("APK ambiguity! Only one apk file can be installed when",
              "also pushing obb file!")
        return False

    if not app_list:
        print("No APK found among provided files, aborting!")
        return False

    if not obb:
        app_failure = []
        for app in app_list:
            app_name = aapt_execute("dump", "badging", app,
                                    return_output=True, as_list=False)
            app_name = re.search("(?<=name=')[^']*", app_name).group()


            print("BEGINNING INSTALLATION:", app_name)
            print("Your device may ask you for confirmation!\n")

            if not install_apk(device, app, app_name):
                print("FAILED TO INSTALL:", app_name)
                app_failure.append((app_name, app))

            else:
                print("SUCCESFULLY INSTALLED:", app_name)

        print("Installed", len(app_list) - len(app_failure), "out of",
              len(app_list), "provided apks.")

        if app_failure:
            indent = 4
            print("The following apks could not be installed:")

            for app_path, app_name in app_failure:
                print(indent*" ", Path(app_path).name, ":", app_name)

    else:
        app = app_list[0]
        app_name = aapt_execute("dump", "badging", app,
                                return_output=True, as_list=False)
        app_name = re.search("(?<=name=')[^']*", app_name).group()

        if not install_apk(device, app, app_name):
            print("FAILED TO INSTALL:", app_name)
            return False

        print("\nSUCCESSFULLY COPIED AND INSTALLED THE APK FILE\n")

        print("BEGINNING COPYING OBB FILE FOR:", app_name)

        if not push_obb(device, obb, app_name):
            print("OBB COPYING FAILED")
            return False

        print("SUCCESSFULLY COPIED OBB FILE TO ITS DESTINATION.\n")
        print("Installation complete!")


def install_apk(device, apk_file, app_name, ignore_uninstall_err=False):
    """
    """

    preinstall_log = device.shell_command("pm", "list", "packages",
                                          return_output=True, as_list=False)

    if app_name in preinstall_log:
        print("Different version of the app already installed, deleting...")
        uninstall_log = device.adb_command("uninstall", app_name,
                                           return_output=True)

        if uninstall_log[-1] != "Success":
            if device.status != "device":
                print("Device has been suddenly disconnected!")
                return False
            else:
                print("Unexpected error!")
                print(app_name, "could not be uninstalled!")
                print("Installation cannot continue.", "You can ignore",
                      "this error with '--force' option alongside --install")

                if ignore_uninstall_err:
                    print("Error ignored.")
                    print("Installer will attempt to replace the app.")
                else:
                    return False

        print("Successfully uninstalled", app_name, "\n")

    device.adb_command("install", "-r", "-i", "com.android.vending",
                       apk_file)

    postinstall_log = device.shell_command("pm", "list", "packages",
                                           return_output=True)

    for log_line in postinstall_log:
        if app_name in log_line:
            return True

    if device.status != "device":
        print(device.info["Product"]["Model"],
              "- Device has been suddenly disconnected!")
    else:
        print("Installed app was not found by package manager")
        print(app_name, "could not be installed!")
        print("Please make sure that your device meets app's criteria")

    return False


def push_obb(device, obb_file, app_name):
    """
    """
    obb_folder = "/mnt/sdcard/Android/obb"

    obb_name = str(Path(obb_file).name)

    # prepare environment for copying
    # pipe the stdout to suppress unnecessary errors
    device.shell_command("mkdir", obb_folder, return_output=True)
    device.shell_command("rm", "-fr", obb_folder + "/" + app_name,
                         return_output=True)
    device.shell_command("mkdir", obb_folder + "/" + app_name,
                         return_output=True)

    obb_target = "/mnt/sdcard/Android/obb/" + app_name + "/" + obb_name

    #pushing obb in two steps to circumvent write protection
    device.adb_command("push", obb_file, "/mnt/sdcard/" + obb_name)
    device.shell_command("mv", "\"/mnt/sdcard/" + obb_name + "\"",
                         "\"" + obb_target + "\"")

    push_log = device.shell_command("ls", "\"" + obb_target + "\"",
                                    return_output=True, as_list=False)

    if push_log == obb_target:
        return True

    if device.status != "device":
        print("Device has been suddenly disconnected!")
    else:
        print("Pushed obb file could not be found in destination folder.")

    return False


def record(device, output=None):
    """Start recording device's screen.
    Recording can be stopped by either reaching the time limit, or pressing ctrl+c.
    After the recording has stopped, the helper confirms that the recording has
    been saved to device's storage and copies it to user's drive.
    """

    if not output:
        output = "./"

    Path(output).mkdir(exist_ok=True)

    filename = "screenrecord_" + strftime("%Y.%m.%d_%H.%M.%S")
    remote_recording = "/mnt/sdcard/" + filename

    filename = device.info["Product"]["Model"] + "_" + filename
    output = str(Path(Path(output).resolve(), filename))

    print("Helper will record your device's screen (audio is not captured).")
    print("The recording will stop after pressing 'ctrl+c', or if 3 minutes have elapsed.")
    print("Recording will be then saved to '{}'".format(output))
    input("Press enter whenever you are ready to record.\n")

    try:
        device.shell_command("screenrecord", "--verbose", remote_recording,
                             return_output=False)
        print("\nRecording stopped by device.")
    except KeyboardInterrupt:
        print("\nRecording stopped bu user.")

    # we're waiting for the clip to be fully saved to device's storage
    # there must be a better way of doing this...
    sleep(1)

    recording_log = device.shell_command("ls", remote_recording,
                                         return_output=True, as_list=False)

    if recording_log != remote_recording:
        if device.status != "device":
            print("Device has been suddenly disconnected!")
        else:
            print("Unexpected error! The file could not be found on device!")

        return False

    device.adb_command("pull", remote_recording, output, return_output=False)

    if Path(output).is_file():
        return output

    return False


def pull_traces(device, output=None):
    """
    """

    # I have enountered devices which have the anr file set to read-only
    # that's why I am using 'cat anr > file' instead of just an 'adb pull'

    if output is None:
        output = Path()
    else:
        output = Path(output)

    output.mkdir(exist_ok=True)
    output = output.resolve()

    anr_filename = "".join([device.info["Product"]["Model"], "_anr_",
                            strftime("%Y.%m.%d_%H.%M.%S"), ".txt"])

    traces = device.shell_command("cat", "/data/anr/traces.txt",
                                  return_output=True, as_list=False)

    # TODO: check if what is saved is actually full traces file
    # device might have been suddenly disconnected during cat-ing
    # which will result in only partial log

    with open(str(output) + anr_filename, mode="w", encoding="utf-8") as anr_file:
        anr_file.write(traces)

    return str(Path(output, anr_filename))


def clean(device, config=CLEANER_CONFIG):
    """
    """
    # TODO: Test each cleaning action for success / failure
    # TODO: Count the number of removed files / apps

    known_options = {"remove"           :(["shell", "rm", "--"]),
                     "remove_recursive" :(["shell", "rm", "-r", "--"]),
                     "uninstall"        :(["uninstall"]),
                     "replace"          :(["shell", "rm", "-f", "--"], ["push"])
                    }

    parsed_config = {}
    bad_config = []

    for count, line in enumerate(open(config, mode="r").readlines()):
        if line.startswith("#") or not line.strip():
            continue

        count += 1

        pair = line.split(":", maxsplit=1)
        if len(pair) != 2:
            bad_config.append((count, "No value"))
            continue

        key = pair[0].strip()
        value = pair[1].strip()

        if key not in known_options:
            bad_config.append((count, "Unknown command"))
            continue

        if not value:
            bad_config.append((count, "No value"))
            continue

        if key not in parsed_config:
            parsed_config[key] = []

        if key == "replace":
            items = []
            for item in value.split(","):
                items.append(item.strip())

            parsed_config[key].append(items)
        else:
            if key == "uninstall":
                if not Path(value).is_file():
                    parsed_config[key].append(value)
                    continue
            if " " not in value:
                parsed_config[key].append(value)
                continue

            if value[0] not in ["'", "\""]:
                value = "\"" + value

            if value[-1] not in ["'", "\""]:
                value += "\""

            parsed_config[key].append(value)

    if bad_config:
        print("Errors encountered in the config file")
        print("(", config, ")", sep="")
        indent = 4
        for line, reason in bad_config:
            print(indent*" ", "Line", line, "-", reason)

    print(parsed_config)

    for option, value in parsed_config.items():
        for item in value:
            if option == "replace":
                print(*known_options[option][0], item[0])
                print(*known_options[option][1], item[1], item[0])
                input()
                remote = ""
                if item[0][0] not in ["'", "\""]:
                    remote = "\"" + item[0]

                if remote[-1] not in ["'", "\""]:
                    remote += "\""

                device.adb_command(*known_options[option][0], remote)
                device.adb_command(*known_options[option][1], item[1], item[0])
            else:
                print(*known_options[option], item)
                input()
                device.adb_command(*known_options[option], item)


if __name__ == "__main__" or __name__ == "helper__main__":
    ARGS = PARSER.parse_args()

    CHOSEN_DEVICE = None

    if ARGS == NO_ARGS:
        import helper_interactive

        helper_interactive.interactive_loop()
        sys.exit()

    if ARGS.version:
        print(VERSION_STRING)
        print(SOURCE_STRING)
        print()
        sys.exit()

    if ARGS.device:
        get_devices()

        if not ARGS.device in get_devices():
            print("Device with serial number", ARGS.device,
                  "was not found by Helper!")
            print("Check your usb connection and make sure",
                  "you're typing in a valid serial number.\n")
            sys.exit()

        CHOSEN_DEVICE = DEVICES[ARGS.device]
    elif not ARGS.info:
        CHOSEN_DEVICE = pick_device()
        if not CHOSEN_DEVICE:
            sys.exit()

    if ARGS.install:
        install(CHOSEN_DEVICE, ARGS.install)

    if ARGS.pull_traces:
        destination = pull_traces(CHOSEN_DEVICE, ARGS.pull_traces)
        if destination:
            print("Traces file was saved to:", destination, sep="\n")
        else:
            print("Unexpected error occurred --",
                  "could not save traces to drive")

    if ARGS.record:
        destination = record(CHOSEN_DEVICE, ARGS.record)
        if destination:
            print("Recording was saved to:", destination, sep="\n")
        else:
            print("Unexpected error occurred --",
                  "could not save recording to drive")

    if ARGS.clean:
        D = []
        if CHOSEN_DEVICE:
            D = [CHOSEN_DEVICE]
        else:
            D.extend(get_devices())

        for d in D:
            clean(d, ARGS.clean)

    if ARGS.info:
        D = []
        if CHOSEN_DEVICE:
            D = [CHOSEN_DEVICE]
        else:
            D.extend(get_devices())

        for d in D:
            d.print_full_info()
