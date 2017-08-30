""""""
import sys
from pathlib import Path
from argparse import ArgumentParser

import helper as helper_
import helper.main as main_
import helper.device as device_


HELPER_CLI_DESC = """{:.80}
""".format(helper_.VERSION_STRING)

PARSER = ArgumentParser(prog="helper", description=HELPER_CLI_DESC)
PARSER.add_argument("-v", "--version", action="version",
                    version=helper_.VERSION_STRING)
COMMANDS = PARSER.add_subparsers(title="Commands", dest="command", metavar="")

### Gneral-use optional arguments
HELP_DETAIL = """Specify command target by passing a device's serial number.
Device must be specified if you want to record, install or pull traces while
there are multiple devices connected to your PC."""
OPT_DEV = ArgumentParser("device", add_help=False)
OPT_DEV.add_argument("-d", "--device", default="", metavar="device",
                     help=HELP_DETAIL)

HELP_DETAIL = """Specify the output directory. If no directory is chosen, then
files are saved in the same directory helper was launched from."""
OPT_OUT = ArgumentParser("output", add_help=False)
OPT_OUT.add_argument("-o", "--output", default=".", metavar="directory",
                     help=HELP_DETAIL)

### Helper Commands definitions
HELP_GENERAL = """Install one or more apps on a device."""
HELP_DETAIL = """ Valid input for this commands is either: single .apk file,
.apk file with one or more .obb files, multiple .apk files. If another version
of installed app is already on device, it and all its data will be removed
before installing the new version."""
CMD = COMMANDS.add_parser("install", parents=[OPT_DEV, OPT_OUT], aliases=["i"],
                          help=HELP_GENERAL, epilog=HELP_DETAIL)
# TODO: Write help for install's 'file' argument
HELP_ARGUMENT = """"""
CMD.add_argument("install", nargs="+", metavar="files", help=HELP_ARGUMENT)

HELP_GENERAL = """Clean various files from a device. """
HELP_DETAIL = """By default, this command
removes only helper-created files, but further behavior can be customized with
cleaner config file. Currently available options are: removing files and
directories, clearing app data, uninstalling apps and replacing files on device
with local versions. For configuration example, see the config file itself: {}.
""".format(helper_.CLEANER_CONFIG)
CMD = COMMANDS.add_parser("clean", parents=[OPT_DEV, OPT_OUT], aliases="c",
                          help=HELP_GENERAL, epilog=HELP_DETAIL)
# TODO: Write help for cleaner's 'config' argument
HELP_ARGUMENT = """"""
CMD.add_argument("clean", nargs="?", default=helper_.CLEANER_CONFIG,
                 metavar="config", help=HELP_ARGUMENT)

HELP_GENERAL = """Record the screen of your device."""
HELP_DETAIL = """To stop and save the recorded video, press
'ctrl+c'. Videos have a hard time-limit of three minutes -- this is imposed by
the internal command and cannot be extended -- recording will be stopped
automatically after reaching that limit. NOTE: Sound is not, and cannot be
recorded."""
CMD = COMMANDS.add_parser("record", parents=[OPT_DEV, OPT_OUT], aliases="r",
                          help=HELP_GENERAL, epilog=HELP_DETAIL)

HELP_GENERAL = """Pull the dalvik vm stack traces (aka ANR log)."""
# TODO: Write detailed help for traces
HELP_DETAIL = """"""
CMD = COMMANDS.add_parser("traces", parents=[OPT_DEV, OPT_OUT], aliases="t",
                          help=HELP_GENERAL, epilog=HELP_DETAIL)

HELP_GENERAL = """Extract the .apk file of an installed application."""
# TODO: Write detailed help for extract-apk
HELP_DETAIL = """"""
CMD = COMMANDS.add_parser("extract-apk", parents=[OPT_DEV, OPT_OUT],
                          aliases="x", help=HELP_GENERAL, epilog=HELP_DETAIL)
# TODO: Write help for extract-apk's 'app-name' argument
HELP_ARGUMENT = """"""
CMD.add_argument("extract_apk", nargs="+", metavar="app name", help=HELP_ARGUMENT)


HELP_GENERAL = """Show status of all connected devices."""
# TODO: Write detailed help for scan
HELP_DETAIL = """"""
CMD = COMMANDS.add_parser("scan", aliases="s", help=HELP_GENERAL,
                          epilog=HELP_DETAIL)

HELP_GENERAL = """Show status and detailed information on connected devices."""
# TODO: Write detailed help for scan-detail
HELP_DETAIL = """"""
CMD = COMMANDS.add_parser("detailed-scan", parents=[OPT_DEV, OPT_OUT],
                          aliases=["ds"], help=HELP_GENERAL,
                          epilog=HELP_DETAIL)

