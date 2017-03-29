import sys
from pathlib import Path
from argparse import ArgumentParser, SUPPRESS

import helper as helper_
import helper.main as main_


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
PARSER_GROUP.add_argument("--bugreport", nargs="?", const=".", default=None,
                          dest="bugreport", help=SUPPRESS)


PARSER_NO_ARGS = PARSER.parse_args([])


def main(args=None):
    if args is None:
        args = PARSER.parse_args()
    else:
        args = PARSER.parse_args(args)
    chosen_device = None

    if args == PARSER_NO_ARGS:
        # no arguments passed, display help
        PARSER.parse_args(["-h"])
        return

    if args.version:
        print(helper_.VERSION_STRING)
        print(helper_.SOURCE_STRING)
        return

    if args.bugreport:
        from helper.tests import dump_devices
        dump_devices(args.bugreport)
        return

    if args.gui:
        from helper.GUI import helper_gui
        helper_gui.main()

    if args.device:
        main_.get_devices()
        if not args.device[0].strip() in main_.DEVICES:
            print("Device with serial number", args.device[0].strip(),
                  "was not found by Helper!")
            return
        chosen_device = main_.DEVICES[args.device[0].strip()]
    #
    elif not args.info or not args.clean:
        chosen_device = main_.pick_device()
        if not chosen_device:
            return

    if args.install:
        for filepath in args.install:
            if not Path(filepath).is_file():
                print("Provided path does not point to an existing file:",
                      str(Path(filepath).resolve()), sep="\n")
                return
        main_.install(chosen_device, *args.install)

    if args.clean:
        if not Path(args.clean).is_file():
            print("Provided path does not point to an existing config file:",
                  str(Path(args.clean).resolve()), sep="\n")
            return
        device_list = []
        if chosen_device:
            device_list = [chosen_device]
        else:
            device_list.extend(main_.get_devices())

        for device in device_list:
            main_.clean(device, args.clean)

    if args.pull_traces:
        if not Path(args.pull_traces).is_dir():
            print("Provided path does not point to an existing directory!\n",
                  str(Path(args.pull_traces).resolve()), sep="")
            return
        destination = main_.pull_traces(chosen_device, args.pull_traces)
        if destination:
            print("Traces file was saved to:", destination, sep="\n")

    if args.record:
        if not Path(args.record).is_dir():
            print("Provided path does not point to an existing directory!\n",
                  str(Path(args.record).resolve()), sep="")
            return
        destination = main_.record(chosen_device, args.record)
        if destination:
            print("Recorded clip was saved to:", destination, sep="\n")

    if args.info:
        device_list = []
        if chosen_device:
            device_list = [chosen_device]
        else:
            device_list.extend(main_.get_devices())

        for device in device_list:
            device.print_full_info()
