"""Main module combining operations on apks and devices"""

import sys
from pathlib import Path
from time import strftime, sleep

import helper as helper_
from helper.apk import get_app_name

def install(device, *items, stdout_=sys.stdout):
    """Install apps.
    Accepts either a list of apk files, or list with one apk and as many
    obb files as you like.
    """
    apk_list = []
    obb_list = []

    for item in items:
        if item[-3:].lower() == "apk":
            apk_list.append(item)

        if item[-3:].lower() == "obb":
            obb_list.append(item)

    if len(apk_list) > 1 and obb_list:
        stdout_.write(" ".join(["APK ambiguity! Only one apk file can be",
                                "installed when also pushing obb files!\n"]))
        return False

    if not apk_list:
        stdout_.write("No APK found among provided files, aborting!\n")
        return False

    if not obb_list:
        install_apks_only(device, apk_list, stdout_=stdout_)
    else:
        install_with_obbs(device, apk_list[0], obb_list, stdout_=stdout_)


def install_apks_only(device, apk_list, stdout_=sys.stdout):
    app_failure = []

    for apk_file in apk_list:
        app_name = get_app_name(apk_file, stdout_=stdout_)
        stdout_.write(" ".join(["\nINSTALLING:", app_name, "\n"]))
        stdout_.write("Your device may ask you to confirm this!\n")

        if not install_application(device, apk_file, app_name, stdout_=stdout_):
            app_failure.append(app_name)

    if len(apk_list) > 1:
        stdout_.write(
            " ".join(["\nInstalled", str(len(apk_list) - len(app_failure)),
                      "out of", str(len(apk_list)), "provided apks.\n"]))
        if app_failure:
            stdout_.write("The following apks could not be installed:\n")
            for app_name in app_failure:
                stdout_.write("".join([app_name, "\n"]))


def install_with_obbs(device, apk_file, obb_list, stdout_=sys.stdout):
    app_name = get_app_name(apk_file, stdout_=stdout_)

    stdout_.write(" ".join(["\n", "INSTALLING:", app_name, "\n"]))
    stdout_.write("Your device may ask you to confirm this!\n")

    if not install_application(device, apk_file, app_name, stdout_=stdout_):
        return False

    stdout_.write(" ".join(["\nCOPYING OBB FILES FOR:", app_name, "\n"]))
    prepare_obb_dir(device, app_name)
    for obb_file in obb_list:
        if not push_obb(device, obb_file, app_name, stdout_=stdout_):
            stdout_.write("ERROR: Failed to copy " + obb_file + "\n")
            return False
    stdout_.write("\nSuccesfully installed {}!\n".format(app_name))


def install_application(device, apk_file, app_name, stdout_=sys.stdout):
    """Install an app on specified device."""
    preinstall_log = device.shell_command(
        "pm", "list", "packages", return_output=True, as_list=False)

    if app_name in preinstall_log:
        stdout_.write(" ".join(["WARNING: Different version of the app",
                                "already installed\n"]))
        result = _clean_uninstall(
            device, target=app_name, app_name=True, check_packages=False)
        if not result:
            return False

    device.adb_command("install", "-r", "-i", "com.android.vending",
                       apk_file, stdout_=stdout_)
    postinstall_log = device.shell_command("pm", "list", "packages",
                                           return_output=True)
    for log_line in postinstall_log:
        if app_name in log_line:
            return True

    if device.status != "device":
        stdout_.write("ERROR: Device has been suddenly disconnected!\n")
    else:
        if app_name.startswith("UNKNOWN APP NAME"):
            stdout_.write(
                "ERROR: No app name, cannot verify installation outcome\n")
        else:
            stdout_.write(
                "ERROR: Installed app was not found by package manager\n")
            stdout_.write(app_name + " could not be installed!\n")
            stdout_.write(
                "Please make sure that your device meets app's criteria\n")
    return False


def prepare_obb_dir(device, app_name):
    """Prepare the obb directory for installation."""
    # pipe the stdout to suppress unnecessary errors
    obb_folder = device.ext_storage + "/Android/obb"
    device.shell_command("mkdir", obb_folder, return_output=True)
    device.shell_command(
        "rm", "-r", obb_folder + "/" + app_name, return_output=True)
    device.shell_command(
        "mkdir", obb_folder + "/" + app_name, return_output=True)


def push_obb(device, obb_file, app_name, stdout_=sys.stdout):
    """Push <obb_file> to /mnt/sdcard/Android/obb/<your.app.name> on
    <Device>.

    File is copied to primary storage, and from there to the obb folder.
    This is done in two steps because attempts to 'adb push' it directly
    into obb folder may fail on some devices.
    """
    obb_name = str(Path(obb_file).name)
    obb_target = "".join([device.ext_storage, "/Android/obb/", app_name, "/",
                          obb_name])

    #pushing obb in two steps to circumvent write protection
    device.adb_command("push", obb_file, device.ext_storage + "/" + obb_name,
                       stdout_=stdout_)
    device.shell_command("mv", "".join(['"', device.ext_storage, "/",
                                        obb_name, '"']),
                         "".join(['"', obb_target, '"']))
    push_log = device.shell_command("ls", "".join(['"', obb_target, '"']),
                                    return_output=True, as_list=False)
    if push_log == obb_target:
        return True

    if device.status != "device":
        stdout_.write("ERROR: Device has been suddenly disconnected!\n")
    else:
        stdout_.write(
            "ERROR: Pushed obb file was not found in destination folder.\n")
    return False


