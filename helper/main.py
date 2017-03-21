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
from time import strftime, sleep
import helper as _helper
from helper import sys
from helper import Path
from helper import OrderedDict

DEVICES = {}

ABI_TO_ARCH = _helper.ABI_TO_ARCH
CLEANER_CONFIG = _helper.CLEANER_CONFIG
COMPRESSION_TYPES = _helper.COMPRESSION_TYPES
ADB = _helper.ADB
AAPT = _helper.AAPT


def adb_execute(*args, return_output=False, check_server=True, as_list=True,
                _stdout=sys.stdout):
    """Execute an ADB command, and return -- or don't -- its result.

    If check_server is true, function will first make sure that an ADB server
    is available before executing the command.
    """
    try:
        if check_server:
            subprocess.run([ADB, "start-server"], stdout=subprocess.PIPE)

        if return_output:
            cmd_out = subprocess.run((ADB,) + args, stdout=subprocess.PIPE,
                                     stderr=subprocess.STDOUT, encoding="utf-8",
                                     universal_newlines=True).stdout.strip()

            if as_list:
                return cmd_out.splitlines()

            return cmd_out

        if _stdout != sys.__stdout__:
            cmd_out = subprocess.Popen((ADB,) + args, stdout=subprocess.PIPE,
                                       universal_newlines=True, encoding="utf-8")

            last_line = ''
            for line in cmd_out.stdout:
                if line != last_line:
                    _stdout.write(line)
                    last_line = line
        else:
            subprocess.run((ADB,) + args)

    except FileNotFoundError:
        _stdout.write("Helper expected ADB to be located in '")
        _stdout.write(ADB)
        _stdout.write("' but could not find it.")
        _stdout.write("\n")
        sys.exit("Please make sure the ADB binary is in the specified path.")

    except (PermissionError, OSError):
        print("Helper could not launch ADB. Please make sure the following",
              "path is correct and points to an actual ADB binary:", ADB,
              "To fix this issue you may need to edit or delete the helper",
              "config file, located at:", _helper.CONFIG)
        sys.exit()


def aapt_execute(*args, return_output=False, as_list=True, _stdout=sys.stdout):
    """Execute an AAPT command, and return -- or don't -- its result."""
    try:
        if return_output:
            cmd_out = subprocess.run((AAPT,) + args, stdout=subprocess.PIPE,
                                     universal_newlines=True, encoding="utf-8"
                                    ).stdout.strip()

            if as_list:
                return cmd_out.splitlines()

            return cmd_out

        if _stdout != sys.__stdout__:
            cmd_out = subprocess.Popen((AAPT,) + args, stdout=subprocess.PIPE,
                                       universal_newlines=True, encoding="utf-8")

            last_line = ''
            for line in cmd_out.stdout:
                if line != last_line:
                    _stdout.write(line)
                    last_line = line
        else:
            subprocess.run((AAPT,) + args)
    except FileNotFoundError:
        _stdout.write("Helper expected AAPT to be located in '")
        _stdout.write(AAPT)
        _stdout.write("' but could not find it.")
        _stdout.write("\n")
        sys.exit("Please make sure the AAPT binary is in the specified path.")
    except (PermissionError, OSError):
        print("Helper could not launch AAPT. Please make sure the following",
              "path is correct and points to an actual AAPT binary:", AAPT,
              "To fix this issue you may need to edit or delete the helper",
              "config file, located at:", _helper.CONFIG)
        sys.exit()


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


