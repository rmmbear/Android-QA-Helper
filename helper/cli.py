""""""
import sys
from pathlib import Path
from argparse import ArgumentParser

import helper as helper_
import helper.main as main_
import helper.device as device_


HELPER_CLI_DESC = helper_.VERSION_STRING

PARSER = ArgumentParser(prog="helper", description=HELPER_CLI_DESC)
PARSER.add_argument("-v", "--version", action="version",
                    version="".join([helper_.VERSION_STRING, " : ",
                                     helper_.COPYRIGHT_STRING]))
COMMANDS = PARSER.add_subparsers(title="Commands", dest="command", metavar="")

### Gneral-use optional arguments
HELP_DEVICE = """Specify command target by passing a device's serial number.
This value must be given if there are multiple devices connected."""
OPT_DEV = ArgumentParser("device", add_help=False)
OPT_DEV.add_argument("-d", "--device", default="", metavar="device",
                     help=HELP_DEVICE)

HELP_OUTPUT = """Specify the output directory. If no directory is chosen, the
files will be saved in the same directory helper was launched from."""
OPT_OUT = ArgumentParser("output", add_help=False)
OPT_OUT.add_argument("-o", "--output", default=".", metavar="directory",
                     help=HELP_OUTPUT)


### Helper Commands definitions
HELP_INSTALL = """Install one or more apps on a device."""
HELP_INSTALL_DETAIL = """If another version of the app being installed is
already on the device, helper will attempt to remove it and all its data first
before replacing them. Note that system apps can only be replaced with newer
versions and the '--replace_system_apps' option must be specified."""
CMD = COMMANDS.add_parser("install", parents=[OPT_DEV, OPT_OUT], aliases=["i"],
                          help=HELP_INSTALL, epilog=HELP_INSTALL_DETAIL)
HELP_INSTALL_FILES = """.apk file(s) or one apk and its obb expansion
file(s)."""
CMD.add_argument("install", nargs="+", metavar="files",
                 help=HELP_INSTALL_FILES)
HELP_INSTALL_KEEP = """Keep data and cache directories when replacing apps."""
CMD.add_argument("--keep-data", action="store_true", help=HELP_INSTALL_KEEP)
HELP_INSTALL_LOCATION = """Set the install location to either internal or
external SD card. By default it is set to 'automatic', which lets the device
decide the location based on available storage space and install location set
in app's AndroidManifest.xml."""
CMD.add_argument("--location", choices=["internal", "external"],
                 default="automatic", help=HELP_INSTALL_LOCATION)
HELP_INSTALL_NAME = """Use this option to set the installer name used during
installation. By default it is 'android.helper'. Under normal circumstances
this would be the name of the appstore app used, so for example:
com.sec.android.app.samsungapps (Samsung Galaxy Apps), com.android.vending
(Google Play Store), com.amazon.mShop.android (Amazon Underground),
com.amazon.venezia (Amazon appstore--the native appstore app for Kindle Fire).
Changing installer name may be useful for testing store-specific functionality.
"""
CMD.add_argument("--installer-name", default="android.helper",
                 help=HELP_INSTALL_NAME)


HELP_CLEAN = """Clean various files from a device. """
HELP_CLEAN_DETAIL = """By default, this command removes only helper-created
files but its behavior can be customized with cleaner config file. Currently
available options are: removing files and directories, clearing app data,
uninstalling apps and replacing files on device with local versions. For
configuration example, see the default config file: {}.
""".format(helper_.CLEANER_CONFIG)
CMD = COMMANDS.add_parser("clean", parents=[OPT_DEV, OPT_OUT], aliases="c",
                          help=HELP_CLEAN, epilog=HELP_CLEAN_DETAIL)
HELP_CLEAN_CONFIG = """Path to a valid cleaner config file. For example of a
valid config, see the default file in this program's root directory."""
CMD.add_argument("clean", nargs="?", default=helper_.CLEANER_CONFIG,
                 metavar="config", help=HELP_CLEAN_CONFIG)


HELP_RECORD = """Record the screen of your device."""
HELP_RECORD_DETAIL = """To stop and save the recorded video, press 'ctrl+c'.
Videos have a hard time-limit of three minutes--this is imposed by the internal
command and cannot be extended--recording will be stopped automatically after
reaching that limit. NOTE: Sound is not, and cannot be recorded."""
CMD = COMMANDS.add_parser("record", parents=[OPT_DEV, OPT_OUT], aliases="r",
                          help=HELP_RECORD, epilog=HELP_RECORD_DETAIL)


