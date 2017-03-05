#         Android QA Helper - helping you test Android apps!
#          Copyright (C) 2017  Maciej Mysliwczyk ('rmmbear')
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
import subprocess
import xml.etree.ElementTree as ET
from time import strftime, sleep
import helper as _helper
from helper import sys
from helper import Path
from helper import OrderedDict


ABI_TO_ARCH = {"armeabi"    :"32bit (ARM)",
               "armeabi-v7a":"32bit (ARM)",
               "arm64-v8a"  :"64bit (ARM64)",
               "x86"        :"32bit (Intel x86)",
               "x86_64"     :"64bit (Intel x86_64)",
               "mips"       :"32bit (Mips)",
               "mips64"     :"64bit (Mips64)",
              }

CLEANER_OPTIONS = {"remove"           :(["shell", "rm", "--"]),
                   "remove_recursive" :(["shell", "rm", "-r", "--"]),
                   "uninstall"        :(["uninstall"]),
                   "replace"          :(["shell", "rm", "-f", "--"],
                                        ["push"])
                  }

DEVICES = {}
COMPRESSION_TYPES = _helper.COMPRESSION_TYPES
ADB = _helper.ADB
AAPT = _helper.AAPT
CLEANER_CONFIG = _helper.CLEANER_CONFIG


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
        print("ERROR: No devices found! Check USB connection and try again.")

    return device_list