def get_devices(_stdout=sys.stdout):
    """Return a list of currently connected devices, as announced by ADB.

    Also update the internal 'DEVICES' tracker with newly connected
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

            unreachable = "{} - {} - Could not be reached! Got status '{}'.\n"

            if device.initialized:
                _stdout.write(unreachable.format(device.info["Product"]["Manufacturer"],
                                                 device.info["Product"]["Model"],
                                                 device_status))
            else:
                _stdout.write(unreachable.format(device_serial, "UNKNOWN DEVICE",
                                                 device_status))
        else:
            device_list.append(device)

    if not device_list:
        _stdout.write("ERROR: No devices found! Check USB connection and try again.\n")

    return device_list


def pick_device(_stdout=sys.stdout):
    """Ask the user to pick which device they want to use. If there are no
    devices to choose from, it will return the sole connected device or None.
    """

    device_list = get_devices()

    if not device_list:
        return None

    if len(device_list) == 1:
        return device_list[0]

    while True:
        _stdout.write("Multiple devices detected!\n")
        _stdout.write("Please choose which of devices below you want to work with.")
        _stdout.write("\n")
        for counter, device in enumerate(device_list):
            _stdout.write(counter + ": ")
            device.print_basic_info()
            _stdout.write("\n")

        user_choice = input("Enter your choice: ").strip()
        if not user_choice.isnumeric():
            _stdout.write("The answer must be a number!\n")
            continue

        user_choice = int(user_choice)

        if user_choice < 0  or user_choice >= len(device_list):
            _stdout.write("Answer must be one of the above numbers!\n")
            continue

        return device_list[user_choice]


class Device:

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


    def adb_command(self, *args, **kwargs):
        """Same as adb_execute(*args), but specific to the given device.
        """

        return adb_execute("-s", self.serial, *args, **kwargs)


    def shell_command(self, *args, **kwargs):
        """Same as adb_execute(["shell", *args]), but specific to the given
        device.
        """

        return adb_execute("-s", self.serial, "shell", *args, **kwargs)


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


    def _get_prop_info(self):
        """Extract all manner of different info from Android's property list."""
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


    def _get_shell_env(self):
        """Extract information from Android's shell environment"""
        #TODO: Extract information from Android shell
        #shell_env = self.shell_command("printenv", return_output=True,
        #                               as_list=False)
        primary_storage_paths = ["/mnt/sdcard", # this is a safe bet (in my experience)
                                 "/storage/emulated", # older androids don't have this one
                                 "/storage/emulated/0",
                                 "/storage/sdcard0",
                                 "/mnt/emmc" # are you a time traveler?
                                ]

        self.ext_storage = primary_storage_paths[0]


    def print_full_info(self, _stdout=sys.stdout):
        """Print all information contained in device.info onto the screen."""
        indent = 4

        for info_category in self.info:
            _stdout.write(info_category + ":")
            _stdout.write("\n")

            for info_name, prop in self.info[info_category].items():
                if prop is None:
                    prop = "Unknown"
                _stdout.write(indent*" " + info_name + ": " + prop)
                _stdout.write("\n")


    def print_basic_info(self, _stdout=sys.stdout):
        """Print basic device information to console.
        Prints: manufacturer, model, OS version and available texture
        compression types.
        """
        _stdout.write(self.info["Product"]["Manufacturer"] + " - ")
        _stdout.write(self.info["Product"]["Model"] + " - ")
        _stdout.write(self.info["OS"]["Android Version"])
        _stdout.write("\n")
        _stdout.write("Compression Types: " + self.info["GPU"]["Compression Types"])
        _stdout.write("\n")


def get_app_name(apk_file):
    """Extract app name of the provided apk, from its manifest file.
    Return name if it is found, an empty string otherwise.
    """
    app_dump = aapt_execute("dump", "badging", apk_file, return_output=True,
                            as_list=False)
    app_name = re.search("(?<=name=')[^']*", app_dump)

    if app_name:
        return app_name.group()

    return ""


