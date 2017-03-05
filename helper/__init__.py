import sys
import os
import inspect
import shutil
from pathlib import Path
from collections import OrderedDict

VERSION = "0.10"
VERSION_DATE = "05-03-2017"
GITHUB_SOURCE = "https://github.com/rmmbear/Android-QA-Helper"
VERSION_STRING = " ".join(["Android QA Helper ver", VERSION, ":",
                           VERSION_DATE, ": Copyright (c) 2017 rmmbear"]
                         )
SOURCE_STRING = "Check the source code at " + GITHUB_SOURCE

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


BASE = get_script_dir()
DEFAULT_ADB = BASE + "/adb/adb"
DEFAULT_AAPT = BASE + "/build_tools/aapt"

if sys.platform == "win32":
    DEFAULT_AAPT += ".exe"
    DEFAULT_ADB += ".exe"

ADB = shutil.which("adb")
if not ADB:
    if Path(DEFAULT_ADB).is_file():
        ADB = DEFAULT_ADB
    else:
        print("Helper could not find ADB, which is required for this program.")
        print("Please enter the path pointing to ADB binary and press enter")
        user_adb = input(": ").strip()
        if not Path(user_adb).is_file():
            print("Provided path is not a file!")
            sys.exit()

        ADB = str(Path(user_adb).resolve())

AAPT = shutil.which("aapt")
if not AAPT:
    if Path(DEFAULT_AAPT).is_file():
        AAPT = DEFAULT_AAPT
    else:
        print("Helper could not find AAPT, which is required for this program.")
        print("Please enter the path pointing to AAPT binary and press enter")
        user_aapt = input(": ").strip()
        if not Path(user_aapt).is_file():
            print("Provided path is not a file!")
            sys.exit()

        AAPT = str(Path(user_aapt).resolve())

CLEANER_CONFIG = BASE + "/cleaner_config"
COMPRESSION_DEFINITIONS = BASE + "/compression_identifiers"
COMPRESSION_TYPES = {}
load_compression_types()