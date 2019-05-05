"""Command line interface module"""
import sys
import logging
from pathlib import Path
from argparse import ArgumentParser

import helper as helper_
import helper.main as main_
import helper.device as device_

LOGGER = logging.getLogger(__name__)

HELPER_CLI_DESC = helper_.VERSION_STRING

PARSER = ArgumentParser(prog="helper", description=HELPER_CLI_DESC)
PARSER.add_argument(
    "-v", "--version", action="version", version=helper_.VERSION_STRING)

COMMANDS = PARSER.add_subparsers(title="Commands", dest="command", metavar="")

### Gneral-use optional arguments
OPT_DEVICE = ArgumentParser("device", add_help=False)
OPT_DEVICE.add_argument(
    "-d", "--device", default="", metavar="device",
    help="""Specify command target by passing a device's serial number.
    This value must be given if there are multiple devices connected.""")

OPT_OUTPUT = ArgumentParser("output", add_help=False)
OPT_OUTPUT.add_argument(
    "-o", "--output", default=".", metavar="directory",
    help="""Specify the output directory. If no directory is chosen, the files
    will be saved in the same directory helper was launched from.""")


### Helper Commands definitions
CMD = COMMANDS.add_parser(
    "install", parents=[OPT_DEVICE, OPT_OUTPUT], aliases=["i"],
    help="Install one or more apps on a device.",
    epilog="""If another version of the app being installed is already on the
    device, helper will attempt to remove it and all its data first before
    replacing them. Note that system apps can only be replaced with newer
    versions and the '--replace_system_apps' option must be specified.""")

CMD.add_argument(
    "install", nargs="+", metavar="files",
    help=".apk file(s) or one apk and its obb expansion file(s).")

CMD.add_argument(
    "--keep-data", action="store_true",
    help="Keep data and cache directories when replacing apps.")

CMD.add_argument(
    "--location", choices=["internal", "external"], default="automatic",
    help="""Set the install location to either internal or external SD card. By
    default it is set to 'automatic', which lets the device decide the location
    based on available storage space and install location set in app's
    AndroidManifest.xml.""")

CMD.add_argument(
    "--installer-name", default="android.helper",
    help="""Use this option to set the installer name used during installation.
    By default it is 'android.helper'. Under normal circumstances this would be
    the name of the appstore app used, so for example:
    com.sec.android.app.samsungapps (Samsung Galaxy Apps),
    com.android.vending (Google Play Store),
    com.amazon.mShop.android (Amazon Underground - Android app),
    com.amazon.venezia (Amazon appstore - native Kindle Fire).
    Changing installer name may be useful for testing store-specific
    functionality.""")

CMD = COMMANDS.add_parser(
    "clean", parents=[OPT_DEVICE, OPT_OUTPUT], aliases="c",
    help="Clean the device storage as per the instructions in cleaner config.",
    epilog=f"""By default, this command removes only helper-created
    files but its behavior can be customized with cleaner config file.
    Currently available options are: removing files and directories, clearing
    app data, uninstalling apps and replacing files on device with local
    versions. For configuration example, see the default config file:
    {helper_.CLEANER_CONFIG}.""")

CMD.add_argument(
    "clean", nargs="?", default=helper_.CLEANER_CONFIG, metavar="config",
    help="""Path to a valid cleaner config file. For example of a
    valid config, see the default file in this program's root directory.""")

CMD = COMMANDS.add_parser(
    "record", parents=[OPT_DEVICE, OPT_OUTPUT], aliases="r",
    help="Record the screen of your device.",
    epilog="""To stop and save the recorded video, press 'ctrl+c'.
    Videos have a hard time-limit of three minutes -- this is imposed by
    the internal command and cannot be extended -- recording will be stopped
    automatically after reaching that limit. NOTE: Sound is not recorded.""")

CMD = COMMANDS.add_parser(
    "traces", parents=[OPT_DEVICE, OPT_OUTPUT], aliases="t",
    help="Save the dalvik vm stack traces (aka ANR log) to a file.",
    epilog="Save the dalvik vm stack traces (aka ANR log) to a file.")

