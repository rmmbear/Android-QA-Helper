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
from shutil import which
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
BIN = str(Path(CWD, "bin"))
CLEANER_CONFIG = str(Path(CWD, "cleaner_config"))
Path(CWD).mkdir(parents=True, exist_ok=True)
Path(BIN).mkdir(parents=True, exist_ok=True)
Path(CLEANER_CONFIG).touch(exist_ok=True)

#config requires CWD from this module
from . import config

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


def exe(executable, *args, return_output=False, as_list=False, stdout_=sys.stdout):
    """Run provided file as executable.
    Return string containing the output of executed command.
    """
    LOGGER.debug("Executing %s %s", executable.name, args)
    try:
        if return_output:
            cmd_out = subprocess.run((executable.__fspath__(),) + args,
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
            cmd_out = subprocess.Popen((executable.__fspath__(),) + args,
                                       stdout=subprocess.PIPE,
                                       stderr=subprocess.STDOUT)
            lines = iter(cmd_out.stdout.readline, b'')
            while cmd_out.poll() is None:
                for line in lines:
                    stdout_.write(line.decode("utf-8", "replace"))
        else:
            subprocess.run((executable.__fspath__(),) + args)

        return ""
    except PermissionError:
        if executable.is_dir():
            stdout_.write("ERROR: Provided path points to a directory and not a file")
        else:
            stdout_.write(
                "ERROR: Could not execute the provided binary due permission error!\n"
                "   Please make sure the current user has necessary permissions!\n")
        stdout_.write(f"    {executable}")
        sys.exit()
    except FileNotFoundError:
        stdout_.write(
            f"ERROR: Executable does not exist: {executable}\n")
        stdout_.write(f"    {executable}")
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
        stdout_.write(f"    {executable}")
        #TODO: should either re-raise the error or throw a custom one
        # preferrably, sys.exit() should only be thrwon in cli/gui
        sys.exit()



def find_executable(executable_name, version_command="version"):
    """
    Return path of the executable, whose name matches executable_name.
    On windows ".exe" extension is added automatically to executable_name.
    This function looks for the executable in the following ways (in order):
    1. check config for saved valid path from previous run
    2. check in {CWD}/bin/{executable_name}
    3. use shutil.which to look find the executable

    Return pathlib Path object.
    """
    # load the path saved in config
    executable = config.CONFIG_VALS[executable_name]
    if executable:
        LOGGER.info("Received path from config for %s: %s", executable_name, executable)
        if not executable.is_file():
            LOGGER.info("File found, but missing ")
            executable = None
    else:
        LOGGER.info("Did not receive %s's path from config", executable_name)

    # previous method failed,  check default bin folder
    if not executable:
        LOGGER.info("%s not found in config", executable_name)
        LOGGER.info("Looking for %s in default BIN folder (%s)", executable_name, BIN)
        if sys.platform == "win32":
            executable = Path(BIN, executable_name+".exe")
        else:
            executable = Path(BIN, executable_name)
        if not executable.is_file():
            executable = None

    # previous method failed, search for executable in PATH
    if not executable:
        LOGGER.info("%s not found in default bin folder (%s)", executable_name, BIN)
        LOGGER.info("Looking for %s using shutil.which", executable_name)
        executable = which(executable_name)
        if executable:
            executable = Path(executable)

    if not executable:
        LOGGER.info("%s not found with 'shutil.which'", executable_name)
        LOGGER.error("Could not find executable (%s)", executable_name)
        return "", "Unknown"

    # not checking for permissions - these will be tested anyway in exe()
    LOGGER.debug("Successfully found %s (%s)", executable_name, executable)
    version = exe(executable, version_command, return_output=True).strip()
    return executable, version


ADB = None
AAPT = None
ADB_VERSION = "Unknown"
AAPT_VERSION = "Unknown"
ADB, ADB_VERSION = find_executable("adb")
AAPT, AAPT_VERSION = find_executable("aapt")

LOGGER.info("ADB VERSION: %s", ADB_VERSION)
LOGGER.info("AAPT VERSION: %s", AAPT_VERSION)

# TODO: count what adb/aapt calls are made during each session
