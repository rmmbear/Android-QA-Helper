import sys
from argparse import ArgumentParser, SUPPRESS
import helper as _helper


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
add items to the list.""".format(_helper.CLEANER_CONFIG)
PARSER_GROUP.add_argument("-c", "--clean", nargs="?", const=_helper.CLEANER_CONFIG,
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
PARSER_GROUP.add_argument("--bugreport", nargs="?", const=".", default=None,
                          dest="bugreport", help=SUPPRESS)


PARSER_NO_ARGS = PARSER.parse_args([])

def main():
    args = PARSER.parse_args()

    chosen_device = None

    if args == PARSER_NO_ARGS:
        # no arguments passed, display help
        PARSER.parse_args(["-h"])
        sys.exit()


    if args.version:
        print(_helper.VERSION_STRING)
        print(_helper.SOURCE_STRING)
        print()
        sys.exit()

    if args.bugreport:
        from helper.tests.test_pytest import dump_devices

        dump_devices(args.bugreport)
        sys.exit()


    import helper.main as _main

    if args.device:
        _main.get_devices()

        if not args.device in _main.get_devices():
            print("Device with serial number", args.device,
                  "was not found by Helper!")
            print("Check your usb connection and make sure",
                  "you're entering a valid serial number.\n")
            sys.exit()

        chosen_device = _main.DEVICES[args.device]
    elif not args.info:
        chosen_device = _main.pick_device()
        if not chosen_device:
            sys.exit()

    if args.install:
        _main.install(chosen_device, args.install)

    if args.pull_traces:
        destination = _main.pull_traces(chosen_device, args.pull_traces)
        if destination:
            print("Traces file was saved to:", destination, sep="\n")
        else:
            print("Unexpected error -- could not save traces to drive")

    if args.record:
        destination = _main.record(chosen_device, args.record)
        if destination:
            print("Recording was saved to:", destination, sep="\n")
        else:
            print("Unexpected error -- could not save recording to drive")

    if args.clean:
        device_list = []
        if chosen_device:
            device_list = [chosen_device]
        else:
            device_list.extend(_main.get_devices())

        for device in device_list:
            _main.clean(device, args.clean)

    if args.info:
        device_list = []
        if chosen_device:
            device_list = [chosen_device]
        else:
            device_list.extend(_main.get_devices())

        for device in device_list:
            device.print_full_info()
