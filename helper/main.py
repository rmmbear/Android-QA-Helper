"""Main module combining operations on apks and devices"""
import sys
from pathlib import Path
from time import strftime

import helper as helper_
from helper import apk as apk_

def install(device, *items, stdout_=sys.stdout):
    """Install apps.
    Accepts either a list of apk files, or list with one apk and as many
    obb files as you like.
    """
    apk_list = []
    obb_list = []

    for item in items:
        if item[-3:].lower() == "apk":
            apk_list.append(apk_.App(item))

        if item[-3:].lower() == "obb":
            obb_list.append(item)

    if len(apk_list) > 1 and obb_list:
        stdout_.write("ERROR: APK ambiguity!")
        stdout_.write(
            "Please specify only one apk for installation with obb files!\n")
        return False

    # TODO: Accommodate for situations where aapt is not available
    # TODO: Add ability to pick install location

    if not apk_list:
        stdout_.write("ERROR: No APKs found among provided files, aborting!\n")
        return False

    install_failure = []

    # Take care of apk files(s)
    for apk_file in apk_list:
        stdout_.write("".join(["\nINSTALLING: ", apk_file.app_name, "\n"]))

        if not install_app(device, apk_file, stdout_=stdout_):
            install_failure.append(apk_file.app_name)

    installed = len(apk_list) - len(install_failure)

    if installed:
        if installed > 1:
            stdout_.write(
                " ".join(["\nSuccesfully installed", str(installed),
                          "out of", str(len(apk_list)), "provided apks:\n"]))
        else:
            stdout_.write("\nSuccesfully installed ")

        for apk_file in apk_list:
            if apk_file.app_name not in install_failure:
                stdout_.write("".join([apk_file.app_name, "\n"]))

    if install_failure:
        if len(install_failure) > 1:
            stdout_.write("The following apks could not be installed:\n")
        else:
            stdout_.write("\nCould not install ")

        for app_name in install_failure:
            stdout_.write("".join([app_name, "\n"]))

        return

    # take care of obb file(s)
    if obb_list:
        apk_file = apk_list[0]
        if apk_file.app_name.startswith("Unknown"):
            stdout_.write("ERROR: Unknown app name, cannot push obb files!\n")
            return False

        stdout_.write("\nCopying obb files...\n")
        device.device_init(limit_init=("shell_environment"))

        # Prepare the target directory
        obb_folder = device.ext_storage + "/Android/obb"
        device.shell_command("mkdir", obb_folder, return_output=True)
        device.shell_command("mkdir", obb_folder + "/" + apk_file.app_name,
                             return_output=True)
        device.shell_command("rm", "".join([obb_folder, "/", apk_file.app_name,
                                            "/", "*.obb"]), return_output=True)

        for obb_file in obb_list:
            if not push_obb(device, obb_file, apk_file.app_name, stdout_=stdout_):
                stdout_.write("ERROR: Failed to copy " + obb_file + "\n")
                return False

        stdout_.write(" ".join(["\nSuccesfully copied obb files for",
                                apk_file.display_name, "!\n"]))


def install_app(device, apk_file, install_location="automatic",
                installer_name="android_helper", stdout_=sys.stdout):
    """Install an application from a local apk file."""
    possible_install_locations = {"automatic":"", "external":"-s",
                                  "internal":"-f"}

    if apk_file.app_name.startswith("Unknown"):
        stdout_.write(
            "WARNING: This app does not appear to be a valid .apk archive\n")
    else:
        is_compatible = apk_file.check_compatibility(device)
        if not is_compatible[0]:
            stdout_.write("WARNING: This apk and device are not compatible!\n")
            for reason in is_compatible[1]:
                stdout_.write(reason + "\n")

    device.device_init(limit_init=("system_apps", "thirdparty_apps"),
                       force_init=True)

    if apk_file.app_name in device.thirdparty_apps:
        stdout_.write(" ".join(["WARNING: Different version of the app",
                                "already installed\n"]))
        if not _clean_uninstall(device, apk_file, stdout_=stdout_):
            stdout_.write("ERROR: Could not uninstall the app!\n")
            return False
    elif apk_file.app_name in device.system_apps:
        stdout_.write(
            "WARNING: This app already exists on device as a system app!\n")
        stdout_.write(
            "         System apps can only be upgraded to newer versions.\n")

    apk_filename = Path(apk_file.host_path).name
    destination = ("/data/local/tmp/helper_" + apk_filename).replace(" ", "_")

    stdout_.write("Copying the apk file to device...\n")
    device.adb_command("push", apk_file.host_path, destination, stdout_=stdout_)

    if not device.is_file(destination):
        stdout_.write("ERROR: Could not copy apk file to device\n")
        return False

    stdout_.write(" ".join(["Installing", apk_file.display_name, "...\n"]))
    stdout_.write(" ".join(["Please check your device, as it may now ask",
                            "you to confirm the installation.\n"]))

    destination = '"{}"'.format(destination)
    device.shell_command("pm", "install", "-r", "-i", installer_name,
                         possible_install_locations[install_location],
                         destination, stdout_=stdout_)
    device.shell_command("rm", destination, stdout_=stdout_)

    device.device_init(limit_init=("system_apps", "thirdparty_apps"),
                       force_init=True)

    # TODO: detect installation failure for system apps
    if apk_file.app_name not in device.thirdparty_apps:
        stdout_.write("ERROR: App could not be installed!\n")
        return False

    stdout_.write("Installation completed!\n")
    return True