HELP_GENERAL = """Dump all available device information to file."""
# TODO: Write detailed help for dump
HELP_DETAIL = """"""
CMD = COMMANDS.add_parser("dump", parents=[OPT_DEV, OPT_OUT], aliases="d",
                          help=HELP_GENERAL, epilog=HELP_DETAIL)

### Hidden commands
COMMANDS.add_parser("gui")
COMMANDS.add_parser("helper-dump")

# Example of caring too much about aesthetics
for group in  PARSER._action_groups:
    if group.title == 'optional arguments':
        group.title = None

PARSER_NO_ARGS = PARSER.parse_args([])


def pick_device(stdout_=sys.stdout):
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
        stdout_.write("Multiple devices detected!\n")
        stdout_.write(
            "Please choose which of devices below you want to work with.\n")
        for counter, device in enumerate(device_list):
            stdout_.write(" ".join([counter, ":"]))
            device.print_basic_info(stdout_)

        stdout_.write("Enter your choice: ")
        user_choice = input().strip()
        if not user_choice.isnumeric():
            stdout_.write("The answer must be a number!\n")
            continue

        user_choice = int(user_choice)
        if user_choice < 0  or user_choice >= len(device_list):
            stdout_.write("Answer must be one of the above numbers!\n")
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

    main_.install(device, *args.install)


def pull_traces(device, args):
    destination = main_.pull_traces(device, args.output)
    if destination:
        print("Traces file was saved to:")
        print(destination)
        return True

    return False


def clean(device, args):
    config_file = args.clean
    if not Path(config_file).is_file():
        print("Provided path does not point to an existing config file:")
        print(config_file)
        return False

    main_.clean(device, config_file)


def extract_apk(device, args):
    for app_name in args.extract_apk:
        out = device.extract_apk(app_name, args.output)
        if out:
            print("Package saved to", out)


def detailed_scan(device, args):
    device.device_init(limit_init=["getprop"])
    print("Preparing report for", device.info("Product", "Manufacturer"),
          device.info("Product", "Model"), "...")

    device.device_init()
    filename = "".join([device.info("Product", "Manufacturer"), "_",
                        device.info("Product", "Model"), "_", "REPORT"])
    with (Path(args.output) / filename).open(mode="w") as device_report:
        device_report.write(device.full_info_string())

    print("Report saved to", str((Path(args.output) / filename).resolve()))


def dump(device, args):
    pass


REGULAR_COMMANDS = {"pull-traces":pull_traces, "t":pull_traces,
                    "record":record, "r":record,
                    "install":install, "i":install,
                    "extract-apk":extract_apk, "x":extract_apk,}

BATCH_COMMANDS = {"clean":clean, "c":clean,
                  "detailed-scan":detailed_scan, "ds":detailed_scan}


def regular_commands(device, args):
    """Set of commands that should not be carried out on more than
    one device at a time.
    """
    try:
        REGULAR_COMMANDS[args.command](device, args)
    except KeyError:
        raise NotImplementedError("The '{}' function is not yet implemented".format(args.command))


def batch_commands(device_list, args):
    """Set of commands that can be run on multiple devices, one after
    another.
    """
    # TODO: work out how to run the below commands concurrently
    # this would be nice,  but I don't see a simple method of doing
    # it in a standard stdout/cli fashion
    # This will have to be implemented inside GUI module
    if args.command == "helper-dump":
        print("Before continuing, please remember that ALL dumped files may",
              "contain sensitive data. Please pay special attention to the",
              "'getprop' file which almost certainly will contain data you do",
              "not want people to see.")
        input("Press enter to continue")

    for device in device_list:
        try:
            BATCH_COMMANDS[args.command](device, args)
        except KeyError:
            raise NotImplementedError("The '{}' function is not yet implemented".format(args.command))


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

    # ^-functionality not requiring initialized devices
    # v-the opposite

    using_batch_commands = args.command not in REGULAR_COMMANDS
    if not args.command in ("scan", "s"):
        print("Waiting for any device to come online...")
        device_.adb_command('wait-for-device')

    chosen_device = None
    connected_devices = device_.get_devices(initialize=False)

    if args.command in ("scan", "s"):
        if connected_devices:
            format_str = "{:13}{:15}{:10}{}"
            print(format_str.format("Serial", "Manufacturer", "Model", "Status"))
            for device in connected_devices:
                device.device_init(limit_init=("getprop"))
                print(format_str.format(
                    device.serial, device.info("Product", "Manufacturer"),
                    device.info("Product", "Model"), device._status))
            print()

        unauthorized_devices = device_._get_devices()
        for device in unauthorized_devices:
            if device[1] == "device":
                unauthorized_devices.remove(device)

        if unauthorized_devices:
            print("The following devices could not be initialized:")
            for serial, status in unauthorized_devices:
                print(serial, ":", status)
            print()
        return

    try:
        if args.device:
            for device in connected_devices:
                if device.serial == args.device:
                    chosen_device = [device]

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

        return regular_commands(chosen_device, args)

    return batch_commands(connected_devices, args)
