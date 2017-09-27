""""""
import re
import sys
from pathlib import Path
from collections import OrderedDict
from time import sleep

import helper as helper_
import helper.apk as apk_
from helper.extract_device_info import INFO_EXTRACTION_CONFIG

ADB = helper_.ADB

# The following variable represents what information is surfaced to the
# user in the detailed-scan
SURFACED_INFO = (("Product", (
                     "Model",
                     "Manufacturer",
                     "Device")),
                 ("OS", (
                     "Version",
                     "API Level",
                     "Build ID",)),
                 ("RAM", ("Total", )),
                 ("CPU", (
                     "Chipset and Type",
                     "Cores",
                     "Architecture",
                     "Max Frequency",
                     "Available ABIs")),
                 ("GPU", (
                     "Model",
                     "Vendor",
                     "GL Version",
                     "Texture Types")),
                 ("Display", (
                     "Resolution",
                     "Density")),
                )


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
        if not device_line.strip():
            continue

        device = device_line.split(maxsplit=1)
        if device[1] not in ("device", "unauthorized", "offline"):
            if not "no permissions" in device[1]:
                stdout_.write(" ".join(["ERROR: helper received unexpected",
                                        "output while scanning for devices:\n"]
                                      )
                             )
                stdout_.write("".join(["      ", device_line + "\n"]))
                device[1] = "unknown error"

        device_list.append((device[0].strip(), device[1].strip()))

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


class DeviceError(Exception):
    """Base class for all device errors."""

    def __init__(self, message, device):
        super().__init__(message)
        self.device = device


class DeviceOfflineError(DeviceError):
    """Device is offline."""


