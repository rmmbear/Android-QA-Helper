""""""
import re
import sys
from collections import OrderedDict

import helper as helper_

ABI_TO_ARCH = helper_.ABI_TO_ARCH
ADB = helper_.ADB


def adb_command(*args, check_server=True, **kwargs):
    """Execute an ADB command, and return -- or don't -- its result.

    If check_server is true, function will first make sure that an ADB
    server is available before executing the command.
    """
    try:
        if check_server:
            helper_.exe(ADB, "start-server", return_output=True)

        return helper_.exe(ADB, *args, **kwargs)
    except FileNotFoundError:
        print("".join(["Helper expected ADB to be located in '", ADB,
                       "' but could not find it.\n"]))
        sys.exit("Please make sure the ADB binary is in the specified path.")
    except (PermissionError, OSError):
        print(
            " ".join(["Helper could not launch ADB. Please make sure the",
                      "following path is correct and points to an actual ADB",
                      "binary:", ADB, "To fix this issue you may need to edit",
                      "or delete the helper config file, located at:",
                      helper_.CONFIG]))
        sys.exit()


def _get_devices(stdout_=sys.stdout):
    """Return a list of tuples with serial number and status, for all
    connected devices.
    """
    device_list = []

    device_specs = adb_command("devices", return_output=True)
    # Check for unexpected output
    # if such is detected, print it and return an empty list
    if device_specs:
        first_line = device_specs.pop(0).strip()
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
    """Return a list of device objects for currently connected devices.
    """
    device_list = []

    for device_serial, device_status in _get_devices(stdout_=stdout_):
        if device_status != "device":
            # device suddenly disconnected or usb debugging not authorized

            unreachable = "{} - {} - Could not be reached! Got status '{}'.\n"

            stdout_.write(unreachable.format(device_serial, "UNKNOWN DEVICE",
                                             device_status))
            continue

        stdout_.write("".join(["Device with serial id '", device_serial,
                               "' connected\n"]))
        device = Device(device_serial, device_status)
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
    device_list = get_devices(stdout_=stdout_)

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
    """Class representing a physical Android device."""
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
        """Same as adb_command(*args), but specific to the given device.
        """
        return adb_command("-s", self.serial, *args, **kwargs)


    def shell_command(self, *args, **kwargs):
        """Same as adb_command(["shell", *args]), but specific to the
        given device.
        """
        return adb_command("-s", self.serial, "shell", *args, **kwargs)


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
        for identifier, name in helper_.COMPRESSION_TYPES.items():
            if identifier in dump:
                compressions.append(name.strip())

        if not self.info["GPU"]["GL Extensions"]:
            self.info["GPU"]["GL Extensions"] = OrderedDict()

        self.info["GPU"]["GL Extensions"] = ", ".join(compressions)


    def _get_shell_env(self):
        """Extract information from Android's shell environment"""
        #TODO: Extract information from Android shell
        shell_env = self.shell_command("printenv", return_output=True,
                                       as_list=False).strip()

        env_dict = {}
        for line in shell_env:
            line = line.split("=", maxsplit=1)
            if len(line) == 1:
                continue
            env_dict[line[0]] = line[1]

        # find the path of the primary storage
        primary_storage = None
        if "EXTERNAL_STORAGE" in env_dict:
            if self.is_dir(env_dict["EXTERNAL_STORAGE"], check_write=True):
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
                if self.is_dir(storage_path, check_write=True):
                    primary_storage = storage_path

        self.ext_storage = primary_storage
        # TODO: search for secondary storage path
        # TODO: search for hostname
        # TODO: decide how to handle situations in which no storage is found


    def is_type(self, file_path, file_type, symlink_ok=False, check_read=True,
                check_write=False, check_execute=False):
        """Check whether a path points to an existing file that matches
        the specified type and whether the current user has specified
        permissions.

        You can check for read, write and execute permissions, by
        setting the respective check_* arguments to True. Function will
        return True only if all specified permissions are available and
        if the path does not point to a symlink or symlink_ok is set to
        True.

        check_read is True by default.
        """
        if not file_path:
            file_path = "."

        permissions = ""
        if check_read:
            permissions += "r"
        if check_write:
            permissions += "w"
        if check_execute:
            permissions += "x"

        out = self.shell_command(
            'if [ -{} "{}" ];'.format(file_type, file_path), "then echo 0;",
            "else echo 1;", "fi", return_output=True, as_list=False).strip()

        if out == '0':
            for permission in permissions:
                out = self.shell_command(
                    'if [ -{} "{}" ];'.format(permission, file_path),
                    "then echo 0;", "else echo 1;", "fi", return_output=True,
                    as_list=False).strip()

                if out == '0':
                    continue
                if out not in ["0", "1"]:
                    print("Got unexpected output while checking for '",
                          permission, "' permission in file", file_path)
                    print("Output:", [out])
                return False

            out = self.shell_command('if [ -L "{}" ];'.format(file_path),
                                     "then echo 0;", "else echo 1;", "fi",
                                     return_output=True, as_list=False).strip()
            if out == '1' or symlink_ok:
                return True

        if out.strip() not in ["0", "1"]:
            print("Got unexpected output while checking for '", file_type,
                  "' type of file", file_path)
            print("Output:", [out])
            return False
        return False


    def is_file(self, file_path, **kwargs):
        """Check whether a path points to an existing directory and
        whether the current user has specified permissions.

        You can check for read, write and execute permissions, by
        setting the respective check_* arguments to True. Function will
        return True only if all specified permissions are available and
        if the path does not point to a symlink or symlink_ok is set to
        True.

        check_read is True by default.
        """
        return self.is_type(file_path=file_path, file_type="f", **kwargs)


    def is_dir(self, file_path, **kwargs):
        """Check whether a path points to an existing directory and
        whether the current user has specified permissions.

        You can check for read, write and execute permissions, by
        setting the respective check_* arguments to True. Function will
        return True only if all specified permissions are available and
        if the path does not point to a symlink or symlink_ok is set to
        True.

        check_read is True by default.
        """
        return self.is_type(file_path=file_path, file_type="d", **kwargs)


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


