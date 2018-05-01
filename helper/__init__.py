#   Android QA Helper - helping you test Android apps!
#   Copyright (C) 2017-2018 rmmbear
#
#   This program is free software: you can redistribute it and/or modify
#   it under the terms of the GNU General Public License as published by
#   the Free Software Foundation, either version 3 of the License, or
#   (at your option) any later version.
#
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.
#
#   You should have received a copy of the GNU General Public License
#   along with this program. If not, see <http://www.gnu.org/licenses/>.

import os
import sys
import shutil
import inspect
import logging
import subprocess
from pathlib import Path

logging.basicConfig(level=logging.WARNING)

LOGGER = logging.getLogger(__name__)

# Program metadata
VERSION = "0.14"
VERSION_DATE = "2018-05-01"
VERSION_STRING = "".join(["Android Helper v", VERSION, " : ", VERSION_DATE])
COPYRIGHT_STRING = "Copyright (c) 2017-2018 rmmbear"
SOURCE_STRING = "Check the source code at https://github.com/rmmbear/Android-QA-Helper"

# Global config variables
ABI_TO_ARCH = {
    "armeabi"    :"32bit (ARM)",
    "armeabi-v7a":"32bit (ARM)",
    "arm64-v8a"  :"64bit (ARM64)",
    "x86"        :"32bit (Intel x86)",
    "x86_64"     :"64bit (Intel x86_64)",
    "mips"       :"32bit (Mips)",
    "mips64"     :"64bit (Mips64)",
}
ADB_VERSION = "Unknown"
AAPT_VERSION = "Unknown"
AAPT_AVAILABLE = False
EDITED_CONFIG = False
HELPER_CONFIG_VARS = ["ADB", "AAPT"]
DEFAULT_CLEANER_CONFIG = """# lines starting with '#' will be ignored
#
# categories:
# 'remove'          - Specify a file or directory to be removed. Dirs
#                     cannot be removed. Accepts wildcards (*).
# 'remove_recursive'- Specify a directory for deletion. Directory and
#                     ALL its contents -- including sub-directories --
#                     will be removed.
# 'clear_data'      - Clear application data of the specified package.
#                     Package can be specified by name or .apk file.
# 'uninstall'       - Remove an app, by specifying its name or path to
#                     local apk file. Some apps cannot be removed.
# 'replace'         - Replace specified remote file with a local file.
#                     If the remote file does not exist, the local will
#                     still be placed in the remote path. Must provide
#                     two -- no more, no less -- semicolon delimited
#                     files.
#
#
# Example usage:
# remove : /mnt/sdcard/Screenshots/*   - Remove all Screenshots
#
# remove_recursive : /mnt/sdcard/DCIM  - Remove the whole DCIM directory
#
# uninstall : com.android.browser      - Remove a package by its name
# uninstall : /home/user/some.apk      - Remove a package by its apk
#
# clear_data : com.android.browser     - Clear application data (name)
# clear_data : /home/user/some.apk     - Clear application data (local
#                                                                  file)
#
#                                | semicolon as delimiter
#                                v
# replace : /mnt/sdcard/somefile ; /home/user/Desktop/someotherfile
#            ^                      ^
#            | remote file          | local file
#

# remove files left by helper
remove : /mnt/sdcard/*_screenrecord_*.mp4
remove : /mnt/sdcard/*_anr_*.txt
remove : /data/local/tmp/helper_*
"""

def _get_script_dir():
    """"""
    if getattr(sys, 'frozen', False):
        path = os.path.abspath(sys.executable)
    else:
        path = inspect.getabsfile(_get_script_dir)

    path = os.path.realpath(path)
    return os.path.dirname(path)

BASE = _get_script_dir()
ADB = BASE + "/../adb/adb"
AAPT = BASE + "/../aapt/aapt"
CONFIG = BASE + "/../helper_config"
CLEANER_CONFIG = BASE + "/../cleaner_config"
#COMPRESSION_DEFINITIONS = BASE + "/../compression_identifiers"

if sys.platform == "win32":
    AAPT += ".exe"
    ADB += ".exe"


def exe(executable, *args, return_output=False, as_list=True,
        stdout_=sys.stdout):
    """Run the provided executable with specified commands"""
    LOGGER.debug("Executing {}".format([executable, *args]))
    try:
        if return_output:
            cmd_out = subprocess.run((executable,) + args,
                                     stdout=subprocess.PIPE,
                                     stderr=subprocess.STDOUT).stdout

            cmd_out = cmd_out.decode("utf-8", "replace")
            # TODO: there is an issue with line endings in adb output
            # on Linux each line is ended with '\r\n'
            # on Windows this becomes '\r\r\n'
            # the easy thing is to just search for double carriage return and
            # replace it, which means that every adb command would gain some
            # overhead. This could, although unlikely, result in mangled output
            # soo... figure out what to do here
            if sys.platform == "win32" and executable == ADB:
                cmd_out = cmd_out.replace("\r\r\n", "\n")

            if as_list:
                return cmd_out.splitlines()
            return cmd_out

        if stdout_ != sys.__stdout__:
            cmd_out = subprocess.Popen((executable,) + args,
                                       stdout=subprocess.PIPE,
                                       stderr=subprocess.STDOUT)
            lines = iter(cmd_out.stdout.readline, b'')
            while cmd_out.poll() is None:
                for line in lines:
                    stdout_.write(line.decode("utf-8", "replace"))
        else:
            subprocess.run((executable,) + args)
    except PermissionError:
        stdout_.write("ERROR: cannot execute the provided binary!\n")
        stdout_.write(executable + "\n")
        stdout_.write("Please check the integrity of the above file and restart this program.\n\n")
        return ""