class Device:
    """Class representing a physical Android device."""
    def __init__(self, serial, status='offline', limit_init=()):
        """"""
        self.serial = serial
        self._extracted_info_groups = []

        self.internal_sd_path = None
        self.external_sd_path = None
        self.anr_trace_path = None

        self.thirdparty_apps = ()
        self.system_apps = ()
        self.device_features = ()
        self.available_commands = ()

        self._info = OrderedDict()

        for pair in SURFACED_INFO:
            props = OrderedDict()
            for prop in pair[1]:
                props[prop] = list()

            self._info[pair[0]] = props

        self.initialized = False
        self._status = status

        if self._status == "device":
            self.device_init(limit_init)


    def adb_command(self, *args, **kwargs):
        """Same as adb_command(*args), but specific to the given device.
        """
        if self.status != "device":
            raise DeviceOfflineError("Called adb command while device {} was offline".format(self.serial), self.serial)

        command_output = adb_command("-s", self.serial, *args, **kwargs)

        if self.status != "device":
            raise DeviceOfflineError("Device {} became offline after adb command".format(self.serial), self.serial)

        return command_output


    def shell_command(self, *args, **kwargs):
        """Same as adb_command(["shell", *args]), but specific to the
        given device.
        """
        if self.status != "device":
            raise DeviceOfflineError("Called adb command while device {} was offline".format(self.serial), self.serial)

        command_output = adb_command("-s", self.serial, "shell", *args, **kwargs)

        if self.status != "device":
            raise DeviceOfflineError("Device {} became offline after adb command".format(self.serial), self.serial)

        return command_output


    @property
    def status(self):
        """Device's current state, as announced by adb. Return offline
        if device was not found by adb.
        """
        self._status = "offline"
        for device_specs in _get_devices():
            if self.serial == device_specs[0]:
                self._status = device_specs[1]
                break

        return self._status


    def info(self, index1, index2=None, nonexistent_ok=False):
        """Fetch the string value for the given info variable."""
        try:
            info_container = self._info[index1]
            if not index2:
                if isinstance(info_container, list):
                    return "\n".join(info_container)

                return info_container

            info_container = info_container[index2]
            return ", ".join(info_container)
        except KeyError:
            if nonexistent_ok:
                return "Unavailable"
            else:
                raise


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

            # This kinda defeats the purpose of the whole info config thing...
            if isinstance(self.internal_sd_path, list):
                self.internal_sd_path = self.internal_sd_path[0]
            if isinstance(self.external_sd_path, list):
                self.external_sd_path = self.external_sd_path[0]
            if isinstance(self.anr_trace_path, list):
                self.anr_trace_path = self.anr_trace_path[0]

            self.initialized = True


    def is_type(self, file_path, file_type, check_read=False,
                check_write=False, check_execute=False, symlink_ok=True):
        """Check whether a path points to an existing file that matches
        the specified type and whether the current user has the
        specified permissions.

        You can check for read, write and execute acccess by
        setting the respective check_* arguments to True. Function will
        return True only if all specified permissions are available and
        if the file is of specified type.

        Symbolic links are accepted by default.
        None of the permissions are tested by default.
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

        # check if the file exists
        exists = self.shell_command(
            'if [ -e "{}" ];'.format(file_path), "then echo 1;",
            "else echo 0;", "fi", return_output=True, as_list=False).strip()
        exists = bool(int(exists))
        if not exists:
            return False

        # check if the file is a symlink
        symlink = self.shell_command(
            'if [ -L "{}" ];'.format(file_path), "then echo 1;",
            "else echo 0;", "fi", return_output=True, as_list=False).strip()
        symlink = bool(int(symlink))
        if symlink and not symlink_ok:
            return False

        # check if the file is the specified type
        is_type = self.shell_command(
            'if [ -{} "{}" ];'.format(file_type, file_path), "then echo 1;",
            "else echo 0;", "fi", return_output=True, as_list=False).strip()
        is_type = bool(int(is_type))
        if not is_type:
            return False

        # check if the shell user has specified permission to the file
        for permission in permissions:
            has_permission = self.shell_command(
                'if [ -{} "{}" ];'.format(permission, file_path),
                "then echo 1;", "else echo 0;", "fi", return_output=True,
                as_list=False).strip()
            has_permission = bool(int(has_permission))
            if not has_permission:
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
        reconnect_status = self.adb_command("reconnect", return_output=True,
                                            as_list=False)
        if reconnect_status.strip().lower() != "done":
            # I don't even know if there is a chance for unexpected output here
            stdout_.write("ERROR: ")
            stdout_.write(reconnect_status + "\n")
            return False

        # TODO: If you wait long enough, all problems will just disappear, right?
        sleep(0.7)

        if self.status == "unauthorized":
            stdout_.write(
                " ".join(["Connection with this device had to be reset,",
                          "to continue you must grant debugging permission",
                          "again.\n"]))
        reconnect_status = self.adb_command("wait-for-device",
                                            return_output=True, as_list=False)
        if reconnect_status:
            # I have not seen the 'wait-for-<status>' command output anything ever
            # so this is a precaution in case it ever will
            stdout_.write("ERROR: ")
            stdout_.write(reconnect_status + "\n")
            return False

        return True


    def full_info_string(self, initialize=True, indent=4):
        """Return a formatted string containing all device info"""
        # ensure all required info is available

        if initialize:
            self.device_init()

        # if an info source is a key in whitelist, only the asociated values
        # will be returned from that group
        # which means that group can be blacklisted by simply not specyfing any
        # values with it
        group_whitelist = {"device_features":("device_features",),
                           "system_apps":(),
                          }

        indent = indent * " "
        group_list = []
        grouped_vars = {}
        ungrouped_vars = []

        # TODO: Look into simplifying this mess

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

                    value = self.info(info_variable.var_dict_1,
                                      info_variable.var_name, True)
                    if not value:
                        value = "Unknown"

                    line = "".join([info_variable.var_name, " : ", value])

                    if info_variable.var_dict_1 not in grouped_vars:
                        grouped_vars[info_variable.var_dict_1] = []

                    if line in grouped_vars[info_variable.var_dict_1]:
                        continue

                    grouped_vars[info_variable.var_dict_1].append(line)
                elif info_variable.var_dict_1 == "_info":
                    value = self.info(info_variable.var_name,
                                      nonexistent_ok=True)
                    if not value:
                        value = "Unknown"

                    line = "".join([info_variable.var_name, " : ", value])
                    ungrouped_vars.append(line)
                else:
                    try:
                        value = self.__dict__[info_variable.var_name]
                    except KeyError:
                        value = "Unavailable"

                    if not value:
                        value = "Unknown"
                    else:
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


    def detailed_info_string(self, initialize=True, indent=4):
        """"""
        info = ""
        if initialize:
            self.device_init(limit_init=())

        for category_name, value_names_list in SURFACED_INFO:
            info = "".join([info, "\n", category_name, ":"])
            for value_name in value_names_list:
                info = "".join([info, "\n", indent*" ", value_name, " : ",
                                self.info(category_name, value_name,
                                          nonexistent_ok=True)])

        return info


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

        self.device_init(limit_init=("thirdparty_apps", "system_apps"))

        if app_name not in self.system_apps and app_name not in self.thirdparty_apps:
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

        filename = "".join([app_name, "(", Path(app_path).stem, ").apk"])
        out_file = Path(out_dir, filename)

        stdout_.write("Copying {}'s apk file...\n".format(app_name))
        self.adb_command("pull", app_path, str(out_file), stdout_=stdout_)

        if out_file.is_file():
            return str(out_file.resolve())

        stdout_.write("ERROR: The apk file could not be copied!\n")
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