# TODO: Update detailed description after implementing obb extraction
CMD = COMMANDS.add_parser(
    "extract-apk", parents=[OPT_DEVICE, OPT_OUTPUT], aliases="x",
    help="""Extract the .apk file of an installed application.""",
    epilog="""Extract the .apk file from device's storage. On some devices
    the archives cannot be extracted. In general, if it is possible to
    extract third part apps, it should be also possible to the same with
    system apps. Note: app's expansion files (OBBs) cannot yet be extracted.""")

CMD.add_argument(
    "extract_apk", nargs="+", metavar="app name",
    help="Package ID of an installed app. For example: android.com.browser.")

COMMANDS.add_parser(
    "scan", aliases="s",
    help="Show status of all connected devices.",
    epilog="""Scan shows serial number, manufacturer, model and connection
    status of all devices connected. If a connection with device could not
    be established, only its serial and connection status is shown.""")

COMMANDS.add_parser(
    "dump", aliases=["d"], parents=[OPT_DEVICE, OPT_OUTPUT],
    help="Dump all available device information to file.",
    epilog="Dump all available device information to file.")

CMD = COMMANDS.add_parser(
    "shell", aliases=["sh"], parents=[OPT_DEVICE],
    help="Issue a shell command for a device.",
    epilog="Issue a shell command for a device.")

CMD.add_argument(
    "command_", nargs="+", metavar="command",
    help="""Note: put "--" as the first argument to suppress argument parsing
    (necessary if your shell command contains dashes).""")

CMD = COMMANDS.add_parser(
    "adb", parents=[OPT_DEVICE],
    help="Issue an adb command for a device.",
    epilog="Issue an adb command for a device.")

CMD .add_argument(
    "command_", nargs="+", metavar="command",
    help="""Note: put "--" as the first argument to suppress argument parsing
    (necessary if your shell command contains dashes).""")


### Hidden commands
#COMMANDS.add_parser("gui")
CMD = COMMANDS.add_parser("debug-dump", parents=[OPT_DEVICE, OPT_OUTPUT])
CMD.add_argument("--full", action="store_true")
COMMANDS.add_parser("run-tests")

del CMD
PARSER_NO_ARGS = PARSER.parse_args([])


def pick_device():
    """Ask the user to pick a device from list of currently connected
    devices. If only one is available, it will be chosen automatically.
    None is returned if there aren't any devices.
    """
    device_list = device_.get_devices(limit_init=["identity"])
    if not device_list:
        return None

    if len(device_list) == 1:
        return device_list[0]

    print("Multiple devices detected!\n")
    print("Please choose which of devices below you want to work with.\n")
    for counter, device in enumerate(device_list):
        print(f"{counter} : {device.name}")

    while True:
        print("Pick a device: ")
        user_choice = input().strip()
        if not user_choice.isnumeric():
            print("The answer must be a number!")
            continue

        user_choice = int(user_choice)
        if user_choice < 0  or user_choice >= len(device_list):
            print("Answer must be one of the above numbers!")
            continue

        return device_list[user_choice]


def record(device, args):
    destination = main_.record(device, args.output)
    if destination:
        print("Recorded video was saved to:")
        print(destination)
        return destination

    return False


def install(device, args):
    for filepath in args.install:
        if not Path(filepath).is_file():
            print("ERROR: Provided path does not point to an existing file:")
            print(filepath)
            return

    main_.install(device, *args.install, install_location=args.location,
                  keep_data=args.keep_data, installer_name=args.installer_name)


def pull_traces(device, args):
    """"""
    destination = main_.pull_traces(device, args.output)
    if destination:
        print("Traces file was saved to:")
        print(destination)
        return True

    return False


def extract_apk(device, args):
    for app_name in args.extract_apk:
        out = device.extract_apk(app_name, args.output)
        if out:
            print("Package saved to:")
            print(out)


def clean(device, args):
    """"""
    config_file = args.clean
    if not Path(config_file).is_file():
        print("Provided path does not point to an existing config file:")
        print(config_file)
        return

    main_.clean(device, config_file)


def scan(args):
    """"""
    format_str = "{:4}{:13}{:14}{:10}{}"
    #       #, serial, manufacturer, model, status
    #TODO: automatically change format string based on what's connected
    #      the end result should be a table that automatically adjusts
    #      column width to its contents
    headers = ["#", "serial num", "manufacturer", "model", "status"]
    device_list = device_.get_devices(True, limit_init=["identity"])
    device_ids = {device.serial:device for device in device_list}

    print(format_str.format(*headers))
    if not device_ids:
        print(format_str.format(*(5*"None")))
        return

    for count, device in enumerate(device_list):
        del device_ids[device.serial]

        print(format_str.format(
            "{}.".format(count), device.serial,
            device.info_dict["device_manufacturer"],
            device.info_dict["device_model"],
            device._status))

    if device_ids:
        print("\nThe following devices could not be initialized:")
        for serial, status in device_ids.items():
            print(f"{serial} : {status}")
        print()