# TODO: Write a more detailed description of the traces function
# It's pretty straightforward, so I don't know if there's anything else
# worth mentioning?
HELP_TRACES = """Save the dalvik vm stack traces (aka ANR log) to a file."""
CMD = COMMANDS.add_parser("traces", parents=[OPT_DEV, OPT_OUT], aliases="t",
                          help=HELP_TRACES, epilog=HELP_TRACES)


HELP_EXTRACT = """Extract the .apk file of an installed application."""
# TODO: Update detailed description after implementing obb extraction
HELP_EXTRACT_DETAIL = """Extract the .apk file from device's storage. On some
devices the archives cannot be extracted. In general, if it is possible to
extract third part apps, it should be also possible to the same with system
apps. Note: app's expansion files cannot yet be extracted."""
CMD = COMMANDS.add_parser("extract-apk", parents=[OPT_DEV, OPT_OUT],
                          aliases="x", help=HELP_EXTRACT,
                          epilog=HELP_EXTRACT_DETAIL)
HELP_EXTRACT_NAME = """Package ID of an installed app. For example:
android.com.browser."""
CMD.add_argument("extract_apk", nargs="+", metavar="app name",
                 help=HELP_EXTRACT_NAME)


HELP_SCAN = """Show status of all connected devices."""
HELP_SCAN_DETAIL = """Scan shows serial number, manufacturer, model and
connection status of all devices connected. If a connection with device could
not be established, only its serial and connection status is shown."""
CMD = COMMANDS.add_parser("scan", aliases="s", help=HELP_SCAN,
                          epilog=HELP_SCAN_DETAIL)


HELP_DSCAN = """Show status and detailed information of connected devices."""
HELP_DSCAN_DETAIL = """Detailed scan displays all info from normal scan as well as
amount of available RAM, version of the OS and basic specifications of the GPU,
CPU and display."""
CMD = COMMANDS.add_parser("detailed-scan", parents=[OPT_DEV, OPT_OUT],
                          aliases=["ds"], help=HELP_DSCAN,
                          epilog=HELP_DSCAN_DETAIL)

# TODO: Write a more detailed description of the dump function
# It's pretty straightforward, so I don't know if there's anything else
# worth mentioning?
HELP_DUMP = """Dump all available device information to file."""
CMD = COMMANDS.add_parser("dump", parents=[OPT_DEV, OPT_OUT],
                          help=HELP_DUMP, epilog=HELP_DUMP)

### Hidden commands
COMMANDS.add_parser("gui")
COMMANDS.add_parser("debug-dump", parents=[OPT_OUT])

# Example of caring too much about aesthetics
for group in  PARSER._action_groups:
    if group.title == 'optional arguments':
        group.title = None

PARSER_NO_ARGS = PARSER.parse_args([])


def pick_device():
    """Ask the user to pick a device from list of currently connected
    devices. If there are no devices to choose from, it will return the
    sole connected device or None, if there are no devices at all.
    """
    # TODO: fix pick_devices()
    raise NotImplementedError
    #device_list = get_devices(stdout_, initialize, limit_init)
    device_list = []
    if not device_list:
        return None

    if len(device_list) == 1:
        return device_list[0]

    while True:
        print("Multiple devices detected!\n")
        print("Please choose which of devices below you want to work with.\n")
        for counter, device in enumerate(device_list):
            print(" ".join([counter, ":"]))
            print(device.basic_info_string())

        print("Enter your choice: ")
        user_choice = input().strip()
        if not user_choice.isnumeric():
            print("The answer must be a number!\n")
            continue

        user_choice = int(user_choice)
        if user_choice < 0  or user_choice >= len(device_list):
            print("Answer must be one of the above numbers!\n")
            continue

        return device_list[user_choice]


def record(device, args):
    destination = main_.record(device, args.output)
    if destination:
        print("Recorded video was saved to:", destination, sep="\n")
        return destination

    return False


def install(device, args):
    for filepath in args.install:
        if not Path(filepath).is_file():
            print("ERROR: Provided path does not point to an existing file:")
            print(filepath)
            return False

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
            print("Package saved to", out)


