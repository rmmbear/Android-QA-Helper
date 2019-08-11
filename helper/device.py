"""
"""
import re
import sys
import logging
from pathlib import Path
from time import sleep, strftime

import helper
import helper.apk
import helper.extract_data
from helper import ADB, VERSION, exe

#ADB = helper_.ADB
LOGGER = logging.getLogger(__name__)
EXTRACTION_FUNCTIONS = {x[8::]:getattr(helper.extract_data, x) for x in dir(helper.extract_data) if x.startswith("extract_")}

#returns 6 integers, corresponding to following tests:
# exists, is a symlink, user can read, user can write, user can execute, custom test
SH_FILE_TEST = """
if [ -e "{}" ]; then echo -n 1;
if [ -L "{}" ]; then echo -n 1; else echo -n 0; fi;
if [ -r "{}" ]; then echo -n 1; else echo -n 0; fi;
if [ -w "{}" ]; then echo -n 1; else echo -n 0; fi;
if [ -x "{}" ]; then echo -n 1; else echo -n 0; fi;
if [ -{} "{}" ]; then echo -n 1; else echo -n 0; fi;
else echo -n 000000; fi
""".strip().replace("\n", " ")

SH_ECHO_GLOB = "for path in {}; do echo -n $path\\;; done"


def adb_command(*args, check_server=None, **kwargs):
    """Execute an ADB command.

    If check_server is true, function will first make sure that an ADB
    server is available before executing the command.
    """
    #LOGGER.debug("Executing %s", str(["ADB", *args]))
    if check_server is None:
        check_server = False
        try:
            if kwargs["return_output"]:
                check_server = True
        except KeyError:
            pass

    if check_server:
        # return_output set to True to suppress printing
        exe(helper.ADB, "start-server", return_output=True)

    return exe(helper.ADB, *args, **kwargs)


def get_serials():
    """Proxy function for 'adb devices'.
    Return list of two-element tuples.
    Tuple[0] = device's serial number
    Tuple[1] = device's adb status
    """
    adb_output = adb_command("devices", return_output=True).splitlines()
    if not adb_output:
        return []

    status_line = adb_output.pop(0).lower()
    if "list of devices attached" not in status_line:
        LOGGER.error("Unexpected adb output:")
        LOGGER.error("%s", status_line)
        LOGGER.error("%s", adb_output)
        return []

    device_list = []
    for line in adb_output:
        if not line:
            continue
        try:
            serial, status = line.strip().split(maxsplit=1)
            device_list.append((serial, status))
        except ValueError:
            LOGGER.error("Could not split line:")
            LOGGER.error("%s", line)

    return device_list


