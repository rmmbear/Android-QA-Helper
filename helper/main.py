"""Main module combining operations on apks and devices"""
import sys
import logging
from pathlib import Path
from time import strftime

import helper
from helper.apk import App

LOGGER = logging.getLogger(__name__)

#FIXME: Sprinkle this module with custom exception classes
# to replace the current approach of printing status messages everywhere


#FIXME: install should take two positional arguments: apk file and obb file list
def install(device, apk_file, obb_files=(), install_location="automatic",
            stdout_=sys.stdout, **kwargs):
    """Install an app.
    """
    apk_file = App(apk_file)
    stdout_.write(f"\nINSTALLING: {apk_file.app_name}\n")

    if install_app(device, apk_file, **kwargs):
        if obb_files:
            if apk_file.app_name.startswith("Unknown"):
                stdout_.write("ERROR: Unknown app name, cannot push obb files!\n")
                #TODO: remove the app if installation cannot be completed
                return False

            stdout_.write("\nCopying obb files...\n")
            for obb in obb_files:
                if not push_obb(device, obb, apk_file.app_name, stdout_=stdout_):
                    stdout_.write("ERROR: Failed to copy " + obb + "\n")
                    return False

        stdout_.write(f"\nSuccesfully installed {apk_file.app_name}\n")
        return True

    return False


def install_app(device, apk_file, install_location="automatic",
                installer_name="android.helper", keep_data=False, stdout_=sys.stdout):
    """Install an application from a local apk file."""
    possible_install_locations = {"automatic":"", "external":"-s",
                                  "internal":"-f"}

    if apk_file.app_name.startswith("Unknown"):
        LOGGER.warning("This app does not appear to be a valid .apk archive")
    else:
        is_compatible = apk_file.check_compatibility(device)
        if not is_compatible[0]:
            stdout_.write("WARNING: This apk and device are not compatible!\n")
            for reason in is_compatible[1]:
                stdout_.write(reason + "\n")

    device.extract_data(limit_to=["installed_packages"])

    if apk_file.app_name in device.info_dict["third-party_apps"]:
        stdout_.write("WARNING: Different version of the app already installed\n")
        if not uninstall_app(device, apk_file, keep_data, stdout_=stdout_):
            stdout_.write("ERROR: Could not uninstall the app!\n")
            return False
    elif apk_file.app_name in device.info_dict["system_apps"]:
        stdout_.write("WARNING: This app already exists on device as a system app!\n")
        stdout_.write("         System apps can only be upgraded to newer versions.\n")

    apk_filename = Path(apk_file.host_path).name
    destination = ("/data/local/tmp/helper_" + apk_filename).replace(" ", "_")

    stdout_.write("Copying the apk file to device...\n")
    device.adb_command("push", apk_file.host_path, destination, stdout_=stdout_)

    if not device.is_file(destination):
        stdout_.write("ERROR: Could not copy apk file to device\n")
        return False

    stdout_.write(f"Installing {apk_file.display_name}...\n")
    stdout_.write(
        f"Please check your device, as it may now ask you to confirm the installation.\n")

    destination = f"'{destination}'"
    device.shell_command("pm", "install", "-r", "-i", installer_name,
                         possible_install_locations[install_location],
                         destination, stdout_=stdout_)
    device.shell_command("rm", destination, stdout_=stdout_)


    device.extract_data(limit_to=["installed_packages"], force_extract=True)

    # TODO: detect installation failure for system apps
    if apk_file.app_name not in device.info_dict["third-party_apps"]:
        stdout_.write("ERROR: App could not be installed!\n")
        return False

    stdout_.write("Installation completed!\n")
    return True