def record_start(device, name=None, stdout_=sys.stdout):
    """Start recording on specified device. Path of the created clip
    is returned after the recording has stopped.

    If a name is not given, generate a name from current date and time.
    """
    filename = "screenrecord_" + strftime("%Y.%m.%d_%H.%M.%S") + ".mp4"
    if name:
        filename = name
    remote_recording = device.ext_storage + "/" + filename

    try:
        device.shell_command("screenrecord", "--verbose", remote_recording,
                             return_output=False, stdout_=stdout_)
    except KeyboardInterrupt:
        pass
    stdout_.write("\nRecording stopped.\n")
    # for some reason on Windows the try block above is not enough
    # an odd fix for an odd error
    try:
        # we're waiting for the clip to be fully saved to device's storage
        # there must be a better way of doing this...
        sleep(1)
    except KeyboardInterrupt:
        sleep(1)
    return remote_recording


def record_copy(device, remote_recording, output, stdout_=sys.stdout):
    """Start copying recorded clip from device's storage to disk.
    """
    recording_log = device.shell_command("ls", remote_recording,
                                         return_output=True, as_list=False)
    if recording_log != remote_recording:
        if device.status != "device":
            stdout_.write("ERROR: Device has been suddenly disconnected!\n")
        else:
            stdout_.write("ERROR: The file was not found on device!\n")
        return False

    filename = Path(remote_recording).name
    filename = device.info["Product"]["Model"] + "_" + filename
    output = str(Path(Path(output).resolve(), filename))

    device.adb_command("pull", remote_recording, output, return_output=False,
                       stdout_=stdout_)
    if Path(output).is_file():
        return output

    return False


def record(device, output=None, force=False, stdout_=sys.stdout):
    """Start recording device's screen.
    Recording can be stopped by either reaching the time limit, or
    pressing ctrl+c. After the recording has stopped, the helper
    confirms that the recording has been saved to device's storage and
    copies it to drive.
    """
    # existence of "screenrecord" is dependent on Android version, but let's
    # look for command instead, just to be safe
    if not "screenrecord" in device.available_commands:
        android_ver = device.info["OS"]["Android Version"]
        api_level = device.info["OS"]["Android API Level"]
        stdout_.write(
            " ".join(["This device's shell does not have the 'screenrecord'",
                      "command. It is available on all devices with Android",
                      "4.4 or higher (API level 19 or higher). Your device",
                      "has Android", android_ver, "API level", api_level,
                      "\n"]))
        return False

    if not output:
        output = str(Path().resolve())
    else:
        output = str(Path(output).resolve())

    if not force:
        stdout_.write(
            "".join(["Helper will record your device's screen (audio is not ",
                     "captured). The recording will stop after pressing ",
                     "'ctrl+c', or if 3 minutes have elapsed. Recording will ",
                     "be then saved to:\n", output, "\n"]))
        try:
            input("Press enter whenever you are ready to record.\n")
        except KeyboardInterrupt:
            stdout_.write("\nRecording canceled!\n")
            return False

    remote_recording = record_start(device, stdout_=stdout_)
    if not remote_recording:
        stdout_.write("ERROR: Unexpected error! Could not record\n")
        return False

    copied = record_copy(device, remote_recording, output, stdout_=stdout_)
    if not copied:
        stdout_.write("ERROR: Could not copy recorded clip!\n")
        return False

    return copied


def pull_traces(device, output=None, stdout_=sys.stdout):
    """Copy the 'traces' file to the specified folder."""
    if output is None:
        output = Path().resolve()
    else:
        output = Path(output).resolve()

    anr_filename = "".join([device.info["Product"]["Model"], "_anr_",
                            strftime("%Y.%m.%d_%H.%M.%S"), ".txt"])
    remote_anr_file = "".join([device.ext_storage, "/", anr_filename])
    device.shell_command("cat", device.anr_trace_path, ">", remote_anr_file)

    cat_log = device.shell_command("ls", remote_anr_file, return_output=True,
                                   as_list=False)
    if cat_log != remote_anr_file:
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


def _clean_uninstall(device, target, app_name=False, check_packages=True,
                     stdout_=sys.stdout):
    """Uninstall an app from specified device. Target can be an app name
    or a path to apk file -- by default it will check if target is a
    file, and if so it will attempt to extract app name from it.
    To disable that, set "app_name" to True.
    """
    if Path(target).is_file() and not app_name:
        target = get_app_name(target, stdout_=stdout_)

    stdout_.write(" ".join(["Uninstalling", target, "... "]))
    if check_packages:
        preinstall_log = device.shell_command(
            "pm", "list", "packages", return_output=True, as_list=False)
        if target not in preinstall_log:
            stdout_.write("ERROR: App was not found\n")
            return False

    uninstall_log = device.adb_command("uninstall", target, return_output=True)
    if uninstall_log[-1] != "Success":
        if device.status != "device":
            stdout_.write("ERROR: Device has been suddenly disconnected!\n")
            return False
        else:
            stdout_.write("Unexpected error!\n")
            stdout_.write(
                " ".join(["ERROR:", target, "could not be uninstalled!\n"]))
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
    result = device.shell_command(command, target, return_output=True,
                                  as_list=False).strip()
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
    push_log = device.shell_command("ls", _remote, return_output=True,
                                    as_list=False)
    if push_log != remote:
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

                  #1                   #2                 #3  #4
CLEANER_OPTIONS = {"remove"           :(_clean_remove,     1, [False]),
                   "remove_recursive" :(_clean_remove,     1, [True]),
                   "replace"          :(_clean_replace,    2, []),
                   "uninstall"        :(_clean_uninstall,  1, [])
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
        for key, action in [("remove", "remove"),
                            ("remove_recursive", "remove"),
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