def _check_adb():
    """Check if executable saved in ADB is and actual ADB executable
    and extract its version.
    """

    #TODO: Change flow to following: 1. Check directory set in config (if any) 2. check default path 3. prompt for input
    # if file is found in directory set in config, but is not a valid executable, error out
    # if a file is not found in 1, display a fallback warning and continue to 2

    adb = ADB
    adb_path_changed = False

    if not Path(adb).is_file():
        adb = shutil.which("adb")

    if not adb:
        print("ADB BINARY MISSING!")
        print("Helper could not find ADB, which is required for communicating with Android devices.")
        print("Please drag and drop ADB onto this window and then press enter to continue.")

        adb = input(": ").strip(" '\"")
        if not Path(adb).is_file():
            print("Provided path is not a file!")
            return False
        print("\n")

        adb = str(Path(adb).resolve())
        adb_path_changed = True

    import re
    out = exe(adb, "version", return_output=True, as_list=False)

    if "android debug bridge" not in out.lower():
        print("CORRUPT ADB BINARY!")
        print(adb)
        print("The file was not recognized as a valid ADB executable.")
        return False

    version_name = re.search("(?<=version ).*", out, re.I)
    version_code = re.search("(?<=revision ).*", out, re.I)

    # TODO: Replace with cfg module
    if adb_path_changed:
        globals()["ADB"] = adb
        globals()["EDITED_CONFIG"] = True
    if version_name:
        version_name = version_name.group().strip()

        if version_code:
            " ".join([version_name, version_code.group().strip()])

        globals()["ADB_VERSION"] = version_name

    return True


def _check_aapt(aapt=AAPT):
    """Check if executable saved in AAPT is and actual AAPT executable
    and extract its version.
    """
    #TODO: Change flow to following: 1. Check directory set in config (if any) 2. check default path 3. prompt for input
    # if file is found in directory set in config, but is not a valid executable, error out
    # if a file is not found in 1, display a fallback warning and continue to 2


    aapt = AAPT
    aapt_path_changed = False

    if not Path(aapt).is_file():
        aapt = shutil.which("aapt")

    if not aapt:
        print("AAPT BINARY MISSING!")
        print("Helper could not find AAPT, which is required for operations on apk files.")
        print("Drag and drop the AAPT executable onto this window and press enter to continue.")
        print("You can also skip loading AAPT by leaving the field empty and pressing enter")
        aapt = input(": ").strip(" '\"")
        if aapt:
            if not Path(aapt).is_file():
                print("Provided path is not a file!")
                return False

            aapt = str(Path(aapt).resolve())
            aapt_path_changed = True
        else:
            print("You chose not to load the AAPT. Please note that some features will not be available because of this.")
            print("This dialog will be displayed for every launch until a valid AAPT executable is found.")
            globals()["AAPT"] = ""
            globals()["AAPT_AVAILABLE"] = False
            return
        print("\n")

    import re
    out = exe(aapt, "version", return_output=True, as_list=False)

    if "android asset packaging tool" not in out.lower():
        print("CORRUPT AAPT BINARY!")
        print(aapt)
        print("The file was not recognized as a valid AAPT executable.")
        return False

    version_name = re.search("(?<=android asset packaging tool, v).*", out, re.I)

    # TODO: Replace with cfg module
    if aapt_path_changed:
        globals()["AAPT"] = aapt
        globals()["EDITED_CONFIG"] = True
    if version_name:
        globals()["AAPT_VERSION"] = version_name.group().strip()

    return True


def _load_config(config):
    """"""
    with open(config, mode="r", encoding="utf-8") as config_file:
        for line in config_file.readlines():
            line = line.strip().split("=", maxsplit=1)

            if len(line) != 2:
                continue

            name = line[0].strip()
            value = line[1].strip()

            if name not in HELPER_CONFIG_VARS:
                continue

            globals()[name] = value


def _save_config(config):
    """"""
    with open(config, mode="w", encoding="utf-8") as config_file:
        for name in HELPER_CONFIG_VARS:
            value = globals()[name]

            config_file.write("".join([name, "=", str(value), "\n"]))


# Create the necessary directories and files if they don't yet exist
Path(ADB).parent.mkdir(exist_ok=True)
Path(AAPT).parent.mkdir(exist_ok=True)
Path(CONFIG).touch(exist_ok=True)

#if not Path(COMPRESSION_DEFINITIONS).is_file():
#    with Path(COMPRESSION_DEFINITIONS).open(mode="w", encoding="utf-8") as texture_file:
#        texture_file.write(DEFAULT_COMPRESSION_IDENTIFIERS)

if not Path(CLEANER_CONFIG).is_file():
    with Path(CLEANER_CONFIG).open(mode="w", encoding="utf-8") as cleaner_file:
        cleaner_file.write(DEFAULT_CLEANER_CONFIG)


CONFIG = CONFIG
_load_config(CONFIG)

if not _check_adb():
    print("Please place a valid ADB executable (and its DLLs on Windows) into the default adb location (", str(Path(BASE + "/../adb").resolve()))
    print("or edit the helper_config file manually.")
    sys.exit()
if not _check_aapt() in (None, True):
    print("Please place a valid AAPT executable into the default adb location (", str(Path(BASE + "/../aapt").resolve()))
    print("or edit the helper_config file manually.")

    sys.exit()

CLEANER_CONFIG = str(Path(CLEANER_CONFIG).resolve())
#COMPRESSION_DEFINITIONS = str(Path(COMPRESSION_DEFINITIONS).resolve())

if EDITED_CONFIG:
    _save_config(CONFIG)

# TODO: replace custom config files (helper, gles textures and cleaner) with cfg module
# TODO: add an interface for editing various configs
# TODO: validate aapt and adb using list of known checksums
# TODO: count what adb/aapt calls are made during each session