def pick_device():
    """Asks the user to pick which device they want to use. If there are no
    devices to choose from it will return the sole connected device or None.
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
                                     return_output=True)

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

            props = prop_pair.split(":", maxsplit=1)
            if len(props) != 2:
                continue

            prop_dict[props[0].strip()] = props[1].strip()[1:-1]


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
        for identifier, name in COMPRESSION_TYPES.items():
            if identifier in dump:
                compressions.append(name.strip())

        if not self.info["GPU"]["Compression Types"]:
            self.info["GPU"]["Compression Types"] = OrderedDict()

        self.info["GPU"]["Compression Types"] = ", ".join(compressions)


    def dump_xml(self):
        pass


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


def get_app_name(apk_file):
    """Extracts app name of the provided apk, from its manifest file.
    Returns name if it is found, an empty string otherwise.
    """

    app_dump = aapt_execute("dump", "badging", apk_file, return_output=True,
                            as_list=False)
    app_name = re.search("(?<=name=')[^']*", app_dump)

    if app_name:
        return app_name.group()

    return ""


def install(device, items):
    """Installs apps.
    Accepts either a list of apk files, or list with one apk and as many obb
    files as you like.
    """

    app_list = []
    obb_list = []

    for item in items:
        if item[-3:].lower() == "apk":
            app_list.append(item)

        if item[-3:].lower() == "obb":
            obb_list.append(item)

    if len(app_list) > 1 and obb_list:
        print("APK ambiguity! Only one apk file can be installed when",
              "also pushing obb files!")
        return False

    if not app_list:
        print("No APK found among provided files, aborting!")
        return False

    if not obb_list:
        app_failure = []
        for app in app_list:
            app_name = get_app_name(app)

            print("\nBEGINNING INSTALLATION:", app_name)
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
        app_name = get_app_name(app)

        if not install_apk(device, app, app_name):
            print("FAILED TO INSTALL:", app_name)
            return False

        print("\nSUCCESSFULLY COPIED AND INSTALLED THE APK FILE\n")

        print("BEGINNING COPYING OBB FILE FOR:", app_name)

        for obb_file in obb_list:
            if not push_obb(device, obb_file, app_name):
                print("OBB COPYING FAILED")
                print("Failed to copy", obb_file)
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
    """Push <obb_file> to /mnt/sdcard/Android/obb/<your.app.name> on <Device>.

    Clears contents of the obb folder and recreates it if necessary. File is
    then copied to internal storage (/mnt/sdcard/), and from there to the obb
    folder. This is done in two steps because of write protection of sorts --
    attempts to adb push it directly into obb folder may fail on some devices.
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
    Recording can be stopped by either reaching the time limit, or pressing
    ctrl+c. After the recording has stopped, the helper confirms that the
    recording has been saved to device's storage and copies it to drive.
    """

    if not output:
        output = "./"

    Path(output).mkdir(exist_ok=True)

    filename = "screenrecord_" + strftime("%Y.%m.%d_%H.%M.%S") + ".mp4"
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
    """Copy contents of the 'traces' into file in the specified folder.
    """

    if output is None:
        output = Path()
    else:
        output = Path(output)

    output.mkdir(exist_ok=True)

    anr_filename = "".join([device.info["Product"]["Model"], "_anr_",
                            strftime("%Y.%m.%d_%H.%M.%S"), ".txt"])

    traces = device.shell_command("cat", "/data/anr/traces.txt",
                                  return_output=True, as_list=False)

    # TODO: check if what is saved is actually full traces file
    # device might have been suddenly disconnected during cat-ing
    # which will result in only partial log

    # maybe 'mv /data/anr/traces/ /mnt/sdcard/tmp_traces' and use adb pull?
    # may be a bit messy...

    with (output / anr_filename).open(mode="w", encoding="utf-8") as anr_file:
        anr_file.write(traces)

    return str((output / anr_filename).resolve())


def parse_cleaner_config(config=CLEANER_CONFIG):
    """Function for parsing cleaner config files. Returns tuple containing a
    parsed config (dict) and bad config (list). The former can be passed to
    clean().
    """

    parsed_config = {}
    bad_config = []

    for count, line in enumerate(open(config, mode="r").readlines()):
        if line.startswith("#") or not line.strip():
            continue

        count += 1 # start from 1 not 0

        pair = line.split(":", maxsplit=1)
        if len(pair) != 2:
            bad_config.append((count, "No value"))
            continue

        key = pair[0].strip()
        value = pair[1].strip()

        if key not in CLEANER_OPTIONS:
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

                parsed_config[key].append(get_app_name(value))
                continue

            if " " not in value:
                parsed_config[key].append(value)
                continue

            if value[0] not in ["'", "\""]:
                value = "\"" + value

            if value[-1] not in ["'", "\""]:
                value += "\""

            parsed_config[key].append(value)


    return (parsed_config, bad_config)


def clean(device, config=CLEANER_CONFIG, parsed_config=None, force=False):
    """
    """
    # TODO: Test each cleaning action for success / failure
    # TODO: Count the number of removed files / apps

    bad_config = []

    if not parsed_config:
        parsed_config, bad_config = parse_cleaner_config(config=config)

    if bad_config:
        print("Errors encountered in the config file")
        print("(", config, ")", sep="")
        indent = 4
        for line, reason in bad_config:
            print(indent*" ", "Line", line, "-", reason)

        print("Aborting cleaning!")
        return False

    if not parsed_config:
        print("Empty config! Cannot clean!")
        return False

    if not force:
        print("The following actions will be performed:")
        indent = 2
        for key, action in [("remove", "remove"),
                            ("remove_recursive", "remove"),
                            ("uninstall", "uninstall")]:

            if key not in parsed_config:
                continue

            for item in parsed_config[key]:
                print(action, ":", item)

        if "replace" in parsed_config:
            print()
            for pair in parsed_config["replace"]:
                print("The file:", pair[0])
                print(indent * " ", end="")
                print("will be replaced with:")
                print(indent * 2 * " ", end="")
                print(pair[1])

        print()
        print("Is this ok?")

        while True:
            usr_choice = input("Y/N : ").strip().upper()
            if usr_choice == "N":
                print("User canceled cleaning")
                return False
            elif usr_choice == "Y":
                break

    for option, value in parsed_config.items():
        for item in value:
            if option == "replace":
                remote = ""
                if item[0][0] not in ["'", "\""]:
                    remote = "\"" + item[0]

                if remote[-1] not in ["'", "\""]:
                    remote += "\""

                device.adb_command(*CLEANER_OPTIONS[option][0], remote)
                device.adb_command(*CLEANER_OPTIONS[option][1], item[1], item[0])
            else:
                device.adb_command(*CLEANER_OPTIONS[option], item)
