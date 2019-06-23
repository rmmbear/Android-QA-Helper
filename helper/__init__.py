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
import time
import shutil
import inspect
import logging
import subprocess
from pathlib import Path

# Program metadata
VERSION = "0.15"
VERSION_STRING = f"Android Helper v{VERSION}"
SOURCE_STRING = "Check the source code at https://github.com/rmmbear/Android-QA-Helper"

LOG_FORMAT_FILE = logging.Formatter("[%(levelname)s] T+%(relativeCreated)d: %(name)s.%(funcName)s() line:%(lineno)d %(message)s")
LOG_FORMAT_TERM = logging.Formatter("[%(levelname)s] %(message)s")
LOGGER = logging.getLogger("helper")
LOGGER.setLevel(logging.DEBUG)
FH = logging.FileHandler("lastrun.log", mode="w")
FH.setLevel(logging.DEBUG)
FH.setFormatter(LOG_FORMAT_FILE)
CH = logging.StreamHandler()
CH.setLevel(logging.WARN)
CH.setFormatter(LOG_FORMAT_TERM)

LOGGER.addHandler(CH)
LOGGER.addHandler(FH)

LOGGER.info("----- %s : Starting %s -----", time.strftime("%Y-%m-%d %H:%M:%S"), VERSION_STRING)


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
####COMMANDS:
# 'remove' or 'rm' - Remove file or empty directory. Accepts wildcards.
#                    Mimics behavior of the unix command 'rm'
# 'recursiverm'    - Remove directory and all its contents. Accepts wildcards.
#                    Behaves like unix's 'rm -R'.
# 'findremove'     - Perform a recursive, case-insensitive search for files
#                    matching specified name. This is like unix's
#                    'find <arg1> -iname <arg2> -type f -delete'. First argument
#                    is the directory in which to search, second is name to
#                    search for, which can use star wildcards. Only removes files.
# 'dataclear'      - Clear app's data. Argument can be a package id, "helper
#                    activity", "from <name>" (where <name> is the name of the
#                    installer), or "3rdparty"
# 'uninstall'      - Remove installed app from device. Argument can be a
#                    package id (for example "com.android.browser") to remove a
#                    specific known app, "helper activity" to remove app
#                    installed by helper (Note that this will not work for apps
#                    installed with a non-default installer name),
#                    "from <name>" to remove apps installed by <name>, or
#                    "3rdparty" to remove ALL third party apps (use caution)
# 'move' or 'mv'   - Move a file or directory. 1st argument is always the source
#                    (the item being moved) and the second is the destination.
#                    behaves like unix 'mv'. Operates only on
# 'copy' or 'cp'   - Copy a file or directory. 1st argument is the source (the
#                    item being copied) and second is the destination. Behaves
#                    like the unix 'cp'.
# 'push'           - Same functionality as adb's push - copy files from host PC
#                    onto connected device. 1st argument is a file or directory
#                    on host PC (in unix or window format), while the second is
#                    the destination path on device.
# 'pull'           - Same functionality as adb's pull - copy files from device
#                    onto host PC. 1st argument is the source file on the device
#                    that is being copied into directory on host PC in second
#                    argument. Host PC path can be in either unix or windows
#                    format.
# 'shell' or 'sh'  - Raw shell command/bash script.
#
####SPECIAL TOKENS:
# The following names have special meaning and can be inserted into paths:
#
# {internal_storage} - Path to the internal storage (also called internal SD).
# {external_storage} - Path to external storage (usually a removable SD Card).
#

# remove files left by helper
remove : /mnt/sdcard/*_screenrecord_*.mp4
remove : /mnt/sdcard/*_anr_*.txt
remove : /data/local/tmp/helper_*
"""

def _get_working_dir():
    """Return string representing the current working directory.
    If frozen, this will be the same directory as the one containing
    base executable, otherwise it will be one directory above the source
    code.
    """
    if getattr(sys, 'frozen', False):
        cwd = Path(sys.executable).parent
    else:
        cwd = Path(inspect.getabsfile(_get_working_dir)).parent / ".."

    return str(cwd.resolve())


CWD = _get_working_dir()
ADB = CWD + "/bin/adb"
AAPT = CWD + "/bin/aapt"
CONFIG = CWD + "/helper_config"
CLEANER_CONFIG = CWD + "/cleaner_config"

if sys.platform == "win32":
    AAPT += ".exe"
    ADB += ".exe"


def exe(executable, *args, return_output=False, as_list=True,
        stdout_=sys.stdout):
    """Run provided file as executable.
    Return string containing the output of executed command.
    """
    if executable not in (ADB, AAPT):
        LOGGER.debug("Executing %s", str([executable, *args]))

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
            #if sys.platform == "win32" and executable == ADB:
            #    cmd_out = cmd_out.replace("\r\r\n", "\n")

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

        return ""
    except PermissionError:
        stdout_.write(
            "ERROR: Could not execute the provided binary due permission error!\n"
            "   Please make sure the current user has necessary permissions!\n")
        sys.exit()
    except FileNotFoundError:
        stdout_.write(
            f"ERROR: Provided executable does not exist: {executable}.\n")
        sys.exit()
    except OSError as error:
        stdout_.write(
            "ERROR: Could not execute provided file due to an OS Error.\n"
            f"    Executable's path: {AAPT}\n"
            f"    OSError error number: {error.errno}\n"
            f"    Error message: {error}")
        if error.errno == 8:
            stdout_.write(
                "    This is most likely because the file is not in executable format!\n")
        #TODO: should either re-raise the error or throw a custom one
        sys.exit()


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
            config_file.write(f"{name}={value}\n")


# Create the necessary directories and files if they don't yet exist
Path(ADB).parent.mkdir(parents=True, exist_ok=True)
Path(AAPT).parent.mkdir(parents=True, exist_ok=True)
Path(CONFIG).touch(exist_ok=True)


if not Path(CLEANER_CONFIG).is_file():
    with Path(CLEANER_CONFIG).open(mode="w", encoding="utf-8") as cleaner_file:
        cleaner_file.write(DEFAULT_CLEANER_CONFIG)


CONFIG = CONFIG
_load_config(CONFIG)

CLEANER_CONFIG = str(Path(CLEANER_CONFIG).resolve())

if EDITED_CONFIG:
    _save_config(CONFIG)

LOGGER.info("Using ADB version %s", ADB_VERSION)
LOGGER.info("Using AAPT version %s", AAPT_VERSION)

# TODO: replace custom config files (helper, gles textures and cleaner) with cfg module
# TODO: add an interface for editing various configs
# TODO: validate aapt and adb using list of known checksums
# TODO: count what adb/aapt calls are made during each session