def push_obb(device, obb_file, app_name, stdout_=sys.stdout):
    """Push <obb-file> to <shared-storage>/Android/obb/<package-name>/
    on <Device>.
    """
    device.device_init(limit_init=("shell_environment"))

    obb_name = str(Path(obb_file).name)
    obb_target_file = "".join([device.ext_storage, "/Android/obb/", app_name,
                               "/", obb_name])

    #pushing obb in two steps - some devices block adb push directly to obb folder
    device.adb_command("push", obb_file, device.ext_storage + "/" + obb_name,
                       stdout_=stdout_)
    device.shell_command("mv",
                         "".join(['"', device.ext_storage, "/", obb_name, '"']),
                         "".join(['"', obb_target_file, '"']),
                         stdout_=stdout_)

    if device.is_file(obb_target_file):
        return True

    if device.status != "device":
        stdout_.write("ERROR: Device has been suddenly disconnected!\n")
    else:
        stdout_.write(
            "ERROR: Pushed obb file was not found in destination folder.\n")
    return False


def record(device, output=".", name=None, silent=False, stdout_=sys.stdout):
    """Start recording device's screen.
    Recording can be stopped by either reaching the time limit, or
    pressing ctrl+c. After the recording has stopped, the helper
    confirms that the recording has been saved to device's storage and
    copies it to drive.
    """
    # existence of "screenrecord" can depend on manufacturer and
    # version of Android
    #
    # Sony devices have a custom screen recording function available to
    # regular users from their device - hold the power button and it should
    # appear alongside reset and shutdown options

    device.device_init(limit_init=("available_commands", "shell_environment"))

    if 'screenrecord' not in device.available_commands:
        stdout_.write(
            " ".join(["This device's shell does not have the 'screenrecord'",
                      "command."]))
        if int(device.info("OS", "API Level")) < 19:
            stdout_.write(
                " ".join(["The command was introduced with API level 19 (",
                          "Android version 4.4.4) and your device has API level",
                          device.info("OS", "API Level"), "(Android version",
                          device.info("OS", "Version"), ").\n"]))
        else:
            stdout_.write(
                " ".join(["Your device's manufacturer opted to not",
                          "include it on device.\n"]))

        stdout_.write(
            " ".join(["Note that you can also record your device's screen",
                      "using Google Play Games. Certain devices (Sony Xperias",
                      "for example) have built-in apps allowing you to record",
                      "your screen. Please refer to your device's manual for",
                      "more information.\n"]))
        return False

    if not silent:
        stdout_.write(
            " ".join(["Helper will record your device's screen (audio is not",
                      "captured). Press 'ctrl + c' to stop recording.",
                      "Recording will be automatically stopped after three",
                      "minutes.\n"]))
        try:
            input("Press enter whenever you are ready to record.\n")
        except KeyboardInterrupt:
            stdout_.write("\nRecording canceled!\n")
            return False

    if name:
        filename = name
    else:
        filename = "".join([device.info("Product", "Model"), "_screenrecord_",
                            strftime("%Y.%m.%d_%H.%M.%S"), ".mp4"])

    remote_recording = "".join([device.ext_storage + "/" + filename])

    try:
        device.shell_command("screenrecord", "--verbose", remote_recording,
                             stdout_=stdout_)
    except KeyboardInterrupt:
        pass
    stdout_.write("\nRecording stopped.\n")


    device.reconnect(stdout_=stdout_)

    if not device.is_file(remote_recording):
        if device.status != "device":
            stdout_.write("ERROR: Device has been suddenly disconnected!\n")
        else:
            stdout_.write("ERROR: Recorded video was not found on device!\n")
        return False

    output = str(Path(output) / Path(remote_recording).name)

    device.adb_command("pull", remote_recording, output, stdout_=stdout_)
    if Path(output).is_file():
        return str(Path(output).resolve())

    stdout_.write("ERROR: Could not copy recorded video!\n")
    return False


