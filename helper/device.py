""""""
import re
import sys
from pathlib import Path
from collections import OrderedDict

import helper as helper_
import helper.apk as apk_

def _load_known_compressions():
    with open(helper_.COMPRESSION_DEFINITIONS, mode="r", encoding="utf-8") as comps:
        for line in comps.read().splitlines():
            if not line or line.startswith("#"):
                continue

            name, comp_id = line.split("=", maxsplit=1)
            KNOWN_COMPRESSION_NAMES[comp_id] = name.strip()


ABI_TO_ARCH = helper_.ABI_TO_ARCH
ADB = helper_.ADB

KNOWN_COMPRESSION_NAMES = {}
_load_known_compressions()


def adb_command(*args, check_server=True, stdout_=sys.stdout, **kwargs):
    """Execute an ADB command, and return -- or don't -- its result.

    If check_server is true, function will first make sure that an ADB
    server is available before executing the command.
    """
    try:
        if check_server:
            helper_.exe(ADB, "start-server", return_output=True)

        return helper_.exe(ADB, *args, **kwargs)
    except FileNotFoundError:
        stdout_.write("".join(["Helper expected ADB to be located in '", ADB,
                               "' but could not find it.\n"]))
        sys.exit()
    except (PermissionError, OSError):
        stdout_.write(
            " ".join(["Helper could not launch ADB. Please make sure the",
                      "following path is correct and points to an actual ADB",
                      "binary:", ADB, "To fix this issue you may need to edit",
                      "or delete the helper config file, located at:",
                      helper_.CONFIG]))
        sys.exit()


def abi_to_arch(abi):
    """"""
    if abi not in ABI_TO_ARCH:
        return "Unknown ({})".format(abi)

    return ABI_TO_ARCH[abi]


def extract_compression_names(surfaceflinger_dump):
    """"""
    extensions = []
    for identifier, name in KNOWN_COMPRESSION_NAMES.items():
        if identifier in surfaceflinger_dump:
            extensions.append(name)

    return extensions


def _get_devices(stdout_=sys.stdout):
    """Return a list of tuples with serial number and status, for all
    connected devices.
    """
    device_list = []

    device_specs = adb_command("devices", return_output=True, as_list=True)
    # Check for unexpected output
    # if such is detected, print it and return an empty list
    if device_specs:
        first_line = device_specs.pop(0).strip()
        if first_line.lower() != "list of devices attached":
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


def get_devices(initialize=True, limit_init=()):
    """Return a list of device objects for currently connected devices.
    """
    device_list = []

    for device_serial, device_status in _get_devices():
        if device_status != "device":
            # device suddenly disconnected or usb debugging not authorized
            continue

        if initialize:
            device = Device(device_serial, device_status, limit_init)
        else:
            device = Device(device_serial, 'delayed_initialization', limit_init)
        device_list.append(device)
    return device_list


