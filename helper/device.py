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


def abi_to_arch(abi):
    if abi not in ABI_TO_ARCH:
        return "Unknown ({})".format(abi)

    return ABI_TO_ARCH[abi]


def extract_gles_extensions(surfaceflinger_dump):
    extensions = []
    for identifier, name in helper_.COMPRESSION_TYPES.items():
        if identifier in surfaceflinger_dump:
            extensions.append(name.strip())

    return extensions


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


def get_devices(stdout_=sys.stdout, initialize=True, limit_init=()):
    """Return a list of device objects for currently connected devices.
    """
    device_list = []

    for device_serial, device_status in _get_devices(stdout_=stdout_):
        if device_status != "device":
            # device suddenly disconnected or usb debugging not authorized
            stdout_.write(" ".join(["Device with serial ID", device_serial,
                                    "could not be reached! Got status:",
                                    device_status, "\n"]))
            continue

        stdout_.write("".join(["Device with serial id '", device_serial,
                               "' connected\n"]))
        if initialize:
            device = Device(device_serial, device_status, limit_init)
        else:
            device = Device(device_serial, 'delayed_initialization', limit_init)
        device_list.append(device)

    if not device_list:
        stdout_.write(
            "ERROR: No devices found! Check USB connection and try again.\n")
    return device_list


