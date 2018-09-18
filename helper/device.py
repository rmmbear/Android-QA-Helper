""""""
import re
import sys
import logging
from pathlib import Path
#from collections import OrderedDict
from time import sleep, strftime

#import helper as helper_
import helper.apk as apk_
import helper.extract_data as extract
from helper import ADB, CONFIG, VERSION, exe

#ADB = helper_.ADB
LOGGER = logging.getLogger(__name__)
EXTRACTION_FUNCTIONS = {x[8::]:getattr(extract, x) for x in dir(extract) if x.startswith("extract_")}

SH_FILE_TEST = """
if [ -e "{}" ]; then
    echo -n 1;
    if [ -L "{}" ]; then
        echo -n 1;
    else echo -n 0;
    fi;
    if [ -r "{}" ]; then
        echo -n 1;
    else echo -n 0;
    fi;
    if [ -w "{}" ]; then
        echo -n 1;
    else echo -n 0;
    fi;
    if [ -x "{}" ]; then
        echo -n 1;
    else echo -n 0;
    fi;
    if [ -{} "{}" ]; then
        echo -n 1;
    else echo -n 0;
    fi;
else echo -n 000000;
fi
""".strip().replace("\n", "")

SH_ECHO_GLOB = """
for path in {}; do
    echo -n $path\\;;
done
""".strip().replace("\n", "")


def adb_command(*args, check_server=None, stdout_=sys.stdout, **kwargs):
    """Execute an ADB command.

    If check_server is true, function will first make sure that an ADB
    server is available before executing the command.
    """
    if check_server is None:
        check_server = False
        try:
            if kwargs["return_output"]:
                check_server = True
        except KeyError:
            pass

    try:
        if check_server:
            exe(ADB, "start-server", return_output=True)

        return exe(ADB, *args, **kwargs)
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
                      CONFIG]))
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
        self._name = None
        self._filename = None
        self._init_cache = {}

        self.info_dict = {x:None for x in extract.INFO_KEYS}

        self.initialized = False
        self._status = status

        if self._status == "device":
            self.extract_data(limit_init)


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
    def name(self):
        """Property holding a human-readable name of the device.

        Name consists of: manufacturer, model and serial number."""
        if self._name:
            return self._name

        if "identity" not in self._extracted_info_groups:
            return "Unknown device ({})".format(self.serial)

        self._name = "".join([self.info_dict["device_manufacturer"], " - ",
                              self.info_dict["device_model"], self.serial,
                             ])
        return self._name


    @property
    def filename(self):
        """Device's name stripped of path-unsafe characters."""
        if self._filename:
            return self._filename

        keep = [';', '$', '%', '=', '^', ']', '{', "'", '.', ',', '}', '+',
                '#', '&', '-', '~', '!', '_', '`', '[', '@', '']
        filename = "".join([x if x.isalnum() or x in keep else "_" for x in self.name])
        self._filename = filename

        return self._filename


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


    def extract_data(self, limit_to=(), force_extract=False):
        """"""
        LOGGER.info("starting data extraction")
        for command_id, command in EXTRACTION_FUNCTIONS.items():
            if limit_to:
                if command_id not in limit_to:
                    continue

            if command in self._extracted_info_groups:
                if not force_extract:
                    LOGGER.info("'%s' - skipping extraction of '%s' - command already executed", self.name, command_id)
                    continue

            LOGGER.info("'%s' - extracting info group '%s'", self.name, command_id)
            command(self)
            if command_id not in self._extracted_info_groups:
                self._extracted_info_groups.append(command_id)

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

        safe_path = "*".join(['"{}"'.format(x) for x in path.split("*")])
        #safe_path = safe_path.replace("\\", "\\\\")

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


    def full_info_string(self, initialize=True, indent=4):
        """Return a formatted string containing all device info"""
        # ensure all required info is available
        LOGGER.info("Starting device info dump")
        if initialize:
            self.extract_data()

        indent = " " * indent
        full_info_string = "# Android QA Helper v.{}".format(VERSION)
        full_info_string += "\n# Generated at {}\n".format(strftime("%Y-%m-%d %H:%M:%S"))

        for info_section in extract.SURFACED_VERBOSE:
            full_info_string = "".join([full_info_string, "\n", info_section[0], ":\n"])
            if isinstance(info_section, list):
                for info_name, info_key in info_section[1]:
                    info_value = self.info_dict[info_key]

                    if not info_value:
                        info_value = "Unknown"
                    elif isinstance(info_value, (list, tuple)):
                        info_value = ", ".join(info_value)

                    full_info_string = "".join([full_info_string, indent, info_name, " : ", info_value, "\n"])

            else:
                info_name, info_key = info_section
                info_value = self.info_dict[info_key]

                if not info_value:
                    info_value = "Unknown"
                elif isinstance(info_value, (list, tuple)):
                    info_value = ", ".join(info_value)

                full_info_string = "".join([full_info_string, indent, info_value, "\n"])

        return full_info_string


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

        if isinstance(app, apk_.App):
            app_name = app.app_name
        else:
            app_name = app

        self.extract_data(limit_to=("installed_packages"))

        if app_name not in self.info_dict["system_apps"] and\
           app_name not in self.info_dict["third-party_apps"]:
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
                stdout_.write("App appears to have been successfully launched.\n")
                return True
        else:
            if self.status != "device":
                stdout_.write("ERROR: Device was suddenly disconnected!\n")
            else:
                stdout_.write("ERROR: Unknown error!\n")
                if launch_log:
                    stdout_.write("AM LOG:\n{}\n".format(launch_log))

        return False
