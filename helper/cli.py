""""""
import sys
from pathlib import Path
from argparse import ArgumentParser, SUPPRESS

import helper as helper_
import helper.main as main_
import helper.device as device_




OPTIONS = ArgumentParser("options", add_help=False)
HELP_DETAIL = """Specify command target by passing a device's serial number.
Device must be specified if you want to record, install or pull traces while
there are multiple devices connected to your PC."""
OPTIONS.add_argument("-d", "--device", default="", help=HELP_DETAIL, metavar="device")

HELP_DETAIL = """Specify the output directory. If no directory is chosen, then
files are saved in the same directory helper was launched from."""
OPTIONS.add_argument("-o", "--output", default=".", help=HELP_DETAIL, metavar="directory")


HELPER_CLI_DESC = """{:.80}
""".format(helper_.VERSION_STRING)

PARSER = ArgumentParser(prog="helper", description=HELPER_CLI_DESC, parents=[OPTIONS])

COMMANDS = PARSER.add_subparsers(title="Commands", dest="command", metavar="")


HELP_GENERAL = """Install one or more apps on a device."""
HELP_DETAIL = """ Valid input for this commands is either: single .apk file,
.apk file with one or more .obb files, multiple .apk files. If another version
of installed app is already on device, it and all its data will be removed
before installing the new version."""
COMMANDS.add_parser("install", help=HELP_GENERAL, parents=[OPTIONS]).add_argument(
    "install", nargs="+", help=HELP_DETAIL, metavar="file")

HELP_GENERAL = """Record the screen of your device."""
HELP_DETAIL = """To stop and save the recorded video, press
'ctrl+c'. Videos have a hard time-limit of three minutes -- this is imposed by
the internal command and cannot be extended -- recording will be stopped
automatically after reaching that limit. NOTE: Sound is not, and cannot be
recorded."""
COMMANDS.add_parser("record", help=HELP_GENERAL, parents=[OPTIONS]).add_argument(
    "record", action="store_true", help=HELP_DETAIL)

HELP_GENERAL = """Pull the dalvik vm stack traces (aka ANR log)."""
HELP_DETAIL = """"""
COMMANDS.add_parser("traces", help=HELP_GENERAL, parents=[OPTIONS]).add_argument(
    "pull-traces", action="store_true", help=HELP_DETAIL)

HELP_GENERAL = """Extract the .apk file of an application installed on device."""
HELP_DETAIL = """"""
COMMANDS.add_parser("extract-apk", help=HELP_GENERAL, parents=[OPTIONS]).add_argument(
    "extract-apk", nargs="+", help=HELP_DETAIL, metavar="app.name")

HELP_GENERAL = """Clean various files from a device."""
HELP_DETAIL = """By default, this command
removes only helper-created files, but further behavior can be customized with
cleaner config file. Currently available options are: removing files and
directories, clearing app data, uninstalling apps and replacing files on device
with local versions. For configuration example, see the config file itself: {}.
""".format(helper_.CLEANER_CONFIG)
COMMANDS.add_parser("clean", help=HELP_GENERAL, parents=[OPTIONS]).add_argument(
    "clean", nargs="?", const=helper_.CLEANER_CONFIG, default=None,
    help=HELP_DETAIL, metavar="config")

HELP_GENERAL = """Show status of all connected devices."""
HELP_DETAIL = """"""
COMMANDS.add_parser("scan", help=HELP_GENERAL).add_argument(
    "scan", action="store_true", help=HELP_DETAIL)

HELP_GENERAL = """Show status and detailed information on connected devices."""
HELP_DETAIL = """"""
COMMANDS.add_parser("scan-detail", help=HELP_GENERAL, parents=[OPTIONS]
    ).add_argument("scan-detail", action="store_true", help=HELP_DETAIL)

HELP_GENERAL = """Dump all available information to file for all connected devices."""
HELP_DETAIL = """"""
COMMANDS.add_parser("dump", help=HELP_GENERAL, parents=[OPTIONS]).add_argument(
    "dump", action="store_true", help=HELP_DETAIL)

PARSER.add_argument("-v", "--version", action="version", version=helper_.VERSION_STRING)

# Hidden options
COMMANDS.add_parser("gui", help=SUPPRESS).add_argument("gui", action="store_true", help=SUPPRESS)
COMMANDS.add_parser("helper-dump", parents=[OPTIONS], help=SUPPRESS).add_argument("helper-dump", action="store_true", help=SUPPRESS)

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
    device.device_init(limit_init=('getprop', 'shell_environment', 'available_commands'))
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

    device.device_init(limit_init=('getprop', 'shell_environment', 'available_commands'))
    main_.install(device, *args.install)


def pull_traces(device, args):
    device.device_init(limit_init=('getprop', 'shell_environment'))
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

    device.device_init(limit_init=('installed_apps', 'shell_environment'))
    main_.clean(device, config_file)

def extract_apk():
    pass

def scan():
    pass

def info():
    pass

def detailed_info():
    pass

REGULAR_COMMANDS = {"pull-traces":pull_traces,
                    "record":record,
                    "install":install}

BATCH_COMMANDS = {"clean":clean}

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
    if args.command == "device-dump":
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

    print([args])
    print([args.command])

    if args == PARSER_NO_ARGS:
        PARSER.parse_args(["-h"])
        return False

    if hasattr(args, "gui"):
        from helper.GUI import helper_gui
        helper_gui.main()
        return

    if hasattr(args, "output"):

        if not Path(args.output[0]).is_dir():
            print("ERROR: The provided path does not point to an existing directory!")
            return False


    # ^-functionality not requiring initialized devices
    # v-the opposite

    using_batch_commands = args.command not in ("pull-traces", "record", "install", "extract-apk")


    print("Waiting for any device to come online...")
    device_.adb_command('wait-for-device')

    chosen_device = None
    connected_devices = device_.get_devices(initialize=False)
    for device in connected_devices:
        print("".join(["Device with serial id '", device.serial,
                       "' connected\n"]))

    if args.device:
        desired_device = args.device[0]
        for device in connected_devices:
            if device.serial == desired_device:
                chosen_device = [device]

        if not chosen_device:
            print("Device with serial number", desired_device,
                  "was not found by Helper!")
            return

    if not chosen_device and len(connected_devices) == 1:
        chosen_device = connected_devices[0]

    if not chosen_device and not using_batch_commands:
        print(device_._get_devices())
        print("This command cannot be carried out with multiple devices",
              "- please specify a serial number with '-d' or disconnect",
              "unused devices.")
        return

    if using_batch_commands:
        return batch_commands(connected_devices, args)

    return regular_commands(chosen_device, args)
