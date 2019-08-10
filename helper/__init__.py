#   Android QA Helper - helping you test Android apps!
#   Copyright (C) 2017-2019 rmmbear
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

import sys
import logging
import subprocess

from pathlib import Path
from time import strftime

VERSION = "0.15"

def _get_working_dir():
    """Return string representing the current working directory.
    This function accounts for three cases:
    - package in frozen code form: same directory as executable
    - installed as pip package: helper directory in user's home
    - source code downloaded from github: one directory above source
    """
    if getattr(sys, 'frozen', False):
        cwd = Path(sys.executable).parent
    else:
        cwd = Path(__file__).parent / ".."

    cwd = cwd.resolve()
    if str(cwd.parent) in sys.path[1::]:
        cwd = Path.home() / "AndroidQAH"

    return str(cwd)


CWD = _get_working_dir()
ADB = str(Path(CWD, "bin", "adb"))
AAPT = str(Path(CWD, "bin", "aapt"))
CONFIG = str(Path(CWD, "helper_config"))
CLEANER_CONFIG = str(Path(CWD, "cleaner_config"))

# Create the necessary directories and files if they don't yet exist
Path(CWD).mkdir(parents=True, exist_ok=True)
Path(ADB).parent.mkdir(parents=True, exist_ok=True)
Path(AAPT).parent.mkdir(parents=True, exist_ok=True)
Path(CONFIG).touch(exist_ok=True)

ADB_VERSION = "Unknown"
AAPT_VERSION = "Unknown"
AAPT_AVAILABLE = False
EDITED_CONFIG = False
HELPER_CONFIG_VARS = ["ADB", "AAPT"]

LOG_FORMAT_FILE = logging.Formatter("[%(levelname)s] T+%(relativeCreated)d: %(name)s.%(funcName)s() line:%(lineno)d %(message)s")
LOG_FORMAT_TERM = logging.Formatter("[%(levelname)s] %(message)s")
LOGGER = logging.getLogger("helper")
LOGGER.setLevel(logging.DEBUG)
FH = logging.FileHandler(CWD + "/lastrun.log", mode="w")
FH.setLevel(logging.DEBUG)
FH.setFormatter(LOG_FORMAT_FILE)
CH = logging.StreamHandler()
CH.setLevel(logging.WARN)
CH.setFormatter(LOG_FORMAT_TERM)

LOGGER.addHandler(CH)
LOGGER.addHandler(FH)

LOGGER.info("----- %s : Starting Android Helper v%s -----", strftime("%Y-%m-%d %H:%M:%S"), VERSION)

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

DEFAULT_CLEANER_CONFIG = """# This is default cleaner config file, it contains explanation of all available
# commands, examples, and some default rules for removing helper's leftover files.
# This config file is used by helper's 'clean' command if no other config is
# supplied.
#
# To use custom config you can either edit and add custom operations to this file
# (it will then be used by default when using 'helper clean') or create a separate
# file and pass it as an argument to the clean command (see 'helper clean -h'
# for more info).
#
# One line can contain only one command, but a command can be continued over
# multiple lines with backslash (as in the example for the shell command below).
# Lines starting with '#' are ignored (the character has no effect if not at the
# start of a line and will not be treated specially otherwise).
# If deleted, this file will be regenerated upon helper's launch.
# All paths concerning the device must be in unix format ('/' is the root,
# elements delimited by '/'), but those concerning host PC can be in either
# windows or unix format.
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
####EXAMPLES:
#
# remove /mnt/sdcard/Screenshots/* #Remove all files from the screenshots folder
# recursiverm /mnt/sdcard/DCIM     #Remove DCIM directory and all its contents
#
# Remove all mp4 files from DCIM folder and all folders below it:
#    findremove {internal_storage}/DCIM *.mp4
#
# dataclear com.android.browser      #Clear data of the default android browser
# dataclear helper activity          #Clear data of all helper-installed apps
# dataclear from com.android.vending #Clear data of Play Store apps
# dataclear 3rdparty                 #Clear data of all non-system apps
#
# uninstall com.android.browser      #Uninstall default android browser
# uninstall helper activity          #Uninstall all helper-installed apps
# uninstall from com.android.vending #Uninstall apps installed by Play Store
# uninstall 3rdparty                 #Uninstalls all third party apps
#
# Move screenshots folder from internal storage to root of external storage:
#    move {internal_storage}/Pictures/Screenshots {external_storage}/
#
# Copy apk to a file named "browser_backup.apk" on external storage:
#    copy /data/app/com.android.browser.apk {external_storage}/browser_backup.apk
#
# Save m's music folder as 'm_music' on device's external storage:
#    push /home/m/Music {external_storage}/m_music
#
# Copy the screenshots folder and all its content onto m's desktop:
#    pull {internal_storage}/Pictures/Screenshots C:\\Users\\m\\Desktop\\
#
# Execute a long shell one-liner which removes all packages installed by GPStore
#    shell pm list packages -i | grep installer=com.android.vending | \\
#          while read pline; do pline=${pline#package:}; pline=${pline% *}; \\
#          echo "removing app $pline"; pm uninstall $pline; done
#
# (above bash one-liner is equivalent to 'uninstall from com.android.vending')
#

####DEFAULT CLEANER COMMANDS:
# remove files left by helper
remove {internal_storage}/helper_*
recursiverm /data/local/tmp/helper
# make sure install location is set to 'auto'
shell pm set-install-location 0

"""

if sys.platform == "win32":
    AAPT += ".exe"
    ADB += ".exe"


def exe(executable, *args, return_output=False, as_list=False,
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
            # on Linux each line is ended with '\r\n'
            # on Windows for some reason this becomes '\r\r\n'
            # which results in empty lines
            # as long as all functions interacting directly with exe's output
            # account for empty lines, this should not be a problem

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
            f"ERROR: Executable does not exist: {executable}\n")
        sys.exit()
    except OSError as error:
        stdout_.write(
            "ERROR: Could not execute provided file due to an OS Error\n"
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


if not Path(CLEANER_CONFIG).is_file():
    with Path(CLEANER_CONFIG).open(mode="w", encoding="utf-8") as cleaner_file:
        cleaner_file.write(DEFAULT_CLEANER_CONFIG)


_load_config(CONFIG)

CLEANER_CONFIG = str(Path(CLEANER_CONFIG).resolve())

if EDITED_CONFIG:
    _save_config(CONFIG)

LOGGER.info("Using ADB version %s", ADB_VERSION)
LOGGER.info("Using AAPT version %s", AAPT_VERSION)

# TODO: replace custom config files (helper, gles textures and cleaner) with cfg module
# TODO: add an interface for editing various configs
# TODO: count what adb/aapt calls are made during each session
