""""""
import sys
from pathlib import Path
from argparse import ArgumentParser, SUPPRESS

import helper as helper_
import helper.main as main_
import helper.device as device_


PARSER = ArgumentParser(prog="helper", usage="%(prog)s [-d <serial>] [options]")


PARSER_GROUP = PARSER.add_mutually_exclusive_group()

HELP_STR = """Install an application or set of applications on a device.
Valid input for this commands is either: single .apk file, .apk file with one
or more .obb files, multiple .apk files. If another version of installed app is
already on device, it and all its data will be removed before installing the
new version."""
PARSER_GROUP.add_argument("-i", "--install", nargs="+", dest="install",
                          help=HELP_STR, metavar="file")

HELP_STR = """Record the screen of your device. Optionally, output path can be
passed alongside this command, by default all videos are saved to the same
directory that helper is in. To stop and save the recorded video, press
'ctrl+c'. Videos have a hard time-limit of three minutes -- this is imposed by
the internal command and cannot be extended -- recording will be stopped
automatically after reaching that limit. NOTE: Sound is not, and cannot be
recorded."""
PARSER_GROUP.add_argument("-r", "--record", action="store_true",
                          dest="record", help=HELP_STR)

HELP_STR = """Pull the dalvik vm stack traces / anr log file to specified
location. If a location is not specified, the file will be saved to helper's
directory."""
PARSER_GROUP.add_argument("-t", "--pull-traces", action="store_true",
                          dest="pull_traces", help=HELP_STR)

HELP_STR = """Extract the .apk file of an application installed on device."""
PARSER_GROUP.add_argument("-e", "--extract-apk", nargs="+", dest="extract_apk",
                          help=HELP_STR, metavar="app.name")

HELP_STR = """Clean various files from a device. By default, this command
removes only helper-created files, but further behavior can be customized with
cleaner config file. Currently available options are: removing files and
directories, clearing app data, uninstalling apps and replacing files on device
with local versions. For configuration example, see the config file itself: {}.
""".format(helper_.CLEANER_CONFIG)
PARSER_GROUP.add_argument("-c", "--clean", nargs="?", const=helper_.CLEANER_CONFIG,
                          default=None, dest="clean", help=HELP_STR,
                          metavar="config")

HELP_STR = """Show available info about connected devices."""
PARSER_GROUP.add_argument("-n", "--info", action="store_true", dest="info",
                          help=HELP_STR)
HELP_STR = "Show program's version and contact info."
PARSER_GROUP.add_argument("-v", "--version", action="store_true",
                          dest="version", help=HELP_STR)
# Hidden options
PARSER_GROUP.add_argument("--gui", action="store_true", dest="gui",
                          help=SUPPRESS)
PARSER_GROUP.add_argument("--device-dump", action="store_true",
                          dest="device_dump", help=SUPPRESS)

HELP_STR = """Use with other commands to specify command target. To select a
device, simply pass its serial number as a value to this command. To get
serial numbers of connected devices, use the '--info' command. Device must be
specified if you want to record, install or pull traces while there are
multiple devices connected to your PC."""
PARSER.add_argument("-d", "--device-serial", nargs=1, dest="device",
                    help=HELP_STR, metavar="serial_no")

HELP_STR = """Specify the output directory for other commands. If no directory
is chosen, then files created by other commands are saved in the same directory
helper was launched from."""
PARSER.add_argument("-o", "--output-dir", nargs=1,
                    dest="output_dir", help=HELP_STR, metavar="directory")


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


def record(device, output):
    if not Path(output).is_dir():
        print("Provided path does not point to an existing directory!")
        print(output)
        return False

    device.device_init(limit_init=('getprop', 'shell_environment', 'available_commands'))
    destination = main_.record(device, output)
    if destination:
        print("Recorded video was saved to:", destination, sep="\n")
        return destination

    return False


def install(device, apk_list):
    for filepath in apk_list:
        if not Path(filepath).is_file():
            print("ERROR: Provided path does not point to an existing file:")
            print(filepath)
            return False

    device.device_init(limit_init=('getprop', 'shell_environment', 'available_commands'))
    main_.install(device, *apk_list)


def pull_traces(device, output):
    if not Path(output).is_dir():
        print("Provided path does not point to an existing directory!")
        print(output)
        return False

    device.device_init(limit_init=('getprop', 'shell_environment'))
    destination = main_.pull_traces(device, output)
    if destination:
        print("Traces file was saved to:")
        print(destination)
        return True

    return False


def clean(device, config_file):
    if not Path(config_file).is_file():
        print("Provided path does not point to an existing config file:")
        print(config_file)
        return False

    device.device_init(limit_init=('installed_apps', 'shell_environment'))
    main_.clean(device, config_file)


def regular_commands(device, args, output_dir="."):
    """Set of commands that should not be carried out on more than
    one device at a time.
    """
    if args.pull_traces:
        return pull_traces(device, output_dir)

    if args.extract_apk:
        device.device_init(limit_init=('getprop', 'installed_apps'))
        for app_name in args.extract_apk:
            device.extract_apk(app_name, output_dir)

    if args.record:
        return record(device, output_dir)

    # install was initially in the batch commands function
    # but since they are not set up for concurrent execution, it doesn't
    # really make sense to put a function that takes minutes to finish
    #
    # to achieve concurrent installation on multiple devices, an external
    # script could be used

    if args.install:
        return install(device, args.install)


def batch_commands(device_list, args, output_dir="."):
    """Set of commands that can be run on multiple devices, one after
    another.
    """
    # TODO: work out how to run the below commands concurrently
    # this would be nice,  but I don't see a simple method of doing
    # it in a standard stdout/cli fashion
    # This will have to be implemented inside GUI module
    if args.device_dump:
        print("Before continuing, please remember that ALL dumped files may",
              "contain sensitive data. Please pay special attention to the",
              "'getprop' file which almost certainly will contain data you do",
              "not want people to see.")
        input("Press enter to continue")

    for device in device_list:
        if args.info:
            device.device_init()
            device.print_full_info()

        if args.clean:
            return clean(device, args.clean)

        if args.device_dump:
            device.device_init()
            from helper.tests import dump_devices
            dump_devices(device, output_dir)


def main(args=None):
    """Parse and execute input commands."""
    args = PARSER.parse_args(args)

    if args == PARSER_NO_ARGS:
        PARSER.parse_args(["-h"])
        return False

    if args.version:
        print(helper_.VERSION_STRING)
        print(helper_.SOURCE_STRING)
        return

    if args.gui:
        from helper.GUI import helper_gui
        helper_gui.main()
        return

    if args.output_dir:
        if not Path(args.output_dir[0]).is_dir():
            print("ERROR: The provided path does not point to an existing directory!")
            return False
        output_dir = args.output_dir[0]
    else:
        output_dir = "."


    # ^-functionality not requiring initialized devices
    # v-the opposite

    using_batch_commands = not (bool(args.pull_traces) or \
                           bool(args.record) or \
                           bool(args.install) or \
                           bool(args.extract_apk))

    if not device_._get_devices():
        print("No devices found!")
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
        print("This command cannot be carried out with multiple devices",
              "- please specify a serial number with '-d' or disconnect",
              "unused devices.")
        return

    if using_batch_commands:
        return batch_commands(connected_devices, args, output_dir)

    return regular_commands(chosen_device, args, output_dir)