def push_obb(device, obb_file, app_name, stdout_=sys.stdout):
    """Push obb expansion file to app's obb folder on device's
    internal SD card.
    """
    device.extract_data(limit_to=["storage"])

    # Prepare the target directory
    obb_folder = device.info_dict["internal_sd_path"] + "/Android/obb"
    device.shell_command("mkdir", obb_folder, return_output=True)
    device.shell_command("mkdir", obb_folder + "/" + app_name,
                         return_output=True)

    if not device.is_dir(obb_folder + "/" + app_name):
        stdout_.write("ERROR: Could not create obb folder.\n")
        return False

    obb_name = str(Path(obb_file).name)
    obb_target_file = "/".join([
        device.info_dict["internal_sd_path"], "Android/obb", app_name, obb_name])

    #pushing obb in two steps - some devices block pushing directly to obb folder
    device.adb_command("push", obb_file, device.info_dict["internal_sd_path"] + "/" + obb_name,
                       stdout_=stdout_)
    device.shell_command(
        "mv", f"'{device.info_dict['internal_sd_path']}/{obb_name}'",
        f"'{obb_target_file}'", stdout_=stdout_)

    if device.is_file(obb_target_file):
        return True

    stdout_.write("ERROR: Pushed obb file was not found in destination folder.\n")
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

    device.extract_data(limit_to=["available_commands", "storage", "identity"])

    if 'screenrecord' not in device.info_dict["shell_commands"]:
        stdout_.write(
            f"This device's shell does not have the 'screenrecord' command.")
        if int(device.info_dict["android_api_level"]) < 19:
            stdout_.write(
                " ".join(["The command was introduced with API level 19 (",
                          "Android version 4.4.4) and your device has API level",
                          device.info_dict["android_api_level"], "(Android version",
                          device.info_dict["android_version"], ").\n"]))
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


        #FIXME: remove interface-related code
        # this must only live in GUI/CLI modules
        # although a countdown could be useful
        try:
            input("Press enter whenever you are ready to record.\n")
        except KeyboardInterrupt:
            stdout_.write("\nRecording canceled!\n")
            return False
    if name:
        filename = name
    else:
        filename = "".join([device.filename, "_screenrecord_",
                            strftime("%Y.%m.%d_%H.%M.%S"), ".mp4"])

    remote_recording = "".join([
        device.info_dict["internal_sd_path"], "/", filename])

    #FIXME: handle DeviceOfflineError
    try:
        device.shell_command("screenrecord", "--verbose", remote_recording,
                             stdout_=stdout_)
    except KeyboardInterrupt:
        pass
    stdout_.write("\nRecording stopped.\n")

    device.reconnect(stdout_=stdout_)

    if not device.is_file(remote_recording):
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

    device.extract_data(limit_to=["storage", "identity"])

    anr_filename = "".join([device.filename, "_anr_",
                            strftime("%Y.%m.%d_%H.%M.%S"), ".txt"])

    remote_anr_file = "".join([device.info_dict["internal_sd_path"], "/", anr_filename])
    device.shell_command("cat", device.info_dict["anr_trace_path"], ">", remote_anr_file)

    if not device.is_file(remote_anr_file):
        stdout_.write("ERROR: The file was not found on device!\n")
        return False

    device.adb_command(
        "pull", remote_anr_file, str(output / anr_filename), stdout_=stdout_)

    if (output / anr_filename).is_file():
        return str((output / anr_filename).resolve())

    stdout_.write("ERROR: The file was not copied!\n")
    return False


def clear_app_data(device, app, stdout_=sys.stdout):
    """Clear app data.

    The app argument can be either package id or an initialized app object.
    """
    if isinstance(app, str):
        display_name = app
        app_name = app
    else:
        display_name = app.display_name
        app_name = app.app_name

    device.extract_data(limit_to=["installed_packages"])

    stdout_.write(
        f"Clearing application data: {display_name}... ")
    stdout_.flush()

    process_log = device.shell_command(
        "pm", "clear", app_name, return_output=True, as_list=False).strip()

    if process_log == "success":
        stdout_.write("Done\n")
        return True

    if app_name not in device.info_dict["system_apps"] and \
       app_name not in device.info_dict["third-party_apps"]:
        stdout_.write("ERROR: Application not found on device!\n")
        return False

    stdout_.write("ERROR: Could not clear data!\n")
    stdout_.write(process_log + "\n")
    return False


def uninstall_app(device, app, keep_data=False, stdout_=sys.stdout):
    """Uninstall applications from device.

    The app argument can be either package id or an initialized app object.
    """
    if isinstance(app, str):
        display_name = app
        app_name = app
    else:
        display_name = app.display_name
        app_name = app.app_name

    if keep_data:
        keep_data = "-k"
    else:
        keep_data = ""

    device.extract_data(limit_to=["installed_packages"])
    system_app = False

    if app_name in device.info_dict["system_apps"]:
        system_app = True
        stdout_.write(
            f"{display_name} is a system app and cannot be removed completely.\n")
        stdout_.write(f"Resetting {display_name} to factory version...")
    else:
        stdout_.write(f"Uninstalling {display_name}...")

    stdout_.flush()

    process_log = device.shell_command("pm", "uninstall", keep_data, app_name,
                                       return_output=True,
                                       as_list=False).strip().lower()

    if system_app:
        if process_log == "failure":
            stdout_.write("Cannot downgrade!\n")
            return False

        if process_log == "success":
            stdout_.write("Done\n")
            return True

        stdout_.write("ERROR: Unexpected error!\n")
        stdout_.write(process_log + "\n")
        return False

    device.extract_data(limit_to=["installed_packages"])
    if app_name in device.info_dict["third-party_apps"]:
        stdout_.write("ERROR: App could not be removed!\n")
        stdout_.write(process_log + "\n")
        return False

    stdout_.write("Done!\n")
    return True