def get_devices(initialize=True, limit_init=("identity",), allow_offline=False):
    """Return a list of device objects for currently connected devices.
    """
    device_list = []

    for device_serial, device_status in get_serials():
        if device_status != "device" and not allow_offline:
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
        self._name = None
        self._filename = None
        self._init_cache = {}

        self.info_dict = {x:None for x in helper.extract_data.INFO_KEYS}

        self.initialized = False
        self._status = status

        if self._status == "device":
            self.extract_data(limit_init)


    def adb_command(self, *args, **kwargs):
        """Same as adb_command(*args), but specific to the given device.
        """
        if self.status != "device":
            raise DeviceOfflineError(
                "Called adb command while device {} was offline".format(self.serial), self.serial)

        command_output = adb_command("-s", self.serial, *args, **kwargs)

        if self.status != "device":
            raise DeviceOfflineError(
                "Device {} became offline after adb command".format(self.serial), self.serial)

        return command_output


    def shell_command(self, *args, **kwargs):
        """Same as adb_command(["shell", *args]), but specific to the
        given device.
        """
        if self.status != "device":
            raise DeviceOfflineError(
                "Called adb command while device {} was offline".format(self.serial), self.serial)

        command_output = adb_command("-s", self.serial, "shell", *args, **kwargs)

        if self.status != "device":
            raise DeviceOfflineError(
                "Device {} became offline after adb command".format(self.serial), self.serial)

        return command_output


    @property
    def name(self):
        """Property holding a human-readable name of the device.

        Name consists of: manufacturer, model and serial number."""
        if self._name:
            return self._name

        if "identity" not in self._extracted_info_groups:
            return "Unknown device ({})".format(self.serial)

        self._name = " - ".join(
            [self.info_dict["device_manufacturer"], self.info_dict["device_model"],
             self.serial])
        return self._name


    @property
    def filename(self):
        """Device's name stripped of path-unsafe characters."""
        if self._filename:
            return self._filename

        keep = [';', '$', '%', '=', '^', ']', '{', "'", '.', ',', '}', '+',
                '#', '&', '-', '~', '!', '_', '`', '[', '@']
        filename = "".join([x if x.isalnum() or x in keep else "_" for x in self.name])
        self._filename = filename

        return self._filename


    @property
    def status(self):
        """Device's current state, as announced by adb. Return offline
        if device was not found by adb.
        """
        self._status = "offline"
        for device_specs in get_serials():
            if self.serial == device_specs[0]:
                self._status = device_specs[1]
                break

        return self._status


    def extract_data(self, limit_to=(), force_extract=False):
        """"""
        LOGGER.info("%s - starting data extraction", self.name)
        for command_id, command in EXTRACTION_FUNCTIONS.items():
            if limit_to:
                if command_id not in limit_to:
                    continue

            if command in self._extracted_info_groups:
                if not force_extract:
                    LOGGER.info("'%s' - skipping extraction of '%s' - command already executed", self.name, command_id)
                    continue
                LOGGER.info("'%s' - extraction of the next group has been forced ", self.name)

            LOGGER.info("'%s' - extracting info group '%s'", self.name, command_id)
            command(self)
            if command_id not in self._extracted_info_groups:
                self._extracted_info_groups.append(command_id)
                # progress indicator for long loads
                if not limit_to:
                    print(".", end="", flush=True)

        if not limit_to:
            print()
        self._init_cache = {}


    def is_type(self, file_path, file_type, check_read=False,
                check_write=False, check_execute=False, symlink_ok=True):
        """Check whether a path points to an existing file that matches
        the specified type and whether the current user has the
        specified permissions.

        You can check for read, write and execute acccess by
        setting the respective check_* arguments to True. Function will
        return True only if all queried permissions are available and
        if the file is of given type.

        Symbolic links are accepted by default.
        None of the permissions are tested by default.

        Return values:
         1 file meets criteria
         0 file does not exist
        -1 wrong type
        -2 symlink
        -3 missing read permissions
        -4 missing write permissions
        -5 missing execute permissions
        Negative status is returned as soon as a failed test is
        encountered (so if all permissions are missing, only the
        first missing permission will be reported).
        """
        if len(file_type) != 1:
            raise ValueError("Only one test can be carried out at a time (see the 'conditional expressions' section of the bash manual for possible tests)")

        if not file_path:
            file_path = "."

        #outputs a 6 character-long string describing the file
        #sample output: 101011 = exists, not symlink, read and execute permissions granted, passed custom test (file_type)

        test = SH_FILE_TEST.format(*[file_path for x in range(5)], file_type, file_path)

        file_status = self.shell_command(test, return_output=True, as_list=False).strip()

        LOGGER.debug("file %s was tested, received: elrwxt %s", file_path, file_status)

        if not len(file_status) > 1:
            return False

        #exists, is link, read permission, write permission, execute permission, custom test
        e, l, r, w, x, t = [bool(int(x)) for x in file_status]

        tests = [
            (True, e, 0),
            (True, t, -1),
            (not(symlink_ok), not(l), -2),
            (check_read, r, -3),
            (check_write, w, -4),
            (check_execute, x, -5),
        ]

        for case in tests:
            # converse implication
            if not(not(case[0]) or case[1]):
                return case[2]

        # file exists and meets all criteria
        return 1


    def is_file(self, file_path, *args, **kwargs):
        """Check whether given path points to an existing file and
        current user has the specified permissions.

        This is the same as calling device.is_type(<path>, "f", ...)
        """
        return self.is_type(file_path, "f", *args, **kwargs)


    def is_dir(self, file_path, *args, **kwargs):
        """Check whether given path points to an existing directory and
        current user has the specified permissions.

        This is the same as calling device.is_type(<path>, "d", ...)
        """
        return self.is_type(file_path, "d", *args, **kwargs)


    def glob(self, path):
        """Return list of paths matching the expanded wildcard path.

        Currently, only the '*' wildcard is supported.
        """
        if "*" not in path:
            raise ValueError("Path must contain a wildcard!")

        #TODO: Make "?" wildcards work

        safe_path = "*".join([f'"x"' for x in path.split("*")])

        shell_command = SH_ECHO_GLOB.format(safe_path)
        path_list = self.shell_command(shell_command, return_output=True, as_list=False).strip().split(";")
        path_list = [x[:-1] for x in path_list if x]
        try:
            path_list.remove(path)
        except ValueError:
            pass

        return path_list


    def reconnect(self, stdout_=sys.stdout):
        """Restart connection with device.

        Return true when device comes back online.
        """
        reconnect_status = adb_command("-s", self.serial, "reconnect",
                                       return_output=True, as_list=False)
        # TODO: New versions of adb started outputting device status when reconnecting devices

        """from time import strftime
        if reconnect_status.strip().lower() != "done":
            # I don't even know if there is a chance for unexpected output here
            stdout_.write("ERROR: ")
            stdout_.write(reconnect_status + "\n")
            return False
        """

        # TODO: If you wait long enough, all problems will just disappear, right?
        sleep(0.7)

        if self.status != "device":
            stdout_.write(
                " ".join(["Connection with this device had to be reset,",
                          "to continue you must reconnect your device and/or",
                          "grant debugging permission again.\n"]))
        reconnect_status = adb_command("-s", self.serial, "wait-for-device",
                                       return_output=True, as_list=False)
        if reconnect_status:
            # I have not seen the 'wait-for-<status>' command output anything ever
            # so this is a precaution in case it ever will
            stdout_.write("ERROR: ")
            stdout_.write(reconnect_status + "\n")
            return False

        return True


    def info_dump(self, out_file, initialize=True, indent=4):
        """Write all available info on device to file-like object 'out_file'.
        """
        # ensure all required info is available
        if initialize:
            self.extract_data()

        indent = " " * indent
        written = out_file.write(f"# Android QA Helper v.{VERSION}\n")
        written += out_file.write(f"# Generated at {strftime('%Y-%m-%d %H:%M:%S %z')}\n")

        for section_name, section_items in helper.extract_data.SURFACED_VERBOSE.items():
            written += out_file.write(f"\n{section_name}:\n")

            for val_name, val_ref in section_items:
                written += out_file.write(f"{indent}")
                if val_name:
                    written += out_file.write(f"{val_name}: ")

                val_val = self.info_dict[val_ref]

                if not val_val:
                    written += out_file.write("Unknown\n")
                elif isinstance(val_val, (list, tuple)):
                    for item in val_val[:-1]:
                        written += out_file.write(f"{item}, ")
                    written += out_file.write(f"{val_val[-1]}\n")
                else:
                    written += out_file.write(f"{val_val}\n")

        return written


    def basic_info_string(self):
        """Return formatted string containing basic device information.
        contains: manufacturer, model, OS version and available texture
        compression types.
        """
        # ensure all required data is available
        self.extract_data(limit_to=["gpu", "identity", "os"])

        model = self.info_dict["device_model"]
        if not model:
            model = "Unknown model"

        manufacturer = self.info_dict["device_manufacturer"]
        if not manufacturer:
            manufacturer = "Unknown manufacturer"

        os_ver = self.info_dict["android_version"]
        if not os_ver:
            os_ver = "Unknown OS version"

        line1 = " - ".join([manufacturer, model, os_ver])
        line2 = "".join(["Texture compression types: ",
                         ", ".join(self.info_dict["gles_texture_compressions"])])

        return "\n".join([line1, line2])


    def extract_apk(self, app, out_dir=".", stdout_=sys.stdout):
        """Extract an application's apk file.

        To specify the application, provide either an app name or an
        app object.
        """

        if isinstance(app, helper.apk.App):
            app_name = app.app_name
        else:
            app_name = app

        self.extract_data(limit_to=("installed_packages"))

        if app_name not in self.info_dict["system_apps"] and\
           app_name not in self.info_dict["third-party_apps"]:
            stdout_.write(f"{app_name} not in list of installed apps.\n")
            return False

        app_path = self.shell_command(
            "pm", "path", app_name, return_output=True, as_list=False).strip()

        package_line = re.search('(?<=package:).*', app_path)
        if not package_line:
            # this should not happen under normal circumstances
            stdout_.write("ERROR: Got no path from package manager!\n")
            return False

        app_path = package_line.group()

        filename = f"{app_name} ({Path(app_path).stem}).apk"
        out_file = Path(out_dir, filename)

        stdout_.write("Copying {}'s apk file...\n".format(app_name))
        self.adb_command("pull", app_path, str(out_file), stdout_=stdout_)

        if out_file.is_file():
            return str(out_file.resolve())

        stdout_.write("ERROR: The apk file could not be copied!\n")
        return False


    def launch_app(self, app, stdout_=sys.stdout):
        """Launch an app"""

        intent = f"{app.app_name}/{app.launchable_activity}"

        launch_log = self.shell_command(
            "am", "start", "-n", intent, return_output=True, as_list=False)

        #TODO: make error detection prettier
        if "".join(("Starting: Intent { cmp=", intent, "}")) in launch_log:
            if "Error type" in launch_log:
                stdout_.write("ERROR: App was not launched!\n")

                if f"Activity class {{intent}} does not exist" in launch_log:
                    stdout_.write("Either the app is not installed or the launch activity does not exist\n")
                    stdout_.write(f"Intent: {intent}")
                else:
                    am_log = re.search("(?:Error type [0-9]*)(.*)", launch_log, re.DOTALL).group(1)
                    stdout_.write(f"AM LOG:\n{am_log}\n")
            elif "Activity not started, its current task has been brought to the front" in launch_log:
                stdout_.write("App already running, bringing it to front.\n")
                return True
            else:
                stdout_.write("App appears to have been successfully launched.\n")
                return True
        else:
            if self.status != "device":
                stdout_.write("ERROR: Device was suddenly disconnected!\n")
            else:
                stdout_.write("ERROR: Unknown error!\n")
                if launch_log:
                    stdout_.write(f"AM LOG:\n{launch_log}\n")

        return False
