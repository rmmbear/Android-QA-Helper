"""Module for analyzing apk packages with aapt"""

import re
import sys
import subprocess
from pathlib import Path

import helper as helper_

AAPT = helper_.AAPT


def aapt_execute(*args, return_output=False, as_list=True, stdout_=sys.stdout):
    """Execute an AAPT command, and return -- or don't -- its result."""
    try:
        if return_output:
            cmd_out = subprocess.run((AAPT,) + args, stdout=subprocess.PIPE,
                                     stderr=subprocess.STDOUT).stdout
            cmd_out = cmd_out.decode("utf-8", "replace").strip()

            if as_list:
                return cmd_out.splitlines()
            return cmd_out

        if stdout_ != sys.__stdout__:
            cmd_out = subprocess.Popen((AAPT,) + args, stdout=subprocess.PIPE,
                                       stderr=subprocess.STDOUT).stdout
            cmd_out = cmd_out.decode("utf-8", "replace").strip()

            last_line = ''
            for line in cmd_out.stdout:
                if line != last_line:
                    stdout_.write(line)
                    last_line = line
        else:
            subprocess.run((AAPT,) + args)
    except FileNotFoundError:
        stdout_.write("".join(["Helper expected AAPT to be located in '", AAPT,
                               "' but could not find it.\n"]))
        sys.exit("Please make sure the AAPT binary is in the specified path.")
    except (PermissionError, OSError):
        stdout_.write(" ".join(["Helper could not launch AAPT. Please make",
                                "sure the following path is correct and",
                                "points to an actual AAPT binary:", AAPT,
                                "To fix this issue you may need to edit or",
                                "delete the helper config file, located at:",
                                helper_.CONFIG]))
        sys.exit()


def get_app_name(apk_file, stdout_=sys.stdout):
    """Extract app name of the provided apk, from its manifest file.
    Return name if it is found, an empty string otherwise.
    """
    app_dump = aapt_execute(
        "dump", "badging", apk_file, return_output=True, as_list=False)
    app_name = re.search("(?<=name=')[^']*", app_dump)

    if app_name:
        return app_name.group()

    app_name = "UNKNOWN APP NAME (" + Path(apk_file).name + ")"
    stdout_.write("ERROR: Unknown app name\n")
    stdout_.write(
        " ".join(["Could not extract app name from the provided apk file:\n"]))
    stdout_.write(apk_file + "\n")
    stdout_.write("It may not be a valid apk archive.\n")
    return app_name
