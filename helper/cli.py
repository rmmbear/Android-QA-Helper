"""Command line interface module"""
import sys
import logging
from pathlib import Path
from argparse import ArgumentParser

import helper
import helper.main
import helper.device

LOGGER = logging.getLogger(__name__)

PARSER = ArgumentParser(
    prog="helper", description="CLI utility for interfacing with Android devices",
    epilog="""You can pass the '-h' argument to all of the above commands for detailed description.
    Feel free to check out the source code and report any issues at github.com/rmmbear/Android-QA-Helper"""
)
PARSER.add_argument(
    "-v", "--version", action="version", version="%(prog)s {}".format(helper.VERSION))

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
    help="Install an app on connected device.",
    epilog="""If another version of the app is already on the device, helper
    will attempt to remove it and all its data first before replacing it.
    Note that system apps can only be replaced with newer versions and the
    '--replace-system-apps' argument must be used.""")

CMD.add_argument(
    "install", metavar="APK",
    help=".apk file.")

CMD.add_argument(
    "--obb", nargs="+", metavar="OBB",
    help="Keep data and cache directories when replacing apps.")

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
    {helper.CLEANER_CONFIG}.""")

CMD.add_argument(
    "clean", nargs="?", default=helper.CLEANER_CONFIG, metavar="config",
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
    "extract", parents=[OPT_DEVICE, OPT_OUTPUT], aliases="x",
    help="""Extract .apk file of an installed application.""",
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
    "command_", nargs="*", metavar="command",
    help="""Note: put "--" as the first argument to suppress argument parsing
    (necessary if your shell command contains dashes).""")

CMD = COMMANDS.add_parser(
    "adb", parents=[OPT_DEVICE],
    help="Issue an adb command for a device.",
    epilog="Issue an adb command for a device.")

CMD .add_argument(
    "command_", nargs="*", metavar="command",
    help="""Note: put "--" as the first argument to suppress argument parsing
    (necessary if your shell command contains dashes).""")


### Hidden commands
CMD = COMMANDS.add_parser("debug-dump", parents=[OPT_DEVICE, OPT_OUTPUT])
CMD.add_argument("--full", action="store_true")
COMMANDS.add_parser("run-tests")

del CMD
PARSER_NO_ARGS = PARSER.parse_args([])


def find_adb_and_aapt(require_adb=True, require_aapt=True):
    """Find and set paths of the necessary tools.
    Invokes helper.tools.tool_grabber if tools are not found.
    This function modifies global state - it sets paths of ADB and AAPT,
    as well as their _VERSION variables, in package's __init__'s scope .
    """
    if not require_adb and not require_aapt:
        return

    tools = ("ADB", "AAPT")
    missing = []
    required = {"ADB":require_adb, "AAPT":require_aapt}

    for tool_name in tools:
        tool_path = getattr(helper, tool_name)
        # only care about the executable if it's required
        if required[tool_name] and not tool_path:
            missing.append(tool_name)

    if missing:
        print(f"Tools missing: {missing}")
        print("Helper cannot run without above tools - would you like to download them now?")
        try:
            userinput = input("Y/N ")
        except EOFError:
            print("Aborting...")
            sys.exit()

        if userinput[0] not in "yY":
            LOGGER.info("early exit - user did not allow download of missing tools")
            sys.exit()

        if len(missing) == 2:
            tool = "all"
        else:
            tool = missing[0].lower()
        # download the missing tool(s) using helper.tools.tool_grabber
        from .tools import tool_grabber
        tool_grabber.main(arguments=f"--tool {tool}".split())

        for tool in missing:
            out = helper.find_executable(tool.lower())
            setattr(helper, tool, out[0])
            setattr(helper, f"{tool}_VERSION", out[1])

        # it is possible that tool_grabber fails to download all tools
        # this could be because of user-side errors
        # (faulty internet connection, for example)
        # so we need to make sure they have really been found
        found_all = True
        for tool in missing:
            if not getattr(helper, tool):
                found_all = False

        if not found_all:
            LOGGER.error("Could not find downloaded tools, aborting")
            sys.exit()


def pick_device():
    """Ask the user to pick a device from list of currently connected
    devices. If only one is available, it will be chosen automatically.
    None is returned if there aren't any devices.
    """
    device_list = helper.device.get_devices(limit_init=["identity"])
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
    destination = helper.main.record(device, args.output)
    if destination:
        print("Recorded video was saved to:")
        print(destination)
        return destination

    return False


def install(device, args):
    if not Path(args.install).is_file():
        print("ERROR: Provided path does not point to an existing file:")
        print(args.install)
        return
    helper.main.install(
        device, args.install, args.obb, install_location=args.location,
        keep_data=args.keep_data, installer_name=args.installer_name)


def pull_traces(device, args):
    """"""
    destination = helper.main.pull_traces(device, args.output)
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

    helper.main.clean(device, config_file)


def scan(args):
    """"""
    device_list = helper.device.get_devices(True, ["identity"], True)
    if not device_list:
        print()
        print("No devices detected")
        return

    # Load everything into lines, including the headers
    lengths = [2, 10, 12, 5, 6]
    lines = [("#", "Serial #", "Manufacturer", "Model", "Status")]
    for count, device in enumerate(device_list):
        count = str(count + 1)
        serial = device.serial
        manufacturer = device.info_dict["device_manufacturer"]
        manufacturer = manufacturer if manufacturer else "Unknown"
        model = device.info_dict["device_manufacturer"]
        model = model if model else "Unknown"
        status = device._status
        for x, item in enumerate((count, serial, manufacturer, model, status)):
            lengths[x] = max(len(item), lengths[x])

        lines.append((count, serial, manufacturer, model, status))

    # create format string dynamically
    # each column has a width of its widest element + 2
    format_str = "{:" + "}{:".join([str(x+2) for x in lengths]) + "}"
    for line in lines:
        print(format_str.format(*line))


def info_dump(device, args):
    """"""
    device.extract_data(limit_to=["identity"])
    print(f"Collecting info from {device.name} ...")

    filename = f"{device.filename}_REPORT"
    output_path = (Path(args.output) / filename).resolve()
    with output_path.open(mode="w") as device_report:
        device.info_dump(device_report)

    print(f"Report saved to {str(output_path)}")


def debug_dump(device, args):
    """Dump device data to files.
    What is dumped is controlled by extract_data's INFO_SOURCES.
    This data is meant to be loaded into DummyDevice for debugging and
    compatibility tests.
    """
    print("Please remember that dumped files may contain sensitive data. Use caution.")
    directory = Path(args.output)
    directory.mkdir(exist_ok=True)

    # this is very silly
    # make _init_cache getter retrieve the value from immortal_cache
    # while its setter simply does nothing, which prevents device.get_data from
    # "deleting" the cache (it does so by assigning an empty dict to _init_cache)
    # because doing it this way modifies the class definition at runtime and prevents
    # updating device information (except for methods which skip cache checks
    # explicitly), helper should exit immediately after data is dumped
    # The only reason I'm going with this is because I don't want to mess with
    # device module right now
    device.immortal_cache = {}
    helper.device.Device._init_cache = property(
        lambda self: self.immortal_cache,
        lambda self, value: None
    )
    print("-----")
    print("\nDumping", device.name)
    device_dir = Path(directory, (device.filename + "_DUMP"))
    device_dir.mkdir(exist_ok=True)

    from helper.extract_data import INFO_SOURCES
    for source_name, command in INFO_SOURCES.items():
        if source_name.startswith("debug") and not args.full:
            continue

        if source_name in device.immortal_cache:
            output = device.immortal_cache[source_name]
        else:
            output = device.shell_command(*command, return_output=True, as_list=False)

        with Path(device_dir, source_name).open(mode="w", encoding="utf-8") as dump_file:
            dump_file.write(output)

        print(".", end="", flush=True)

    print("\nDumping device's info_dict")
    print("\nLoading data")
    try:
        device.extract_data()
    except:
        print("ERROR: Encountered an exception during load, dumping as-is")
    with Path(device_dir, "device_info_dict").open(mode="w", encoding="utf-8") as info_dict_file:
        for key, value in device.info_dict.items():
            info_dict_file.write(f"{key}: {str(value)}\n")

    print("Device dumped to", str(device_dir))


def run_tests(args):
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
    helper.device.adb_command(*args.command_, return_output=False, check_server=False)


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
    "dump":(info_dump, 2), "d":(info_dump, 2),
}


def main(args=None):
    """Parse and execute input commands."""
    find_adb_and_aapt()
    LOGGER.info("Starting parsing arguments")
    args = PARSER.parse_args(args)

    LOGGER.info("Starting helper with option %s", args.command)

    if args == PARSER_NO_ARGS:
        PARSER.parse_args(["-h"])
        return

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
    #FIXME: do not initialize other devices when performing actions on specific device

    #TODO: Implement a timeout
    print("Waiting for any device to come online...")
    helper.device.adb_command('wait-for-device', return_output=True)

    connected_devices = helper.device.get_devices(initialize=False)
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
        except helper.device.DeviceOfflineError:
            print("Device has been suddenly disconnected!")

    if required_devices == 2:
        if chosen_device:
            connected_devices = [chosen_device]
        for device in connected_devices:
            try:
                command(device, args)
            except helper.device.DeviceOfflineError:
                print(f"Device {device.name} has been suddenly disconnected!")

#TODO: Implement screenshot command
#TODO: Implement keyboard and keyboard-interactive
#      Enter text into textfields on Android device using PC's keyboard