def pull_traces(device, output=None, stdout_=sys.stdout):
    """Copy the 'traces' file to the specified folder."""
    if output is None:
        output = Path().resolve()
    else:
        output = Path(output).resolve()

    device.device_init(limit_init=("getprop", "shell_environment"))

    anr_filename = "".join([device.info("Product", "Model"), "_anr_",
                            strftime("%Y.%m.%d_%H.%M.%S"), ".txt"])
    remote_anr_file = "".join([device.ext_storage, "/", anr_filename])
    device.shell_command("cat", device.anr_trace_path, ">", remote_anr_file)

    if not device.is_file(remote_anr_file):
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


def _clean_uninstall(device, apk_file, check_packages=True, clear_data=False,
                     stdout_=sys.stdout):
    """Uninstall an app from specified device. Target can be an app name
    or a path to apk file -- by default it will check if target is a
    file, and if so it will attempt to extract app name from it.
    To disable that, set "app_name" to True.
    """
    if isinstance(apk_file, str):
        display_name = apk_file
        app_name = apk_file
    else:
        display_name = apk_file.display_name
        app_name = apk_file.app_name

    if clear_data:
        stdout_.write("".join(["Clearing application data: ",
                               display_name, "... "]))
    else:
        stdout_.write("".join(["Uninstalling ", display_name, "... "]))

    stdout_.flush()
    if check_packages:
        preinstall_log = device.shell_command("pm", "list", "packages",
                                              return_output=True,
                                              as_list=False).strip()
        if app_name not in preinstall_log:
            stdout_.write("ERROR: App was not found\n")
            return False

    if clear_data:
        uninstall_log = device.shell_command("pm", "clear", app_name,
                                             return_output=True,
                                             as_list=False).strip()
    else:
        uninstall_log = device.adb_command("uninstall", app_name,
                                           return_output=True,
                                           as_list=False).strip()

    # TODO: Use a better error/success detection method
    # - check if the app has been removed from list of available packages in pm
    # - don't know what to do for data cleaning though

    if uninstall_log.lower() != "success":
        if device.status != "device":
            stdout_.write("ERROR: Device has been suddenly disconnected!\n")
        else:
            stdout_.write("ERROR: Unexpected error!\n")
            for line in uninstall_log:
                stdout_.write(line + "\n")

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
    stdout_.flush()
    result = device.shell_command(command, target, return_output=True,
                                  as_list=False).strip()

    # TODO: Use a better error/success detection method
    # - use the device.is_type methods here

    # TODO: fix the mixed output type
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
    result = _clean_remove(device, remote, stdout_=stdout_)
    if int(result) < 0:
        stdout_.write(
            " ".join(["Cannot replace", remote, "due to unexpected error\n"]))
        return False

    stdout_.write(" ".join(["Placing", local, "in its place\n"]))
    device.adb_command("push", local, remote, stdout_=stdout_)

    _remote = remote
    if " " in _remote:
        _remote = '"{}"'.format(remote)

    if not device.is_file(_remote):
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

                  #1                   #2                #3  #4
CLEANER_OPTIONS = {"remove"           :(_clean_remove,    1, [False]),
                   "remove_recursive" :(_clean_remove,    1, [True]),
                   "replace"          :(_clean_replace,   2, []),
                   "uninstall"        :(_clean_uninstall, 1, []),
                   "clear_data"       :(_clean_uninstall, 1, [False, True])
                  }


def parse_cleaner_config(config=helper_.CLEANER_CONFIG):
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
        config = helper_.CLEANER_CONFIG

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
        for key, action in [("remove_recursive", "remove"),
                            ("remove", "remove"),
                            ("clear_data", "clear app data"),
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
                                                stdout_=stdout_)


def logcat_record(device, *filters, output_file=None, log_format="threadtime",
                  stdout_=sys.stdout):
    """"""
    # TODO: Simultaneously display and write the log if above verbosity threshold
    # e.g. Only display log in the console if verbosity in all filters is above
    # 'info' (that is also why I'm not using logcat -f /path/to/file)
    if not output_file:
        output_file = "logcat_" + strftime("%Y.%m.%d_%H.%M.%S") + ".log"

    stdout_.write("Recording logcat log, press ctrl+c to stop...\n")
    with open(output_file, mode="w", encoding="utf-8") as log_file:
        try:
            device.adb_command("logcat", "-v", log_format, *filters,
                               return_output=False, stdout_=log_file)
        except KeyboardInterrupt:
            pass
        stdout_.write("\nLog recording stopped.\n")
        # for some reason on Windows the try block above is not enough
        # an odd fix for an odd error
        try:
            pass
        except KeyboardInterrupt:
            pass

    return output_file