class Device:
    """Class representing a physical Android device."""
    def __init__(self, serial, status='offline', limit_init=()):
        """"""
        self.serial = serial
        self._extracted_info_groups = []

        self.ext_storage = None
        self.secondary_storage = None
        self.anr_trace_path = None

        self.installed_apps = ()
        self.device_features = ()
        self.available_commands = ()

        self._info = OrderedDict()

        info = [
            ("Product", [
                "Model",
                "Name",
                "Manufacturer",
                "Brand",
                "Device"]),
            ("OS", [
                "Version",
                "API Level",
                "Build ID",
                "Build Fingerprint"]),
            ("RAM", [
                "Total"]),
            ("CPU", [
                "Chipset and Type",
                "Cores",
                "Architecture",
                "Max Frequency",
                "Available ABIs"]),
            ("GPU", [
                "Model",
                "GL Version",
                "Texture Types"]),
            ("Display", [
                "Resolution",
                "Density",
                "X-DPI",
                "Y-DPI"]),
            ("Notable Features", [
                "Bluetooth",
                "Bluetooth Low Energy",
                "InfraRed",
                "NFC"]),
            ]

        for pair in info:
            props = OrderedDict()
            for prop in pair[1]:
                props[prop] = list()

            self._info[pair[0]] = props

        self.initialized = False
        self._status = status

        if self._status == "device":
            self.device_init(limit_init)


    def __str__(self):
        """Return device's serial number."""
        return self.serial


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
            else:
                self._status = "Offline"

        return self._status


    def info(self, index1, index2=None):
        """Fetch the string value for the given info ."""
        info_container = self._info[index1]
        if not index2:
            if isinstance(info_container, list):
                return "\n".join(info_container)

            return info_container

        info_container = info_container[index2]
        return ", ".join(info_container)


    def device_init(self, limit_init=(), force_init=False):
        """Gather all the information."""
        if self.status == "device":
            for info_source, info_specs in INFO_EXTRACTION_CONFIG.items():
                source_name = info_source[-1]

                if not force_init and source_name in self._extracted_info_groups:
                    continue

                if limit_init and source_name not in limit_init:
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

                self._extracted_info_groups.append(source_name)

            # This kinda defeats the [urpose of the whole info config thing...
            if isinstance(self.ext_storage, list):
                self.ext_storage = self.ext_storage[0]
            if isinstance(self.secondary_storage, list):
                self.secondary_storage = self.secondary_storage[0]
            if isinstance(self.anr_trace_path, list):
                self.anr_trace_path = self.anr_trace_path[0]


            self.initialized = True


    def is_type(self, file_path, file_type, check_read=True, check_write=False,
                check_execute=False, symlink_ok=False):
        """Check whether a path points to an existing file that matches
        the specified type and whether the current user has the
        specified permissions.

        You can check for read, write and execute acccess by
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

        if out not in ["0", "1"]:
            print("Got unexpected output while checking for '", file_type,
                  "' type of file", file_path)
            print("Output:", [out])
            return False

        if out == '1':
            return False

        for permission in permissions:
            out = self.shell_command(
                'if [ -{} "{}" ];'.format(permission, file_path),
                "then echo 0;", "else echo 1;", "fi", return_output=True,
                as_list=False).strip()

            if out not in ["0", "1"]:
                print("Got unexpected output while checking for '",
                      permission, "' permission in file", file_path)
                print("Output:", [out])

            if out == '1':
                return False

        out = self.shell_command('if [ -L "{}" ];'.format(file_path),
                                 "then echo 0;", "else echo 1;", "fi",
                                 return_output=True, as_list=False).strip()
        if not (out == '1' or symlink_ok):
            return False

        return True


    def is_file(self, file_path, *args, **kwargs):
        """Check whether a path points to an existing file and whether
        the current user has the specified permissions.

        This is the same as calling device.is_type(<path>, "f", ...)
        """
        return self.is_type(file_path, "f", *args, **kwargs)


    def is_dir(self, file_path, *args, **kwargs):
        """Check whether a path points to an existing directory and
        whether the current user has the specified permissions.

        This is the same as calling device.is_type(<path>, "d", ...)
        """
        return self.is_type(file_path, "d", *args, **kwargs)


    def reconnect(self, stdout_=sys.stdout):
        """Restart connection with device.

        Return true when device comes back online.
        """
        self.adb_command("reconnect")
        reconnect_status = self.adb_command("wait-for-device",
                                            return_output=True, as_list=False)
        if reconnect_status:
            # I have not seen the 'wait-for-<status>' command output anything ever
            # so this is a precaution in case it ever will
            stdout_.write(reconnect_status + "\n")
            return False

        return True


    def full_info_string(self, indent=4):
        """Return a formatted string containing all device info"""
        # ensure all required info is available
        self.device_init()

        # if an info source is a key in whitelist, only the asociated values
        # will be returned from that group
        group_whitelist = {}
        indent = indent * " "
        group_list = []
        grouped_vars = {}
        ungrouped_vars = []

        full_info_string = "-----Android QA Helper v.{}-----".format(
            helper_.VERSION)

        for info_category, variables_list in INFO_EXTRACTION_CONFIG.items():
            info_source = info_category[-1]

            for info_variable in variables_list:
                if info_source in group_whitelist and \
                info_variable.var_name not in group_whitelist[info_source]:
                    continue

                if info_variable.var_dict_2 == "_info":
                    if info_variable.var_dict_1 not in group_list:
                        group_list.append(info_variable.var_dict_1)

                    try:
                        value = self.info(info_variable.var_dict_1, info_variable.var_name)
                        if not value:
                            value = "Unknown"
                    except KeyError:
                        value = "Unavailable"

                    line = "".join([info_variable.var_name, " : ", value])

                    if info_variable.var_dict_1 not in grouped_vars:
                        grouped_vars[info_variable.var_dict_1] = []

                    if line in grouped_vars[info_variable.var_dict_1]:
                        continue

                    grouped_vars[info_variable.var_dict_1].append(line)
                elif info_variable.var_dict_1 == "_info":
                    value = self.info(info_variable.var_name)
                    if not value:
                        value = "Unknown"

                    line = "".join([info_variable.var_name, " : ", value])
                    ungrouped_vars.append(line)
                else:
                    if not self.__dict__[info_variable.var_name]:
                        value = "Unknown"
                    else:
                        value = self.__dict__[info_variable.var_name]
                        if isinstance(value, (list, tuple)):
                            value = ", ".join(value)
                        else:
                            value = str(value)

                    line = "".join([info_variable.var_name, " : ", value])
                    ungrouped_vars.append(line)


        for group in group_list:
            full_info_string = "".join([full_info_string, "\n", group, ":\n"])
            for value in grouped_vars[group]:
                full_info_string = "".join([full_info_string, indent, value, "\n"])

        full_info_string += "\n"

        for value in ungrouped_vars:
            full_info_string = "".join([full_info_string, value, "\n"])

        return full_info_string


    def basic_info_string(self):
        """Return formatted string containing basic device information.
        contains: manufacturer, model, OS version and available texture
        compression types.
        """
        # ensure all required data is available
        self.device_init(limit_init=("getprop", "surfaceflinger_dump"))

        model = self.info("Product", "Model")
        if not model:
            model = "Unknown model"

        manufacturer = self.info("Product", "Manufacturer")
        if manufacturer is None:
            manufacturer = "Unknown manufacturer"

        os_ver = self.info("OS", "Version")
        if os_ver is None:
            os_ver = "Unknown OS version"

        line1 = " - ".join([manufacturer, model, os_ver])
        line2 = "".join(["Texture compression types: ",
                         self.info("GPU", "Texture Types")])

        return "\n".join([line1, line2])


    def extract_apk(self, app, out_dir=".", stdout_=sys.stdout):
        """Extract an application's apk file.

        To specify the application, provide either an app name or an
        app object.
        """

        if isinstance(app, apk_.App):
            app_name = app.app_name
        else:
            app_name = app

        if app_name not in self.installed_apps:
            stdout_.write(" ".join([app_name, "not in list of installed apps.\n"]))
            return False

        app_path = self.shell_command(
            "pm", "path", app_name, return_output=True, as_list=False).strip()

        package_line = re.search('(?<=package:).*', app_path)
        if not package_line:
            # this should not happen under normal circumstances
            stdout_.write("ERROR: Got no path from package manager!\n")
            return False

        app_path = package_line.group()

        filename = Path(app_path).name
        out_file = Path(out_dir, filename)

        stdout_.write("Copying {}'s apk file...\n".format(app_name))
        self.adb_command("pull", app_path, str(out_file), stdout_=stdout_)

        if out_file.is_file():
            return str(out_file.resolve())

        stdout_.write("ERROR: The apk file could not be saved locally!\n")
        return False


    def launch_app(self, app, stdout_=sys.stdout):
        """Launch an app"""

        intent = "".join([app.app_name, "/", app.launchable_activity])

        launch_log = self.shell_command("am", "start", "-n", intent,
                                        return_output=True, as_list=False)

        #TODO: make error detection prettier
        if "".join(["Starting: Intent { cmp=", intent, " }"]) in launch_log:
            if "Error type" in launch_log:
                stdout_.write("ERROR: App was not launched!\n")

                if "".join(["Activity class {", intent, "} does not exist"]) in launch_log:
                    stdout_.write("Either the app is not installed or the launch activity does not exist\n")
                    stdout_.write("Intent: {}\n".format(intent))
                else:
                    stdout_.write("AM LOG:\n{}\n".format(re.search("(?:Error type [0-9]*)(.*)", launch_log, re.DOTALL).group(1)))
            elif "Activity not started, its current task has been brought to the front" in launch_log:
                stdout_.write("App already running, bringing it to front.\n")
                return True
            else:
                stdout_.write("App appears to have been succesfully launched.\n")
                return True
        else:
            if self.status != "device":
                stdout_.write("ERROR: Device was suddenly disconnected!\n")
            else:
                stdout_.write("ERROR: Unknown error!\n")
                if launch_log:
                    stdout_.write("AM LOG:\n{}\n".format(launch_log))

        return False


class InfoSpec:
    """"""
    __slots__ = ('var_name', 'var_dict_1', 'var_dict_2', 'extraction_commands',
                 'resolve_multiple_values', 'resolve_existing_values',
                 'post_extraction_commands')
    def __init__(self, var_name, var_dict_1=None, var_dict_2=None,
                 extraction_commands=((),), post_extraction_commands=None,
                 resolve_multiple_values='append', resolve_existing_values='append'):
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
            if self.resolve_multiple_values == 'drop' and extracted:
                break

            tmp_extracted = self._extract_value(extraction_strategy, source)
            tmp_extracted = self._format_value(tmp_extracted)
            if not tmp_extracted:
                continue

            try:
                tmp_extracted = tmp_extracted.strip()
            except AttributeError:
                pass

            if self.resolve_multiple_values == 'replace':
                if isinstance(tmp_extracted, list):
                    extracted = tmp_extracted
                else:
                    extracted = [tmp_extracted]
            else:
                if isinstance(tmp_extracted, list):
                    extracted.extend(tmp_extracted)
                else:
                    extracted.append(tmp_extracted)

        if extracted:
            if exists and self.resolve_existing_values in ("append", "prepend"):

                for item in extracted:
                    sanitized_item = item.lower().replace(" ", "")
                    for existing_value in value_container[self.var_name]:
                        sanitized_existing_value = existing_value.lower().replace(" ", "")
                        # check if the extracted info is redundant
                        if sanitized_item in sanitized_existing_value:
                            extracted.remove(item)
                            break
                        # check if extracted info is more verbose than the existing value
                        elif sanitized_existing_value in sanitized_item:
                            old_item = value_container[self.var_name].index(existing_value)
                            value_container[self.var_name][old_item] = item
                            extracted.remove(item)
                            break

                #if value_container[self.var_name].lower() in extracted.lower():
                #    value_container[self.var_name] = extracted

                if self.resolve_existing_values == "append":
                    value_container[self.var_name].extend(extracted)
                else:
                    extracted.extend(value_container[self.var_name])
                    value_container[self.var_name] = extracted
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
            return extracted_value
        if extracted_value is None:
            return ''

        for formatting_commands in self.post_extraction_commands:
            # 0 - command, 1 - *args, 2 - **kwargs
            try:
                args = list(formatting_commands[2])
            except IndexError:
                args = []
            try:
                kwargs = formatting_commands[3]
            except IndexError:
                kwargs = dict()

            while '$extracted' in args:
                args[args.index('$extracted')] = extracted_value

            for pair in kwargs:
                while "$extracted" in pair:
                    pair[pair.index('$extracted')] = extracted_value

            try:
                if formatting_commands[0] == "function":
                    extracted_value = formatting_commands[1](*args, **kwargs)

                else:
                    extracted_value = extracted_value.__getattribute__(
                        formatting_commands[1])(*args, **kwargs)
            except ValueError:
                extracted_value = ''

            if not extracted_value:
                return None

        return extracted_value


INFO_EXTRACTION_CONFIG = {
    (("getprop",), (("as_list", False), ("return_output", True)), "getprop") : (
        InfoSpec(
            extraction_commands=(
                (re.search, ('(?<=\\[ro\\.product\\.name\\]: \\[).*(?=\\])', '$source')),),
            var_name='Name', var_dict_1='Product', var_dict_2='_info'),
        InfoSpec(
            extraction_commands=(
                (re.search, ('(?<=\\[ro\\.product\\.model\\]: \\[).*(?=\\])', '$source')),),
            var_name='Model', var_dict_1='Product', var_dict_2='_info'),
        InfoSpec(
            extraction_commands=(
                (re.search, ('(?<=\\[ro\\.product\\.brand\\]: \\[).*(?=\\])', '$source')),),
            var_name='Brand', var_dict_1='Product', var_dict_2='_info'),
        InfoSpec(
            extraction_commands=(
                (re.search, ('(?<=\\[ro\\.product\\.device\\]: \\[).*(?=\\])', '$source')),),
            var_name='Device', var_dict_1='Product', var_dict_2='_info'),
        InfoSpec(
            extraction_commands=(
                (re.search, ('(?<=\\[ro\\.product\\.manufacturer\\]: \\[).*(?=\\])', '$source')),),
            var_name='Manufacturer', var_dict_1='Product', var_dict_2='_info'),
        InfoSpec(
            extraction_commands=(
                (re.search, ('(?<=\\[ro\\.sf\\.lcd_density\\]: \\[).*(?=\\])', '$source')),),
            var_name='Density', var_dict_1='Display', var_dict_2='_info'),
        InfoSpec(
            extraction_commands=(
                (re.search, ('(?<=\\[ro\\.build\\.id\\]: \\[).*(?=\\])', '$source')),),
            var_name='Build ID', var_dict_1='OS', var_dict_2='_info'),
        InfoSpec(
            extraction_commands=(
                (re.search, ('(?<=\\[ro\\.build\\.version\\.sdk\\]: \\[).*(?=\\])', '$source')),),
            var_name='API Level', var_dict_1='OS', var_dict_2='_info'),
        InfoSpec(
            extraction_commands=(
                (re.search, ('(?<=\\[ro\\.build\\.version\\.release\\]: \\[).*(?=\\])', '$source')),),
            var_name='Version', var_dict_1='OS', var_dict_2='_info'),
        InfoSpec(
            extraction_commands=(
                (re.search, ('(?<=\\[ro\\.build\\.fingerprint\\]: \\[).*(?=\\])', '$source')),),
            var_name='Build Fingerprint', var_dict_1='OS', var_dict_2='_info'),
        InfoSpec(
            extraction_commands=(
                (re.search, ('(?<=\\[ro\\.board\\.platform\\]: \\[).*(?=\\])', '$source')),),
            var_name='Chipset and Type', var_dict_1='CPU', var_dict_2='_info'),
        InfoSpec(
            extraction_commands=(
                (re.search, ('(?<=\\[ro\\.product\\.cpu\\.abi\\]: \\[).*(?=\\])', '$source')),),
            var_name='Architecture', var_dict_1='CPU', var_dict_2='_info',
            post_extraction_commands=(
                ('function', abi_to_arch, ('$extracted',)),)),
        # accommodate for device that only have two abis and abilist is not available in getprop
        InfoSpec(
            extraction_commands=(
                (re.search, ('(?<=\\[ro\\.product\\.cpu\\.abi\\]\\: \\[).*(?=\\])', '$source')),
                (re.search, ('(?<=\\[ro\\.product\\.cpu\\.abi2\\]\\: \\[).*(?=\\])', '$source'))),
            var_name='Available ABIs', var_dict_1='CPU', var_dict_2='_info'),
        # replace the above info if abilist is available
        InfoSpec(
            extraction_commands=(
                (re.search, ('(?<=\\[ro\\.product\\.cpu\\.abilist\\]\\: \\[).*(?=\\])', '$source')),),
            var_name='Available ABIs', var_dict_1='CPU', var_dict_2='_info', resolve_existing_values='replace',
            post_extraction_commands=(
                ('method', 'replace', (',', ', ')),
                ('method', 'replace', ('  ', ' ')))),
        InfoSpec(
            extraction_commands=(
                (re.search, ('(?<=\\[dalvik\\.vm\\.stack\\-trace\\-file\\]: \\[).*(?=\\])', '$source')),),
            var_name='anr_trace_path'),
    ),
    (("dumpsys", "SurfaceFlinger"), (("as_list", False), ("return_output", True)), "surfaceflinger_dump"): (
        InfoSpec(
            extraction_commands=(
                (re.search, ('(?<=GLES: ).*(?=\\,)', '$source')),),
            var_name='Model', var_dict_1='GPU', var_dict_2='_info'),
        InfoSpec(
            extraction_commands=(
                (re.search, ('(?<=GLES: )(?:[^\\,]+\\,){2}(.*)', '$source'), (('$group', 1),)),),
            var_name='GL Version', var_dict_1='GPU', var_dict_2='_info'),
        InfoSpec(
            extraction_commands=(
                (re.search, ('(?<=x-dpi).*', '$source')),),
            var_name='X-DPI', var_dict_1='Display', var_dict_2='_info',
            post_extraction_commands=(
                ('method', 'strip', (' :\t',)),)),
        InfoSpec(
            extraction_commands=(
                (re.search, ('(?<=y-dpi).*', '$source')),),
            var_name='Y-DPI', var_dict_1='Display', var_dict_2='_info',
            post_extraction_commands=(
                ('method', 'strip', (' :\t',)),)),
        InfoSpec(
            extraction_commands=(
                (re.search, ('(?<=Display\\[0\\] :)[^,]*', '$source')),),
            var_name='Resolution', var_dict_1='Display', var_dict_2='_info',
            post_extraction_commands=(
                ('method', 'strip', (' :\t',)),)),
        InfoSpec(
            extraction_commands=(
                (re.search, ('(?<=GLES:)(.*)(\\n*)(.*\\n*.*)', '$source'), (('$group', 3),)),),
            var_name='gles_extensions',
            post_extraction_commands=(
                ('method', 'split'),)),
        InfoSpec(
            var_name='Texture Types', var_dict_1='GPU', var_dict_2='_info',
            post_extraction_commands=(
                ('function', extract_compression_names, ('$extracted',)),)),
    ),
    (("cat", "/proc/cpuinfo"), (("as_list", False), ("return_output", True)), "cpuinfo"): (
        InfoSpec(
            extraction_commands=(
                (re.search, ('(?<=Hardware).*', '$source')),),
            var_name='Chipset and Type', var_dict_1='CPU', var_dict_2='_info', resolve_existing_values='prepend',
            post_extraction_commands=(
                ('method', 'strip', (' :\t',)),)),
        InfoSpec(
            extraction_commands=(
                (re.search, ('(?<=model name).*', '$source')),
                (re.search, ('(?<=Processor).*', '$source'))),
            var_name='Chipset and Type', var_dict_1='CPU', var_dict_2='_info', resolve_multiple_values='drop',
            post_extraction_commands=(
                ('method', 'strip', (' :\t',)),)),

    ),
    (("cat", "/sys/devices/system/cpu/cpu0/cpufreq/cpuinfo_max_freq"), (("as_list", False), ("return_output", True)), "cpu_freq"): (
        InfoSpec(
            var_name='Max Frequency', var_dict_1='CPU', var_dict_2='_info',
            post_extraction_commands=(
                ('function', int, ('$extracted',)),
                ('method', '__floordiv__', (1000,)),
                ('function', str, ('$extracted',)),
                ('method', "__add__", (' MHz',)))),
    ),
    (("cat", "/sys/devices/system/cpu/possible"), (("as_list", False), ("return_output", True)), "cpu_cores"): (
        InfoSpec(
            extraction_commands=(
                (re.search, ('(?<=-).*', '$source')),
                (re.search, ('.*', '$source'))),
            var_name='Cores', var_dict_1='CPU', var_dict_2='_info', resolve_multiple_values='drop',
            post_extraction_commands=(
                ('function', lambda x: int(x) + 1, ('$extracted',)),
                ('function', str, ('$extracted',)))),
    ),
    (("cat", "/proc/meminfo"), (("as_list", False), ("return_output", True)), "meminfo") : (
        InfoSpec(
            extraction_commands=(
                (re.search, ('(?<=^MemTotal:)[^A-z]*', '$source')),),
            var_name='Total', var_dict_1='RAM', var_dict_2='_info',
            post_extraction_commands=(
                ('function', int, ('$extracted',)),
                ('method', '__floordiv__', (1024,)),
                ('function', str, ('$extracted',)),
                ('method', '__add__', (' MB',)))),
    ),
    (("printenv",), (('as_list', False), ("return_output", True)), "shell_environment") :(
        InfoSpec(
            extraction_commands=(
                (re.search, ('(?<=EXTERNAL_STORAGE=).*', '$source')),),
            var_name="ext_storage"),
        InfoSpec(
            extraction_commands=(
                (re.search, ('(?<=SECONDARY_STORAGE=).*', '$source')),),
            var_name="secondary_storage"),
    ),
    (("ls", "/system/bin"), (('as_list', True), ("return_output", True)), "available_commands") :(
        InfoSpec(
            var_name='available_commands', resolve_existing_values='replace'),
    ),
    (("pm", "list", "features"), (('as_list', False), ("return_output", True)), "device_features") :(
        InfoSpec(
            extraction_commands=(
                (re.search, ('(?<=feature:)android.hardware.bluetooth', '$source')),),
            var_name="Bluetooth", var_dict_1='Notable Features', var_dict_2='_info',
            post_extraction_commands=(
                ('function', str, (u"\u2714",)),)),
        InfoSpec(
            extraction_commands=(
                (re.search, ('(?<=feature:)android.hardware.bluetooth_le', '$source')),),
            var_name="Bluetooth Low Energy", var_dict_1='Notable Features', var_dict_2='_info',
            post_extraction_commands=(
                ('function', str, (u"\u2714",)),)),
        InfoSpec(
            extraction_commands=(
                (re.search, ('(?<=feature:)android.hardware.consumerir', '$source')),),
            var_name="Infrared", var_dict_1='Notable Features', var_dict_2='_info',
            post_extraction_commands=(
                ('function', str, (u"\u2714",)),)),
        InfoSpec(
            extraction_commands=(
                (re.search, ('(?<=feature:)android.hardware.fingerprint', '$source')),),
            var_name="Fingerprint Scanner", var_dict_1='Notable Features', var_dict_2='_info',
            post_extraction_commands=(
                ('function', str, (u"\u2714",)),)),
        InfoSpec(
            extraction_commands=(
                (re.search, ('(?<=feature:)android.software.freeform_window_management', '$source')),),
            var_name="Freeform Window Management", var_dict_1='Notable Features', var_dict_2='_info',
            post_extraction_commands=(
                ('function', str, (u"\u2714",)),)),
        InfoSpec(
            extraction_commands=(
                (re.search, ('(?<=feature:)android.hardware.nfc', '$source')),),
            var_name="NFC", var_dict_1='Notable Features', var_dict_2='_info',
            post_extraction_commands=(
                ('function', str, (u"\u2714",)),)),
        InfoSpec(
            extraction_commands=(
                (re.search, ('(?<=feature:)android.hardware.telephony.cdma', '$source')),),
            var_name="CDMA Telephony", var_dict_1='Notable Features', var_dict_2='_info',
            post_extraction_commands=(
                ('function', str, (u"\u2714",)),)),
        InfoSpec(
            extraction_commands=(
                (re.search, ('(?<=feature:)android.hardware.telephony.gsm', '$source')),),
            var_name="GSM Telephony", var_dict_1='Notable Features', var_dict_2='_info',
            post_extraction_commands=(
                ('function', str, (u"\u2714",)),)),
        InfoSpec(
            extraction_commands=(
                (re.search, ('(?<=feature:)android.hardware.vr.headtracking', '$source')),),
            var_name="VR Headtracking", var_dict_1='Notable Features', var_dict_2='_info',
            post_extraction_commands=(
                ('function', str, (u"\u2714",)),)),
        InfoSpec(
            extraction_commands=(
                (re.search, ('(?<=feature:)android.software.vr.mode', '$source')),),
            var_name="VR Mode", var_dict_1='Notable Features', var_dict_2='_info',
            post_extraction_commands=(
                ('function', str, (u"\u2714",)),)),
        InfoSpec(
            extraction_commands=(
                (re.search, ('(?<=feature:)android.hardware.vr.high_performance', '$source')),),
            var_name="High-Performance VR Mode", var_dict_1='Notable Features', var_dict_2='_info',
            post_extraction_commands=(
                ('function', str, (u"\u2714",)),)),
        InfoSpec(
            extraction_commands=(
                (re.search, ('(?<=feature:)android.hardware.wifi.aware', '$source')),),
            var_name="WiFi-Aware", var_dict_1='Notable Features', var_dict_2='_info',
            post_extraction_commands=(
                ('function', str, (u"\u2714",)),)),
        InfoSpec(
            extraction_commands=(
                (re.findall, ('((?<=feature:).*?)\r', '$source')),),
            var_name='device_features'),
    ),
    (("pm", "list", "packages"), (('as_list', False), ("return_output", True)), "installed_apps") :(
        InfoSpec(
            extraction_commands=(
                (re.findall, ('((?<=package:).*?)\r', '$source')),),
            var_name='installed_apps', resolve_existing_values='replace'),
    ),
    (("wm", "size"), (('as_list', False), ("return_output", True)), "screen_size") :(
        InfoSpec(
            extraction_commands=(
                (re.search, ('(?<=Physical size:).*', '$source')),),
            var_name='Resolution', var_dict_1='Display', var_dict_2='_info', resolve_existing_values='drop'),
    ),
    (("wm", "density"), (('as_list', False), ("return_output", True)), "screen_density") :(
        InfoSpec(
            extraction_commands=(
                (re.search, ("(?<=Physical density:).*", '$source')),),
            var_name='Density', var_dict_1='Display', var_dict_2='_info', resolve_existing_values='drop'),
    ),
}
