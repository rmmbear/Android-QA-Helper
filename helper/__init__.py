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


VERSION = "0.14"
VERSION_DATE = "15-06-2017"
VERSION_STRING = " ".join(["Android QA Helper ver", VERSION, ":", VERSION_DATE,
                           ": Copyright (c) 2017 rmmbear"])
SOURCE_STRING = "Check the source code at https://github.com/rmmbear/Android-QA-Helper"

ABI_TO_ARCH = {"armeabi"    :"32bit (ARM)",
               "armeabi-v7a":"32bit (ARM)",
               "arm64-v8a"  :"64bit (ARM64)",
               "x86"        :"32bit (Intel x86)",
               "x86_64"     :"64bit (Intel x86_64)",
               "mips"       :"32bit (Mips)",
               "mips64"     :"64bit (Mips64)",
              }

HELPER_CONFIG_VARS = ["ADB", "AAPT"]

def exe(executable, *args, return_output=False, as_list=True,
        stdout_=sys.stdout):
    """Run the provided executable with specified commands"""
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


def get_script_dir():
    """"""
    if getattr(sys, 'frozen', False):
        path = os.path.abspath(sys.executable)
    else:
        path = inspect.getabsfile(get_script_dir)

    path = os.path.realpath(path)
    return os.path.dirname(path)


def load_config(config):
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


def save_config(config):
    """"""
    with open(config, mode="w", encoding="utf-8") as config_file:
        for name in HELPER_CONFIG_VARS:
            value = globals()[name]

            config_file.write("".join([name, "=", str(value), "\n"]))


AAPT_AVAILABLE = True
EDITED_CONFIG = False
BASE = get_script_dir()

ADB = Path(BASE + "/../adb/adb")
AAPT = Path(BASE + "/../aapt/aapt")
CONFIG = Path(BASE + "/../helper_config")

if sys.platform == "win32":
    AAPT += ".exe"
    ADB += ".exe"

Path(ADB).parent.mkdir(exist_ok=True)
Path(AAPT).parent.mkdir(exist_ok=True)
if not CONFIG.is_file():
    with CONFIG.open(mode="w", encoding="utf-8") as f:
        pass

CONFIG = str(CONFIG.resolve())
load_config(CONFIG)

if not Path(ADB).is_file():
    ADB = shutil.which("adb")

    if not ADB:

        print("\nADB BINARY MISSING!")
        print("Helper could not find ADB, which is required for this program.",
              "Close this window, place the binary in",
              str(Path(BASE + "/../adb").resolve()), "and delete helper config",
              "(located at:", CONFIG, ") or enter its path below")
        user_path = input(": ")
        user_path = user_path.strip("'\"")
        if not Path(user_path).is_file():
            print("Provided path is not a file!")
            sys.exit()

        ADB = Path(user_path)
        EDITED_CONFIG = True

if not Path(AAPT).is_file():
    AAPT = shutil.which("aapt")

    if not AAPT:
        print("\nAAPT BINARY MISSING!")
        print("Helper could not find AAPT, which is required for certain",
              "operations on apk files, including app installation. To load",
              "the aapt, close this window, place the binary in",
              str(Path(BASE + "/../aapt").resolve()), "and delete helper config",
              "(located at:", CONFIG, "). You can also enter its path below",
              "or press enter without typing anything to skip this.")
        user_path = input(": ").strip()
        if user_path:
            user_path = user_path.strip("'\"")
            if not Path(user_path).is_file():
                print("Provided path is not a file!")
                sys.exit()

            AAPT = Path(user_path)
            EDITED_CONFIG = True
        else:
            print("You chose not to load the aapt binary. Please note that",
                  "some features will not be available because of this.")
            AAPT_AVAILABLE = False

ADB = str(ADB)
AAPT = str(AAPT)

CLEANER_CONFIG = Path(BASE + "/../cleaner_config")
if not CLEANER_CONFIG.is_file():
    with CLEANER_CONFIG.open(mode="w", encoding="utf-8") as empty_file:
        pass

COMPRESSION_DEFINITIONS = Path(BASE + "/../compression_identifiers")
if not COMPRESSION_DEFINITIONS.is_file():
    with COMPRESSION_DEFINITIONS.open(mode="w", encoding="utf-8") as empty_file:
        pass

CLEANER_CONFIG = str(CLEANER_CONFIG)
COMPRESSION_DEFINITIONS = str(COMPRESSION_DEFINITIONS)

if EDITED_CONFIG:
    save_config(CONFIG)