def remove(device, target, recursive=False, stdout_=sys.stdout):
    """Remove file from device.

    Returns True after successful removal of the file or if it
    does not exist and False for permission error and unsuccessful
    removal.
    """
    if recursive:
        recursive = "-r"
    else:
        recursive = ""

    stdout_.write(f"Removing {target}...")
    stdout_.flush()

    # TODO: commented out is the solution that should be more reliable
    #       but which is broken for paths containing wildcards
    #
    #if not (device.is_file(target) or device.is_dir(target)):
    #    stdout_.write("File not found\n")
    #    return True

    #if not (device.is_file(target, check_write=True) or \
    #        device.is_dir(target, check_write=True)):
    #    stdout_.write("Permission denied\n")
    #    return False

    result = device.shell_command("rm", recursive, target,
                                  return_output=True, as_list=False).strip()
    if not result:
        stdout_.write("Done!\n")
        return True

    if "no such file or directory" in result.lower():
        stdout_.write("File not found\n")
        return True

    if "permission denied" in result.lower():
        stdout_.write("Permission denied\n")
        return False

    #if not (device.is_file(target) or device.is_dir(target)):
    #    stdout_.write("Done!\n")
    #    return True

    stdout_.write("Unexpected error:\n")
    stdout_.write(f"{result}\n")
    return False


def replace(device, remote, local, stdout_=sys.stdout):
    """Replace remote file with user-provided one."""
    if not remove(device, remote, stdout_=stdout_):
        stdout_.write(f"Cannot replace {remote}\n")
        return False

    stdout_.write(f"Placing {Path(local).name} in its place...")
    stdout_.flush()

    device.adb_command("push", local, remote, stdout_=stdout_)

    if not device.is_file(remote):
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

                  #1                   #2               #3  #4
CLEANER_OPTIONS = {"remove"           :(remove,         1, [False]),
                   "remove_recursive" :(remove,         1, [True]),
                   "replace"          :(replace,        2, []),
                   "uninstall"        :(uninstall_app,  1, []),
                   "clear_data"       :(clear_app_data, 1, [])
                  }


def parse_cleaner_config(config=helper.CLEANER_CONFIG):
    """Parse the provided cleaner_config file. If no file is provided,
    parse the default config file.

    Return tuple containing parsed config (dict) and bad config (list).
    The former can be passed to clean().
    """
    parsed_config = {}
    bad_config = []
    #FIXME: time for a rewrite
    # shout-outs to past me for this very naive and unnecessarily commplicated
    # implementation od a domain-specific-language without knowing what a dsl is
    #TODO: translate paths prvoided in the config into actual paths on device
    #
    for count, line in enumerate(open(config, mode="r").readlines()):
        if line.strip().startswith("#") or not line.strip():
            continue

        count += 1

        pair = line.split(":", maxsplit=1)
        if len(pair) != 2:
            bad_config.append(f"Line {count}: No value")
            continue

        key = pair[0].strip()
        value = pair[1].strip()

        if key not in CLEANER_OPTIONS:
            bad_config.append(
                f"Line {count}: Unknown command")
            continue

        if not value:
            bad_config.append(f"Line {str(count)}: No value")
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
                f"Line{count}: Expected {expected} argument{plural} but got {got}")
            continue

        parsed_config[key].append(items)

    return (parsed_config, bad_config)


def clean(device, config=None, parsed_config=None, force=False,
          stdout_=sys.stdout):
    """Clean the specified device using instructions contained in
    cleaner_config file.
    """
    # TODO: Count the number of removed files / apps
    bad_config = ""

    if config is None:
        config = helper.CLEANER_CONFIG
    #TODO: separate this function from the parser entirely
    if not parsed_config:
        parsed_config, bad_config = parse_cleaner_config(config=config)

    if bad_config:
        stdout_.write(f"Errors encountered in the config file ({config}):\n")
        stdout_.write("\n".join(bad_config))
        stdout_.write("Aborting cleaning!\n")
        return False

    if not parsed_config:
        stdout_.write("Empty config! Cannot clean!\n")
        return False

    #FIXME: remove interface-related code
    # this must only live in GUI/CLI modules
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
                stdout_.write(f"{action} : {item[0]} \n")

        if "replace" in parsed_config:
            for pair in parsed_config["replace"]:
                stdout_.write(f"\nThe file: {pair[0]}\n")
                stdout_.write(f"{indent * ' '}will be replaced with:\n")
                stdout_.write(f"{indent * '  '}{pair[1]} \n")

        stdout_.write("\nContinue?\n")

        while True:
            usr_choice = input("Y/N : ").strip().upper()
            if usr_choice == "N":
                stdout_.write("Cleaning canceled!\n")
                return False
            if usr_choice == "Y":
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
        output_file = "".join([device.filename, "_logcat_",
                               strftime("%Y.%m.%d_%H.%M.%S"), ".log"])

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