def pick_device(stdout_=sys.stdout, initialize=True, limit_init=()):
    """Ask the user to pick a device from list of currently connected
    devices. If there are no devices to choose from, it will return the
    sole connected device or None, if there are no devices at all.
    """
    device_list = get_devices(stdout_, initialize, limit_init)

    if not device_list:
        return None

    if len(device_list) == 1:
        return device_list[0]

    while True:
        stdout_.write("Multiple devices detected!\n")
        stdout_.write(
            "Please choose which of devices below you want to work with.\n")
        for counter, device in enumerate(device_list):
            stdout_.write(" ".join([counter, ":"]))
            device.print_basic_info(stdout_)

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
    def __init__(self, serial, status='offline', limit_init=()):
        """"""
        self.serial = serial
        self.limit_init = limit_init

        self.ext_storage = None
        self.anr_trace_path = None
        self.available_commands = ()
        self._info = OrderedDict()

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
            ("CPU",     ["Chipset and Type",
                         "Cores",
                         "Architecture",
                         "Max Frequency",
                         "Available ABIs"]),
            ("GPU",     ["Model",
                         "GL Version",
                         "Texture Types"]),
            ("Display", ["Resolution",
                         "Density",
                         "X-DPI",
                         "Y-DPI"])
            ]

        for pair in info:
            props = OrderedDict()
            for prop in pair[1]:
                props[prop] = list()

            self._info[pair[0]] = props

        self.initialized = False
        self._status = status

        if self._status == "device":
            self.device_init()


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
            if self.serial in device_specs:
                self._status = device_specs[1]
                return self._status

        self._status = "Offline"
        return self._status


    def device_init(self):
        """Gather all the information."""
        if self.status == "device":
            for info_source, info_specs in INFO_EXTRACTION_CONFIG.items():
                if self.limit_init and info_source[-1] not in self.limit_init:
                    continue
                try:
                    args = info_source[0]
                except IndexError:
                    args = ()
                try:
                    kwargs = dict(info_source[1])
                except IndexError:
                    kwargs = {}

                source_output = None

                for info_object in info_specs:
                    if info_object.can_run(self):
                        if not source_output:
                            source_output = self.shell_command(*args, **kwargs)

                        info_object.run(self, source_output)

            self.initialized = True


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


    def reconnect(self, stdout_=sys.stdout):
        self.adb_command("reconnect")
        reconnect_status = self.adb_command("wait-for-device",
                                            return_output=True, as_list=False)
        if reconnect_status:
            # I have not seen the 'wait-for-<status>' command output anything ever
            # so this is a precaution in case it ever will
            stdout_.write(reconnect_status + "\n")
            return False

        return True


    def get_full_info_string(self, indent=4):
        """Return a formatted string containing all device info"""
        info_string = []

        indent = indent * " "

        for info_category in self._info:
            info_string.append(info_category + ": ")

            if isinstance(self._info[info_category], list):
                print(self._info[info_category])
                info_string.append(
                    indent + ("\n" + indent).join(self._info[info_category][0]))
                continue
            else:
                for info_name, prop in self._info[info_category].items():
                    if not prop:
                        prop = "Unknown"
                    prop_line = [indent, info_name, ": "]
                    prop_line.extend(prop)

                    info_string.append("".join(prop_line))

        return "\n".join(info_string)


    def print_full_info(self, stdout_=sys.stdout):
        """Print all information from device._info onto screen."""
        stdout_.write(self.get_full_info_string() + "\n")


    def print_basic_info(self, stdout_=sys.stdout):
        """Print basic device information to console.
        Prints: manufacturer, model, OS version and available texture
        compression types.
        """
        model = self._info["Product"]["Model"]
        if not model:
            model = "Unknown model"

        manufacturer = self._info["Product"]["Manufacturer"]
        if manufacturer is None:
            manufacturer = "Unknown manufacturer"

        os_ver = self._info["OS"]["Android Version"]
        if os_ver is None:
            os_ver = "Unknown OS version"

        line1 = " - ".join([manufacturer, model, os_ver]) + "\n"
        line2 = ("Texture compression types: "
                 + str(self._info["GPU"]["Texture Types"])
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
            if exists and self.resolve_existing_values in ("append", "prepend"):
                # check if the extracted info is redundant
                #if extracted.lower() in value_container[self.var_name].lower():
                #    return
                # check if extracted info is more verbose than the existing value
                #if value_container[self.var_name].lower() in extracted.lower():
                #    value_container[self.var_name] = extracted

                if self.resolve_existing_values == "append":
                    value_container[self.var_name].extend(extracted)
                else:
                    value_container[self.var_name] = extracted.extend(value_container[self.var_name])
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
        if extracted_value is None:
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


INFO_EXTRACTION_CONFIG = {
    (("getprop",), (("as_list", False), ("return_output", True)), "getprop") : (
        InfoSpec(extraction_commands=((re.search, ('(?<=\\[ro\\.product\\.name\\]: \\[).*(?=\\])', '$source')),), var_name='Name', var_dict_1='Product', var_dict_2='_info'),
        InfoSpec(extraction_commands=((re.search, ('(?<=\\[ro\\.product\\.model\\]: \\[).*(?=\\])', '$source')),), var_name='Model', var_dict_1='Product', var_dict_2='_info'),
        InfoSpec(extraction_commands=((re.search, ('(?<=\\[ro\\.product\\.brand\\]: \\[).*(?=\\])', '$source')),), var_name='Brand', var_dict_1='Product', var_dict_2='_info'),
        InfoSpec(extraction_commands=((re.search, ('(?<=\\[ro\\.product\\.device\\]: \\[).*(?=\\])', '$source')),), var_name='Device', var_dict_1='Product', var_dict_2='_info'),
        InfoSpec(extraction_commands=((re.search, ('(?<=\\[ro\\.product\\.manufacturer\\]: \\[).*(?=\\])', '$source')),), var_name='Manufacturer', var_dict_1='Product', var_dict_2='_info'),
        InfoSpec(extraction_commands=((re.search, ('(?<=\\[ro\\.sf\\.lcd_density\\]: \\[).*(?=\\])', '$source')),), var_name='Density', var_dict_1='Display', var_dict_2='_info'),
        InfoSpec(extraction_commands=((re.search, ('(?<=\\[ro\\.build\\.id\\]: \\[).*(?=\\])', '$source')),), var_name='Build ID', var_dict_1='OS', var_dict_2='_info'),
        InfoSpec(extraction_commands=((re.search, ('(?<=\\[ro\\.build\\.version\\.sdk\\]: \\[).*(?=\\])', '$source')),), var_name='API Level', var_dict_1='OS', var_dict_2='_info'),
        InfoSpec(extraction_commands=((re.search, ('(?<=\\[ro\\.build\\.version\\.release\\]: \\[).*(?=\\])', '$source')),), var_name='Version', var_dict_1='OS', var_dict_2='_info'),
        InfoSpec(extraction_commands=((re.search, ('(?<=\\[ro\\.build\\.fingerprint\\]: \\[).*(?=\\])', '$source')),), var_name='Build Fingerprint', var_dict_1='OS', var_dict_2='_info'),
        InfoSpec(extraction_commands=((re.search, ('(?<=\\[ro\\.board\\.platform\\]: \\[).*(?=\\])', '$source')),), var_name='Chipset and Type', var_dict_1='CPU', var_dict_2='_info', resolve_multiple_values='merge'),
        InfoSpec(extraction_commands=((re.search, ('(?<=\\[ro\\.product\\.cpu\\.abi\\]: \\[).*(?=\\])', '$source')),), var_name='Architecture', var_dict_1='CPU', var_dict_2='_info', post_extraction_commands=(('function', abi_to_arch, ('$extracted',)),)),
        # accommodate for device that only have two abis and abilist is not available in getprop
        InfoSpec(extraction_commands=((re.search, ('(?<=\\[ro\\.product\\.cpu\\.abi\\]\\: \\[).*(?=\\])', '$source')), (re.search, ('(?<=\\[ro\\.product\\.cpu\\.abi2\\]\\: \\[).*(?=\\])', '$source'))), var_name='Available ABIs', var_dict_1='CPU', var_dict_2='_info', resolve_multiple_values='merge'),
        # replace the above info if abilist is available
        InfoSpec(extraction_commands=((re.search, ('(?<=\\[ro\\.product\\.cpu\\.abilist\\]\\: \\[).*(?=\\])', '$source')),), var_name='Available ABIs', var_dict_1='CPU', var_dict_2='_info', resolve_existing_values='replace', post_extraction_commands=(('method', 'replace', (',', ', ')), ('method', 'replace', ('  ', ' ')))),
        InfoSpec(extraction_commands=((re.search, ('(?<=\\[dalvik\\.vm\\.stack\\-trace\\-file\\]: \\[).*(?=\\])', '$source')),), var_name='anr_trace_path'),
    ),
    (("dumpsys", "SurfaceFlinger"), (("as_list", False), ("return_output", True)), "surfaceflinger_dump"): (
        InfoSpec(extraction_commands=((re.search, ('(?<=GLES: ).*(?=\\,)', '$source')),), var_name='Model', var_dict_1='GPU', var_dict_2='_info'),
        InfoSpec(extraction_commands=((re.search, ('(?<=GLES: )(?:[^\\,]+\\,){2}(.*)', '$source'), (('$group', 1),)),), var_name='GL Version', var_dict_1='GPU', var_dict_2='_info'),
        InfoSpec(extraction_commands=((re.search, ('(?<=x-dpi).*', '$source')),), var_name='X-DPI', var_dict_1='Display', var_dict_2='_info', post_extraction_commands=(('method', 'strip', (' :\t',)),)),
        InfoSpec(extraction_commands=((re.search, ('(?<=y-dpi).*', '$source')),), var_name='Y-DPI', var_dict_1='Display', var_dict_2='_info', post_extraction_commands=(('method', 'strip', (' :\t',)),)),
        InfoSpec(extraction_commands=((re.search, ('(?<=Display\\[0\\] :)[^,]*', '$source')),), var_name='Resolution', var_dict_1='Display', var_dict_2='_info', post_extraction_commands=(('method', 'strip', (' :\t',)),)),
        InfoSpec(var_name='Texture Types', var_dict_1='GPU', var_dict_2='_info', post_extraction_commands=(('function', extract_gles_extensions, ('$extracted',)), ('function', ', '.join, ('$extracted',)))),
    ),
    (("cat", "/proc/cpuinfo"), (("as_list", False), ("return_output", True)), "cpuinfo"): (
        InfoSpec(extraction_commands=((re.search, ('(?<=Hardware).*', '$source')),), var_name='Chipset and Type', var_dict_1='CPU', var_dict_2='_info', post_extraction_commands=(('method', 'strip', (' :\t',)),)),
        InfoSpec(extraction_commands=((re.search, ('(?<=model name).*', '$source')), (re.search, ('(?<=Processor).*', '$source'))), var_name='Chipset and Type', var_dict_1='CPU', var_dict_2='_info', resolve_multiple_values='drop', post_extraction_commands=(('method', 'strip', (' :\t',)),)),

    ),
    (("cat", "/sys/devices/system/cpu/cpu0/cpufreq/cpuinfo_max_freq"), (("as_list", False), ("return_output", True)), "cpu_freq"): (
        InfoSpec(var_name='Max Frequency', var_dict_1='CPU', var_dict_2='_info', post_extraction_commands=(('function', int, ('$extracted',)), ('method', '__floordiv__', (1000,)), ('function', str, ('$extracted',)), ('method', "__add__", (' MHz',)))),
    ),
    (("cat", "/sys/devices/system/cpu/possible"), (("as_list", False), ("return_output", True)), "cpu_cores"): (
        InfoSpec(extraction_commands=((re.search, ('(?<=-).*', '$source')), (re.search, ('.*', '$source'))), var_name='Cores', var_dict_1='CPU', var_dict_2='_info', resolve_multiple_values='drop', post_extraction_commands=(('function', lambda x: int(x) + 1, ('$extracted',)), ('function', str, ('$extracted',)))),
    ),
    (("cat", "/proc/meminfo"), (("as_list", False), ("return_output", True)), "meminfo") : (
        InfoSpec(extraction_commands=((re.search, ('(?<=^MemTotal:)[^A-z]*', '$source')),), var_name='Total', var_dict_1='RAM', var_dict_2='_info', post_extraction_commands=(('function', int, ('$extracted',)), ('method', '__floordiv__', (1024,)), ('function', str, ('$extracted',)), ('method', '__add__', (' MB',)))),
    ),
    (("printenv",), (('as_list', False), ("return_output", True)), "shell_environment") :(
        InfoSpec(extraction_commands=((re.search, ('(?<=EXTERNAL_STORAGE=).*', '$source')),), var_name="ext_storage"),
        InfoSpec(extraction_commands=((re.search, ('(?<=SECONDARY_STORAGE=).*', '$source')),), var_name="secondary_storage")
    ),
    (("ls", "/system/bin"), (('as_list', True), ("return_output", True)), "available_commands") :(
        InfoSpec(var_name='available_commands', resolve_existing_values='replace'),
    ),
    (("pm", "list", "features"), (('as_list', False), ("return_output", True)), "device_features") :(
        InfoSpec(extraction_commands=((re.search, ('(?<=feature:)android.hardware.bluetooth', '$source')),), var_name="Bluetooth", var_dict_1='Notable Features', var_dict_2='_info', post_extraction_commands=(('function', str, (u"\u2714",)),)),
        InfoSpec(extraction_commands=((re.search, ('(?<=feature:)android.hardware.bluetooth_le', '$source')),), var_name="Bluetooth Low Energy", var_dict_1='Notable Features', var_dict_2='_info', post_extraction_commands=(('function', str, (u"\u2714",)),)),
        InfoSpec(extraction_commands=((re.search, ('(?<=feature:)android.hardware.consumerir', '$source')),), var_name="Infrared", var_dict_1='Notable Features', var_dict_2='_info', post_extraction_commands=(('function', str, (u"\u2714",)),)),
        InfoSpec(extraction_commands=((re.search, ('(?<=feature:)android.hardware.fingerprint', '$source')),), var_name="Fingerprint Scanner", var_dict_1='Notable Features', var_dict_2='_info', post_extraction_commands=(('function', str, (u"\u2714",)),)),
        InfoSpec(extraction_commands=((re.search, ('(?<=feature:)android.software.freeform_window_management', '$source')),), var_name="Freeform Window Management", var_dict_1='Notable Features', var_dict_2='_info', post_extraction_commands=(('function', str, (u"\u2714",)),)),
        InfoSpec(extraction_commands=((re.search, ('(?<=feature:)android.hardware.nfc', '$source')),), var_name="NFC", var_dict_1='Notable Features', var_dict_2='_info', post_extraction_commands=(('function', str, (u"\u2714",)),)),
        InfoSpec(extraction_commands=((re.search, ('(?<=feature:)android.hardware.telephony.cdma', '$source')),), var_name="CDMA Telephony", var_dict_1='Notable Features', var_dict_2='_info', post_extraction_commands=(('function', str, (u"\u2714",)),)),
        InfoSpec(extraction_commands=((re.search, ('(?<=feature:)android.hardware.telephony.gsm', '$source')),), var_name="GSM Telephony", var_dict_1='Notable Features', var_dict_2='_info', post_extraction_commands=(('function', str, (u"\u2714",)),)),
        InfoSpec(extraction_commands=((re.search, ('(?<=feature:)android.hardware.vr.headtracking', '$source')),), var_name="VR Headtracking", var_dict_1='Notable Features', var_dict_2='_info', post_extraction_commands=(('function', str, (u"\u2714",)),)),
        InfoSpec(extraction_commands=((re.search, ('(?<=feature:)android.software.vr.mode', '$source')),), var_name="VR Mode", var_dict_1='Notable Features', var_dict_2='_info', post_extraction_commands=(('function', str, (u"\u2714",)),)),
        InfoSpec(extraction_commands=((re.search, ('(?<=feature:)android.hardware.vr.high_performance', '$source')),), var_name="High-Performance VR Mode", var_dict_1='Notable Features', var_dict_2='_info', post_extraction_commands=(('function', str, (u"\u2714",)),)),
        InfoSpec(extraction_commands=((re.search, ('(?<=feature:)android.hardware.wifi.aware', '$source')),), var_name="WiFi-Aware", var_dict_1='Notable Features', var_dict_2='_info', post_extraction_commands=(('function', str, (u"\u2714",)),)),
        InfoSpec(extraction_commands=((re.findall, ('(?<=feature:).*', '$source')),), var_name='device_features', var_dict_1='_info'),
    ),
    (("wm", "size"), (('as_list', False), ("return_output", True)), "screen_size") :(
        InfoSpec(extraction_commands=((re.search, ('(?<=Physical size:).*', '$source')),), var_name='Resolution', var_dict_1='Display', var_dict_2='_info', resolve_existing_values='drop'),
    ),
    (("wm", "density"), (('as_list', False), ("return_output", True)), "screen_density") :(
        InfoSpec(extraction_commands=((re.search, ("(?<=Physical density:).*", '$source')),), var_name='Density', var_dict_1='Display', var_dict_2='_info', resolve_existing_values='drop'),
    ),
}
