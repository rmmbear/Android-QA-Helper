#         Android QA Helper - helping you test Android apps!
#          Copyright (C) 2017  rmmbear
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
import os
import inspect
import shutil
from pathlib import Path
from collections import OrderedDict

VERSION = "0.10"
VERSION_DATE = "14-03-2017"
GITHUB_SOURCE = "https://github.com/rmmbear/Android-QA-Helper"
VERSION_STRING = " ".join(["Android QA Helper ver", VERSION, ":",
                           VERSION_DATE, ": Copyright (c) 2017 rmmbear"]
                         )
SOURCE_STRING = "Check the source code at " + GITHUB_SOURCE

ABI_TO_ARCH = {"armeabi"    :"32bit (ARM)",
               "armeabi-v7a":"32bit (ARM)",
               "arm64-v8a"  :"64bit (ARM64)",
               "x86"        :"32bit (Intel x86)",
               "x86_64"     :"64bit (Intel x86_64)",
               "mips"       :"32bit (Mips)",
               "mips64"     :"64bit (Mips64)",
              }

CLEANER_OPTIONS = {"remove"           :(["shell", "rm", "--"]),
                   "remove_recursive" :(["shell", "rm", "-r", "--"]),
                   "uninstall"        :(["uninstall"]),
                   "replace"          :(["shell", "rm", "-f", "--"],
                                        ["push"])
                  }

HELPER_CONFIG_VARS = ["ADB", "AAPT"]

def get_script_dir():
    """
    """

    if getattr(sys, 'frozen', False):
        path = os.path.abspath(sys.executable)
    else:
        path = inspect.getabsfile(get_script_dir)

    path = os.path.realpath(path)
    return os.path.dirname(path)


def load_compression_types():
    """
    """

    with open(COMPRESSION_DEFINITIONS, mode="r", encoding="utf-8") as comps:
        for line in comps.read().splitlines():
            if not line or line.startswith("#"):
                continue

            comp_id, comp_name = line.split(",")
            COMPRESSION_TYPES[comp_id] = comp_name


def load_config(config):
    with open(config, mode="r") as config_file:
        for line in config_file.readlines():
            line = line.strip().split("=", maxsplit=1)

            if len(line) != 2:
                continue

            name = line[0].strip()
            value = line[1].strip()

            if name not in HELPER_CONFIG_VARS:
                continue

            globals()[name] = value


def save_config(config):
    with open(config, mode="w", encoding="utf-8") as config_file:
        for name in HELPER_CONFIG_VARS:
            value = globals()[name]

            config_file.write("".join([name, "=", str(value), "\n"]))


EDITED_CONFIG = False
BASE = get_script_dir()
CONFIG = str(Path(BASE + "/../helper_config").resolve())
ADB = str(Path(BASE + "/../adb/adb").resolve())
AAPT = str(Path(BASE + "/../aapt/aapt").resolve())
Path(ADB).parent.mkdir(exist_ok=True)
Path(AAPT).parent.mkdir(exist_ok=True)

if Path(CONFIG).is_file():
    print("YEAH ITS THERE")
    load_config(CONFIG)

if sys.platform == "win32":
    AAPT += ".exe"
    ADB += ".exe"

if not Path(ADB).is_file():
    ADB = shutil.which("adb")

    if not ADB:
        print("Helper could not find ADB, which is required for this program.",
              "Close this windoww and place the binary in",
              str(Path(BASE + "/../adb").resolve()), "or enter its path below")
        user_path = input(": ")
        if len(user_path) > 1:
            if user_path[0] in ["'", '"']:
                user_path = user_path[1::]

            if user_path[-1] in ["'", '"']:
                user_path = user_path[:-1]

        if not Path(user_path).is_file():
            print("Provided path is not a file!")
            sys.exit()

        ADB = str(Path(user_path).resolve())
        EDITED_CONFIG = True

if not Path(AAPT).is_file():
    AAPT = shutil.which("aapt")

    if not AAPT:
        print("Helper could not find ADB, which is required for this program.",
              "Close this windoww and place the binary in",
              str(Path(BASE + "/../aapt").resolve()), "or enter its path below")
        user_path = input(": ").strip()
        if len(user_path) > 1:
            if user_path[0] in ["'", '"']:
                user_path = user_path[1::]

            if user_path[-1] in ["'", '"']:
                user_path = user_path[:-1]

        if not Path(user_path).is_file():
            print("Provided path is not a file!")
            sys.exit()

        AAPT = str(Path(user_path).resolve())
        EDITED_CONFIG = True

CLEANER_CONFIG = BASE + "/../cleaner_config"
COMPRESSION_DEFINITIONS = BASE + "/../compression_identifiers"
COMPRESSION_TYPES = {}
load_compression_types()

if EDITED_CONFIG:
    save_config(CONFIG)
