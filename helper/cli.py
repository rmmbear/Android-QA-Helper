""""""
from pathlib import Path
from argparse import ArgumentParser, SUPPRESS

import helper as helper_
import helper.main as main_
import helper.device as device_


PARSER = ArgumentParser(prog="helper", usage="%(prog)s [-d <serial>] [options]")
HELP_STR = """Specify a device you want to work with. Must be used alongside
other options to be effective. This argument is optional and if not specified,
helper will let you choose from the list of currently connected devices."""
PARSER.add_argument("-d", "--device", nargs=1, dest="device", help=HELP_STR,
                    metavar="serial_no")
PARSER_GROUP = PARSER.add_mutually_exclusive_group()
HELP_STR = """Install an app. Can install a single apk, single apk and
accompanying obb file (multiple obb files are accepted, but there can be only
one apk present when pushing obb files), or series of apks."""
PARSER_GROUP.add_argument("-i", "--install", nargs="+", dest="install",
                          help=HELP_STR, metavar="file")
HELP_STR = """Record the screen of your device. Helper will ask you for
confirmation before starting the recording. Once the recording has started, it
will stop on its own after the time limit has elapsed (3 minutes), or if you
press 'ctrl+c'. After the recording has been stopped, helper will copy the file
to specified location. If a location was not specified, the file will be copied
to wherever helper is located. NOTE: Sound is not, and cannot be recorded."""
PARSER_GROUP.add_argument("-r", "--record", nargs="?", const=".", default=None,
                          dest="record", help=HELP_STR, metavar="destination")
HELP_STR = """Pull the dalvik vm stack traces / anr log file to specified
location. If a location is not specified, the file will be copied to wherever
helper was called from."""
PARSER_GROUP.add_argument("-t", "--pull_traces", nargs="?", const=".",
                          default=None, dest="pull_traces", help=HELP_STR,
                          metavar="destination")
HELP_STR = """Clean your device using instructions in cleaner_config file. You
can tell helper to delete files or directories, uninstall apps and replace files
on device with ones from your drive. See the contents of '{}' for info on how to
add items to the list.""".format(helper_.CLEANER_CONFIG)
PARSER_GROUP.add_argument("-c", "--clean", nargs="?", const=helper_.CLEANER_CONFIG,
                          default=None, dest="clean", help=HELP_STR,
                          metavar="config")
HELP_STR = """Show info for all connected devices. If --device was specified,
information only for that device will be shown."""
PARSER_GROUP.add_argument("-n", "--info", action="store_true", dest="info",
                          help=HELP_STR)
HELP_STR = "Show version information."
PARSER_GROUP.add_argument("-v", "--version", action="store_true",
                          dest="version", help=HELP_STR)
# Hidden options
PARSER_GROUP.add_argument("--gui", action="store_true", dest="gui",
                          help=SUPPRESS)
PARSER_GROUP.add_argument("--device_dump", nargs="?", const=".", default=None,
                          dest="device_dump", help=SUPPRESS)


PARSER_NO_ARGS = PARSER.parse_args([])

def regular_commands(device, args):
    device.device_init()
    if args.pull_traces:
        if not Path(args.pull_traces).is_dir():
            print("Provided path does not point to an existing directory!\n",
                  str(Path(args.pull_traces).resolve()), sep="")
            return
        destination = main_.pull_traces(device, args.pull_traces)
        if destination:
            print("Traces file was saved to:", destination, sep="\n")

    if args.record:
        if not Path(args.record).is_dir():
            print("Provided path does not point to an existing directory!\n",
                  str(Path(args.record).resolve()), sep="")
            return
        destination = main_.record(device, args.record)
        if destination:
            print("Recorded video was saved to:", destination, sep="\n")


def batch_commands(device_list, args):
    for device in device_list:
        if args.install:
            for filepath in args.install:
                if not Path(filepath).is_file():
                    print("Provided path does not point to an existing file:")
                    print(str(Path(filepath).resolve()))
                    return

            device.device_init()
            main_.install(device, *args.install)

        if args.info:
            device.limit_init = ()
            device.device_init()
            device.print_full_info()

        if args.clean:
            if not Path(args.clean).is_file():
                print("Provided path does not point to an existing config file:",
                      str(Path(args.clean).resolve()), sep="\n")
                return
            device.device_init()
            main_.clean(device, args.clean)


def main(args=None):
    args = PARSER.parse_args(args)

    if args == PARSER_NO_ARGS:
        PARSER.parse_args(["-h"])
        return

    if args.version:
        print(helper_.VERSION_STRING)
        print(helper_.SOURCE_STRING)
        return

    if args.device_dump:
        from helper.tests import dump_devices
        dump_devices(args.dump_devices)
        return

    if args.gui:
        from helper.GUI import helper_gui
        helper_gui.main()
        return

    # ^-functionality not requiring initialized devices
    # v-the opposite

    using_batch_commands = not (bool(args.pull_traces) or bool(args.record))

    if not device_._get_devices():
        print("No devices found!")
        print("Waiting for any device to come online...")
        device_.adb_command('wait-for-device')

    chosen_device = None
    connected_devices = device_.get_devices(initialize=False,
        limit_init=('getprop', 'shell_environment', 'available_commands'))

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
        batch_commands(connected_devices, args)
    else:
        regular_commands(chosen_device, args)