class InfoSpec:
    """"""
    __slots__ = ('var_name', 'var_dict_1', 'var_dict_2', 'extraction_commands',
                 'resolve_multiple_values', 'resolve_existing_values',
                 'post_extraction_commands')
    def __init__(self, var_name, var_dict_1=None, var_dict_2=None,
                 extraction_commands=((),), post_extraction_commands=None,
                 resolve_multiple_values='merge', resolve_existing_values='merge'):
        """"""
        self.var_name = var_name
        self.var_dict_1 = var_dict_1
        self.var_dict_2 = var_dict_2

        self.extraction_commands = extraction_commands
        self.post_extraction_commands = post_extraction_commands
        self.resolve_multiple_values = resolve_multiple_values
        self.resolve_existing_values = resolve_existing_values


    def get_info_variable_container(self, device):
        """Return dictionary object that is supposed to contain the
        extracted info value.
        """
        container = device.__dict__
        for name in (self.var_dict_2, self.var_dict_1):
            if not name:
                continue
            try:
                container = container[name]
            except KeyError:
                container[name] = {}
                container = container[name]

        return container


    def can_run(self, device):
        """Check if value can be assigned to info container"""
        try:
            exists = bool(self.get_info_variable_container(device)[self.var_name])
        except KeyError:
            exists = False
        return not (exists and self.resolve_existing_values == 'drop')


    def run(self, device, source):
        """"""
        value_container = self.get_info_variable_container(device)
        try:
            exists = bool(value_container[self.var_name])
        except KeyError:
            exists = False

        extracted = []
        for extraction_strategy in self.extraction_commands:
            # 0 - command, 1 - *args, 2 - **kwargs
            if self.resolve_multiple_values == 'drop' and extracted:
                break

            tmp_extracted = self._extract_value(extraction_strategy, source)
            tmp_extracted = self._format_value(tmp_extracted)
            if not tmp_extracted:
                continue

            if self.resolve_multiple_values == 'replace':
                extracted = [tmp_extracted]
            else:
                extracted.append(tmp_extracted)

        if extracted:
            if len(extracted) > 1:
                extracted = ", ".join(extracted)
            else:
                extracted = extracted[0]

            if exists and self.resolve_existing_values == "merge":
                value_container[self.var_name] += ", " + extracted
            else:
                value_container[self.var_name] = extracted


    def _extract_value(self, extraction_command, source):
        """"""
        if not extraction_command:
            return source

        self_kwargs = {"$group":0}

        try:
            args = list(extraction_command[1])
        except IndexError:
            args = []

        while '$source' in args:
            args[args.index('$source')] = source
        try:
            kwargs = extraction_command[2]
        except IndexError:
            kwargs = ()

        for pair in kwargs:
            while "$source" in pair:
                pair[pair.index('$source')] = source

        kwargs = dict(kwargs)
        for var in self_kwargs:
            if var in kwargs:
                self_kwargs[var] = kwargs.pop(var)

        extracted_value = extraction_command[0](*args, **kwargs)
        if extraction_command[0] == re.search and extracted_value:
            extracted_value = extracted_value.group(self_kwargs['$group'])

        return extracted_value


    def _format_value(self, extracted_value):
        """"""
        if not self.post_extraction_commands:
            try:
                return extracted_value.strip()
            except AttributeError:
                return extracted_value
        if not extracted_value:
            return ''

        for formatting_commands in self.post_extraction_commands:
            # 0 - command, 1 - *args, 2 - **kwargs
            args = list(formatting_commands[2])
            while '$extracted' in args:
                args[args.index('$extracted')] = extracted_value
            try:
                kwargs = formatting_commands[3]
            except IndexError:
                kwargs = dict()

            for pair in kwargs:
                while "$extracted" in pair:
                    pair[pair.index('$extracted')] = extracted_value

            try:
                if formatting_commands[0] == "function":
                    extracted_value = formatting_commands[1](*args, **kwargs)

                else:
                    extracted_value = extracted_value.__getattribute__(formatting_commands[1])(*args, **kwargs)
            except ValueError:
                extracted_value = ''

            if not extracted_value:
                return None

        return extracted_value