def install(device, items, _stdout=sys.stdout):
    """Install apps.
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
        _stdout.write("APK ambiguity! Only one apk file can be installed when also pushing obb files!\n")
        return False

    if not app_list:
        _stdout.write("No APK found among provided files, aborting!\n")
        return False

    if not obb_list:
        app_failure = []
        for app in app_list:
            app_name = get_app_name(app)

            _stdout.write("\nBEGINNING INSTALLATION: " + app_name + "\n")
            _stdout.write("Your device may ask you to confirm this!\n")

            if not install_apk(device, app, app_name):
                _stdout.write("FAILED TO INSTALL: " + app_name + "\n")
                app_failure.append((app_name, app))

            else:
                _stdout.write("SUCCESFULLY INSTALLED: " + app_name + "\n")

        _stdout.write("Installed ")
        _stdout.write(str(len(app_list) - len(app_failure)))
        _stdout.write(" out of " + str(len(app_list)) + "provided apks.\n")

        if app_failure:
            indent = 4
            _stdout.write("The following apks could not be installed:")

            for app_path, app_name in app_failure:
                _stdout.write(indent*" " + Path(app_path).name + " : " + app_name)
                _stdout.write("\n")
    else:
        app = app_list[0]
        app_name = get_app_name(app)

        print("BEGINNING INSTALLATION:", app_name)
        print("Your device may ask you to confirm this!\n")

        if not install_apk(device, app, app_name):
            _stdout.write("FAILED TO INSTALL: " + app_name + "\n")
            return False

        _stdout.write("\nSUCCESSFULLY COPIED AND INSTALLED THE APK FILE\n")
        _stdout.write("\n")
        _stdout.write("BEGINNING COPYING OBB FILE FOR: " + app_name + "\n")

        prepare_obb_dir(device, app_name)
        for obb_file in obb_list:
            if not push_obb(device, obb_file, app_name):
                _stdout.write("OBB COPYING FAILED\n")
                _stdout.write("Failed to copy " + obb_file)
                _stdout.write("\n")
                return False

        _stdout.write("SUCCESSFULLY COPIED ALL FILES TO THEIR DESTINATIONS.\n")
        _stdout.write("Installation complete!\n")


def install_apk(device, apk_file, app_name, _stdout=sys.stdout):
    """Install an app on specified device."""
    preinstall_log = device.shell_command("pm", "list", "packages",
                                          return_output=True, as_list=False)

    if app_name in preinstall_log:
        _stdout.write("Different version of the app already installed, deleting...")
        _stdout.write("\n")
        result = _clean_uninstall(device, target=app_name, app_name=True,
                                  check_packages=False)

        if not result:
            return False

        _stdout.write("Successfully uninstalled" + app_name + "\n")

    device.adb_command("install", "-r", "-i", "com.android.vending",
                       apk_file, _stdout=_stdout)

    postinstall_log = device.shell_command("pm", "list", "packages",
                                           return_output=True)

    for log_line in postinstall_log:
        if app_name in log_line:
            return True

    if device.status != "device":
        _stdout.write(device.info["Product"]["Model"] + "- Device has been suddenly disconnected!")
    else:
        _stdout.write("Installed app was not found by package manager")
        _stdout.write(app_name + "could not be installed!")
        _stdout.write("Please make sure that your device meets app's criteria")
    _stdout.write("\n")
    return False


def prepare_obb_dir(device, app_name):
    """Prepare the obb directory for installation."""
    # pipe the stdout to suppress unnecessary errors
    obb_folder = device.ext_storage + "/Android/obb"
    device.shell_command("rm", "-r", obb_folder + "/" + app_name,
                         return_output=True)
    device.shell_command("mkdir", obb_folder + "/" + app_name,
                         return_output=True)


def push_obb(device, obb_file, app_name, _stdout=sys.stdout):
    """Push <obb_file> to /mnt/sdcard/Android/obb/<your.app.name> on <Device>.

    File is copied to primary storage, and from there to the obb folder. This
    is done in two steps because of write protection of sorts -- attempts to
    'adb push' it directly into obb folder may fail on some devices.
    """
    obb_name = str(Path(obb_file).name)
    obb_target = device.ext_storage + "/Android/obb/" + app_name + "/" + obb_name

    #pushing obb in two steps to circumvent write protection
    device.adb_command("push", obb_file, device.ext_storage + "/" + obb_name)
    device.shell_command("mv", '"' + device.ext_storage + "/" + obb_name + '"',
                         '"' + obb_target + '"')

    push_log = device.shell_command("ls", "\"" + obb_target + "\"",
                                    return_output=True, as_list=False)

    if push_log == obb_target:
        return True

    if device.status != "device":
        _stdout.write("Device has been suddenly disconnected!")
    else:
        _stdout.write("Pushed obb file could not be found in destination folder.")
    _stdout.write("\n")
    return False


def record(device, output=None, _stdout=sys.stdout):
    """Start recording device's screen.
    Recording can be stopped by either reaching the time limit, or pressing
    ctrl+c. After the recording has stopped, the helper confirms that the
    recording has been saved to device's storage and copies it to drive.
    """

    if not "screenrecord" in device.available_commands:
        # it is dependent on Android version, but let's look for command instead
        # just to be safe
        android_ver = device.info["OS"]["Android Version"]
        api_level = device.info["OS"]["Android API Level"]

        _stdout.write("This device's shell does not have the 'screenrecord' command. ")
        _stdout.write("Screenrecord command is available on all devices with Android ")
        _stdout.write("4.4 or higher (API level 19 or higher). Your device has ")
        _stdout.write("Android {} (API level {})".format(android_ver, api_level))
        _stdout.write("\n")
        sys.exit()

    if not output:
        output = "./"

    Path(output).mkdir(exist_ok=True)

    filename = "screenrecord_" + strftime("%Y.%m.%d_%H.%M.%S") + ".mp4"
    remote_recording = device.ext_storage + "/" + filename

    filename = device.info["Product"]["Model"] + "_" + filename
    output = str(Path(Path(output).resolve(), filename))

    _stdout.write("Helper will record your device's screen (audio is not captured).")
    _stdout.write("The recording will stop after pressing 'ctrl+c', or if 3 minutes")
    _stdout.write("have elapsed. Recording will be then saved to '" + output + "'.")
    _stdout.write("\n")

    try:
        input("Press enter whenever you are ready to record.\n")
    except KeyboardInterrupt:
        _stdout.write("\nRecording canceled!\n")
        sys.exit()

    try:
        device.shell_command("screenrecord", "--verbose", remote_recording,
                             return_output=False, _stdout=_stdout)
        _stdout.write("\nRecording stopped by device.\n")
    except KeyboardInterrupt:
        _stdout.write("\nRecording stopped.\n")


    # we're waiting for the clip to be fully saved to device's storage
    # there must be a better way of doing this...
    sleep(1)

    recording_log = device.shell_command("ls", remote_recording,
                                         return_output=True, as_list=False)

    if recording_log != remote_recording:
        if device.status != "device":
            _stdout.write("Device has been suddenly disconnected!")
        else:
            _stdout.write("Unexpected error! The file could not be found on device!")
        _stdout.write("\n")

        return False

    device.adb_command("pull", remote_recording, output, return_output=False, _stdout=_stdout)

    if Path(output).is_file():
        return output

    return False


def pull_traces(device, output=None, _stdout=sys.stdout):
    """Copy contents of the 'traces' into file in the specified folder."""
    if output is None:
        output = Path()
    else:
        output = Path(output)

    output.mkdir(exist_ok=True)

    anr_filename = "".join([device.info["Product"]["Model"], "_anr_",
                            strftime("%Y.%m.%d_%H.%M.%S"), ".txt"])

    device.shell_command("cat", device.anr_trace_path, ">",
                         device.ext_storage + "/traces.txt")

    cat_log = device.shell_command("ls", device.ext_storage + "/traces.txt",
                                   return_output=True, as_list=False)

    if cat_log != device.ext_storage + "/traces.txt":
        if device.status != "device":
            _stdout.write("Device has been suddenly disconnected!\n")
        else:
            _stdout.write("Unexpected error! The file could not be found on device!\n")

        return False

    device.adb_command("pull", device.ext_storage + "/traces.txt",
                       str(output / anr_filename))

    if (output / anr_filename).is_file():
        return str((output / anr_filename).resolve())

    if device.status != "device":
        _stdout.write("Device has been suddenly disconnected\n!")
    else:
        _stdout.write("Unexpected error! The file could not copied!\n")

    return False


def _clean_uninstall(device, target, app_name=False, check_packages=True):
    """Uninstall an app from specified device. Target can be an app name or a
    path to apk file -- by default it will check if target is a file, and if so
    it will attempt to extract app name from it. To disable that, set "app_name"
    to True.
    """
    if Path(target).is_file() and not app_name:
        target = get_app_name(target)

    print("> Uninstalling", target, end="... ")
    if check_packages:
        preinstall_log = device.shell_command("pm", "list", "packages",
                                              return_output=True, as_list=False)

        if target not in preinstall_log:
            print("App was not found")
            return False

    uninstall_log = device.adb_command("uninstall", target, return_output=True)

    if uninstall_log[-1] != "Success":
        if device.status != "device":
            print("Device has been suddenly disconnected!")
            return False
        else:
            print("Unexpected error!")
            print(target, "could not be uninstalled!")
            return False

    print("Done!")
    return True


def _clean_remove(device, target, recursive=False):
    """Remove a file from device."""
    command = "rm"
    if recursive:
        command += " -r"

    if " " in target:
        target = '"{}"'.format(target)

    print("> Removing", target, end="... ")

    result = device.shell_command(command, target, return_output=True,
                                  as_list=False).strip()

    if not result:
        if device.status != "device":
            print("Device has been suddenly disconnected!")
            return False

        print("Done!")
        return True
    elif result.lower().endswith("no such file or directory"):
        print("File not found")
        return False
    elif result.lower().endswith("permission denied"):
        print("Permission denied")
        return -1
    else:
        print("Unexpected error, got:")
        print(result)
        return -2


def _clean_replace(device, remote, local):
    """Replace file on device (remote) with the a local one."""
    result = _clean_remove(device, remote)
    if int(result) < 0:
        print("Cannot replace", remote, "due to unexpected error")
        return False

    print("> Placing", local, "in its place")
    device.adb_command("push", local, remote)

    _remote = remote
    if " " in _remote:
        _remote = '"{}"'.format(remote)

    push_log = device.shell_command("ls", _remote, return_output=True,
                                    as_list=False)

    if push_log != remote:
        if device.status != "device":
            print("Device has been suddenly disconnected!")
        else:
            print("Unexpected error! The file could not be found on device!")

        return False

    print("Done!")
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


def parse_cleaner_config(config=CLEANER_CONFIG, _stdout=sys.stdout):
    """Parse the provided cleaner_config file. If no file is provided, parse
    the default config file.

    Return tuple containing parsed config (dict) and bad config (list). The
    former can be passed toclean().
    """
    parsed_config = {}
    bad_config = ""

    for count, line in enumerate(open(config, mode="r").readlines()):
        if line.startswith("#") or not line.strip():
            continue

        count += 1 # start from 1 not 0

        pair = line.split(":", maxsplit=1)
        if len(pair) != 2:
            bad_config += "Line " + str(count) + " - " + "No value\n"
            continue

        key = pair[0].strip()
        value = pair[1].strip()

        if key not in CLEANER_OPTIONS:
            bad_config += "Line " + str(count) + " - " + "Unknown command\n"
            continue

        if not value:
            bad_config  += "Line " + str(count) + " - " + "No value\n"
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
            bad_config += "Line " + str(count) +": "
            bad_config += "Expected " + expected + " arguments "
            bad_config += "but got " + got + "\n"
            continue

        parsed_config[key].append(items)

    return (parsed_config, bad_config)


def clean(device, config=CLEANER_CONFIG, parsed_config=None, force=False,
          _stdout=sys.stdout):
    """Clean the specified device, as"""
    # TODO: Count the number of removed files / apps
    bad_config = ""

    if not parsed_config:
        parsed_config, bad_config = parse_cleaner_config(config=config)

    if bad_config:
        _stdout.write("Errors encountered in the config file ")
        _stdout.write("(" + config + "):\n")
        _stdout.write(bad_config)
        _stdout.write("Aborting cleaning!\n")
        return False

    if not parsed_config:
        _stdout.write("Empty config! Cannot clean!\n")
        return False

    # Ask user to confirm cleaning
    if not force:
        _stdout.write("The following actions will be performed:\n")
        indent = 2
        for key, action in [("remove", "remove"),
                            ("remove_recursive", "remove"),
                            ("uninstall", "uninstall")]:

            if key not in parsed_config:
                continue

            for item in parsed_config[key]:
                _stdout.write(str(action) + " : " + str(item) + "\n")

        if "replace" in parsed_config:
            _stdout.write("\n")
            for pair in parsed_config["replace"]:
                _stdout.write("The file: " + pair[0] + "\n")
                _stdout.write(indent * " " + "will be replaced with:" + "\n")
                _stdout.write(indent * 2 * " " + pair[1] + "\n")

        _stdout.write("\n")
        _stdout.write("Continue?\n")

        while True:
            usr_choice = input("Y/N : ").strip().upper()
            if usr_choice == "N":
                _stdout.write("Cleaning canceled!\n")
                return False
            elif usr_choice == "Y":
                break

    for option, items in parsed_config.items():
        for value in items:
            CLEANER_OPTIONS[option][0].__call__(device, *value,
                                                *CLEANER_OPTIONS[option][2])