def clean(device, args):
    """Remove device as set in cleaner config. Batch command"""
    config_file = args.clean
    if not Path(config_file).is_file():
        print("Provided path does not point to an existing config file:")
        print(config_file)
        return False

    main_.clean(device, config_file)


def scan_connected(device, args):
    """"""
    format_str = "{:13}{:15}{:10}{}"
    device.extract_data(limit_to=["identity"])
    print(format_str.format(
        device.serial, device.info_dict["device_manufacturer"],
        device.info_dict["device_model"], device._status))


def scan_other():
    """"""
    other_devices = device_._get_devices()
    for device in other_devices:
        if device[1] == "device":
            other_devices.remove(device)

    if other_devices:
        print("The following devices could not be initialized:")
        for serial, status in other_devices:
            print(serial, ":", status)
        print()


def detailed_scan(device, args):
    """"""
    device.extract_data(limit_to=["identity"])
    print("Collecting info from", device.name, "...")
    print(device.full_info_string())
    print()


def dump(device, args):
    device.extract_data(limit_to=["identity"])
    print("Preparing report for", device.name, "...")

    device.extract_data()
    filename = "".join([device.filename, "_REPORT"])
    with (Path(args.output) / filename).open(mode="w") as device_report:
        device_report.write(device.full_info_string())

    print("Report saved to", str((Path(args.output) / filename).resolve()))
    print()


def debug_dump(device, args):
    print("Before continuing, please remember that ALL dumped files may",
          "contain sensitive data. Use caution.")
    input("Press enter to continue")

    from helper.tests import dump_devices

    device.extract_data()
    dump_devices(device, args.output)


REGULAR_COMMANDS = {"traces":pull_traces, "t":pull_traces,
                    "record":record, "r":record,
                    "install":install, "i":install,
                    "extract-apk":extract_apk, "x":extract_apk,}

BATCH_COMMANDS = {"clean":clean, "c":clean,
                  "dump":dump, "d":dump,
                  "scan":scan_connected, "s":scan_connected,
                  "detailed-scan":detailed_scan, "ds":detailed_scan,
                  "debug-dump":debug_dump}


def main(args=None):
    """Parse and execute input commands."""
    args = PARSER.parse_args(args)

    if args == PARSER_NO_ARGS:
        PARSER.parse_args(["-h"])
        return False

    if args.command == "gui":
        from helper.GUI import helper_gui
        sys.exit(helper_gui.main())

    if hasattr(args, "output"):
        if not Path(args.output[0]).is_dir():
            print("ERROR: The provided path does not point to an existing directory!")
            return False

    if args.command not in BATCH_COMMANDS and args.command not in REGULAR_COMMANDS:
        raise NotImplementedError("The '{}' function is not yet implemented".format(args.command))

    using_batch_commands = args.command not in REGULAR_COMMANDS
    if not args.command in ("scan", "s"):
        print("Waiting for any device to come online...")
        device_.adb_command('wait-for-device')

    chosen_device = None
    connected_devices = device_.get_devices(initialize=False)

    try:
        if args.device:
            for device in connected_devices:
                if device.serial == args.device:
                    chosen_device = device

            if not chosen_device:
                print("Device with serial number", str(args.device),
                      "was not found by Helper!")
                return
    except AttributeError:
        # Target device cannot be specified in the used command, ignore
        pass

    if not using_batch_commands:
        if not chosen_device:
            if len(connected_devices) == 1:
                chosen_device = connected_devices[0]
            else:
                print("This command cannot be carried out with multiple devices",
                      "- please specify a serial number with '-d' or disconnect",
                      "unused devices.")
                return

        try:
            return REGULAR_COMMANDS[args.command](chosen_device, args)
        except device_.DeviceOfflineError:
            print("Device has been suddenly disconnected!")
            return False

    # TODO: figure out how to better enable process continuation in batch commands after disconnect error
    # preferably without checking for specific input here
    if args.command in ("scan", "s"):
        format_str = "{:13}{:15}{:10}{}"
        print(format_str.format("Serial", "Manufacturer", "Model", "Status"))

    if chosen_device:
        connected_devices = [chosen_device]

    for device in connected_devices:
        try:
            BATCH_COMMANDS[args.command](device, args)
        except device_.DeviceOfflineError:
            print("Device", device.name, "has been suddenly disconnected!")

    if args.command in ("scan", "detailed-scan", "s", "ds"):
        scan_other()

# TODO: add commands for setting various config values
