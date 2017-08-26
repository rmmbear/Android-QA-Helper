#   Android QA Helper - helping you test Android apps!
#   Copyright (C) 2017  rmmbear
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
import inspect
import shutil
import subprocess
from pathlib import Path

# Program meta-info
VERSION = "0.14"
VERSION_DATE = "27-08-2017"
VERSION_STRING = " ".join(["Android QA Helper ver", VERSION, ":", VERSION_DATE,
                           ": Copyright (c) 2017 rmmbear"])
SOURCE_STRING = "Check the source code at https://github.com/rmmbear/Android-QA-Helper"

# Global config variables
ABI_TO_ARCH = {"armeabi"    :"32bit (ARM)",
               "armeabi-v7a":"32bit (ARM)",
               "arm64-v8a"  :"64bit (ARM64)",
               "x86"        :"32bit (Intel x86)",
               "x86_64"     :"64bit (Intel x86_64)",
               "mips"       :"32bit (Mips)",
               "mips64"     :"64bit (Mips64)",
              }
ADB_VERSION = "Unknown"
ADB_REVISION = "Unknown"
AAPT_VERSION = "Unknown"
AAPT_AVAILABLE = True
EDITED_CONFIG = False
HELPER_CONFIG_VARS = ["ADB", "AAPT"]


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
COMPRESSION_DEFINITIONS = BASE + "/../compression_identifiers"

if sys.platform == "win32":
    AAPT += ".exe"
    ADB += ".exe"


def exe(executable, *args, return_output=False, as_list=True,
        stdout_=sys.stdout):
    """Run the provided executable with specified commands"""
    try:
        if return_output:
            cmd_out = subprocess.run((executable,) + args, stdout=subprocess.PIPE,
                                     stderr=subprocess.STDOUT).stdout
            cmd_out = cmd_out.decode("utf-8", "replace")

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
    adb = ADB
    adb_path_changed = False

    if not Path(adb).is_file():
        adb = shutil.which("adb")

    if not adb:
        print("ADB BINARY MISSING!")
        print("Helper could not find ADB, which is required for this program.",
              "Close this window, place the binary in:",
              "'{}'".format(Path(BASE + "/../adb").resolve()),
              "and delete helper config or enter its path below (use drag and",
              "drop if your terminal allows it).")
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
        print("The file is either not an executable binary or is not an ADB",
              "binary. Replace the file with an actual ADB binary and edit",
              "or remove the helper config file.")
        return False

    version_name = re.search("(?<=version ).*", out, re.I)
    version_code = re.search("(?<=revision ).*", out, re.I)

    if adb_path_changed:
        globals()["ADB"] = adb
        globals()["EDITED_CONFIG"] = True
    if version_name:
        globals()["ADB_VERSION"] = version_name.group().strip()
    if version_code:
        globals()["ADB_REVISION"] = version_code.group().strip()

    return True


def _check_aapt(aapt=AAPT):
    """Check if executable saved in AAPT is and actual AAPT executable
    and extract its version.
    """
    aapt = AAPT
    aapt_path_changed = False

    if not Path(aapt).is_file():
        aapt = shutil.which("aapt")

    if not aapt:
        print("AAPT BINARY MISSING!")
        print("Helper could not find AAPT, which is required for certain",
              "operations on apk files, including app installation. To load",
              "the aapt, close this window, place the binary in:",
              "'{}'".format(Path(BASE + "/../aapt").resolve()),
              "and delete helper config. You can also enter its path below",
              "(use drag-and-drop if your terminal allows it) or press enter",
              "without typing anything to skip this.")
        aapt = input(": ").strip(" '\"")
        if aapt:
            if not Path(aapt).is_file():
                print("Provided path is not a file!")
                return False

            aapt = str(Path(aapt).resolve())
            aapt_path_changed = True
        else:
            print("You chose not to load the aapt binary. Please note that",
                  "some features will not be available because of this.")
            globals()["AAPT"] = ""
            globals()["AAPT_AVAILABLE"] = False
            return
        print("\n")

    import re
    out = exe(aapt, "version", return_output=True, as_list=False)

    if "android asset packaging tool" not in out.lower():
        print("CORRUPT AAPT BINARY!")
        print(aapt)
        print("The file is either not an executable binary or is not an AAPT",
              "binary. Replace the file with an actual AAPT binary and edit",
              "or remove the helper config file.")
        return False

    version_name = re.search("(?<=android asset packaging tool, v).*", out, re.I)

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
Path(CLEANER_CONFIG).touch(exist_ok=True)
Path(COMPRESSION_DEFINITIONS).touch(exist_ok=True)

CONFIG = CONFIG
_load_config(CONFIG)

if not _check_adb():
    sys.exit()
if not _check_aapt() in (None, True):
    sys.exit()

CLEANER_CONFIG = str(CLEANER_CONFIG)
COMPRESSION_DEFINITIONS = str(COMPRESSION_DEFINITIONS)

if EDITED_CONFIG:
    _save_config(CONFIG)