def detailed_scan(device, args):
    """"""
    device.extract_data(limit_to=["identity"])
    print(f"Collecting info from {device.name} ...")

    info_string = device.full_info_string()
    if args.output:
        filename = f"{device.filename}_REPORT"
        output_path = (Path(args.output) / filename).resolve()
        with output_path.open(mode="w") as device_report:
            device_report.write(info_string)
        print(f"Report saved to {str(output_path)}")
    else:
        print(info_string)


def debug_dump(device, args):
    print("Please remember that ALL dumped files may contain sensitive data. Use caution.")

    from helper.tests import dump_device

    dump_device(device, args.output, args.full)


def run_tests():
    try:
        import pytest
    except ImportError:
        print("Could not import pytest, cannot run tests")
        return
    sys.argv = [sys.argv[0]]
    pytest.main()


def shell_command(device, args):
    """"""
    print()
    device.shell_command(*args.command_, return_output=False, check_server=False)


def adb_command(args):
    """"""
    device_.adb_command(*args.command_, return_output=False, check_server=False)


COMMAND_DICT = { #command : (function, required_devices),
    #No device commands
    "adb":(adb_command, 0),
    "run-tests":(run_tests, 0),
    "scan":(scan, 0), "s": (scan, 0),
    #Single device commands
    "extract":(extract_apk, 1), "x":(extract_apk, 1),
    "install":(install, 1), "i":(install, 1),
    "record":(record, 1), "r":(record, 1),
    "shell":(shell_command, 1), "sh":(shell_command, 1),
    "traces":(pull_traces, 1), "t":(pull_traces, 1),
    #Multi device commands
    #these commands will run even when only one device is available
    "clean":(clean, 2), "c":(clean, 2),
    "debug-dump":(debug_dump, 2),
    "dump":(detailed_scan, 2), "d":(detailed_scan, 2),
}


def main(args=None):
    """Parse and execute input commands."""
    LOGGER.info("Starting parsing arguments")
    args = PARSER.parse_args(args)

    LOGGER.info("Starting helper with option %s", args.command)

    if args == PARSER_NO_ARGS:
        PARSER.parse_args(["-h"])
        return

    #if args.command == "gui":
    #    LOGGER.info("Launching GUI")
    #    from helper.GUI import helper_gui
    #    sys.exit(helper_gui.main())

    if hasattr(args, "output"):
        if not Path(args.output[0]).is_dir():
            print("ERROR: The provided path does not point to an existing directory!")
            return

    command, required_devices = COMMAND_DICT[args.command]

    #No devices required, call function directly
    if required_devices == 0:
        command(args)
        return

    chosen_device = None

    #TODO: Implement a timeout
    print("Waiting for any device to come online...")
    device_.adb_command('wait-for-device', return_output=True)

    connected_devices = device_.get_devices(initialize=False)
    connected_serials = {device.serial:device for device in connected_devices}

    if hasattr(args, "device"):
        if args.device:
            LOGGER.debug("Chosen device set to %s", args.device)
            try:
                chosen_device = connected_serials[args.device]
            except KeyError:
                print(f"Device with serial number {args.device} was not found by Helper!")
                return

    #TODO: implement concurrent commands
    if required_devices == 1:
        if not chosen_device:
            chosen_device = pick_device()

        try:
            command(chosen_device, args)
        except device_.DeviceOfflineError:
            print("Device has been suddenly disconnected!")

    if required_devices == 2:
        if chosen_device:
            connected_devices = [chosen_device]
        for device in connected_devices:
            try:
                command(device, args)
            except device_.DeviceOfflineError:
                print(f"Device {device.name} has been suddenly disconnected!")

#TODO: Implement screenshot command
#TODO: Implement app inspector as separate command
#TODO: Implement keyboard and keyboard-interactive
#      Enter text into textfields on Android device using PC's keyboard
