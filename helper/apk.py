"""Module for analyzing apk packages with aapt"""
import re
import sys
from pathlib import Path

import helper as helper_

AAPT = helper_.AAPT

def aapt_command(*args, **kwargs):
    """Execute an AAPT command, and return -- or don't -- its result."""
    try:
        return helper_.exe(AAPT, *args, **kwargs)
    except FileNotFoundError:
        print("".join(["Helper expected AAPT to be located in '", AAPT,
                       "' but could not find it.\n"]))
        sys.exit("Please make sure the AAPT binary is in the specified path.")
    except (PermissionError, OSError):
        print(
            " ".join(["Helper could not launch AAPT. Please make sure the",
                      "following path is correct and points to an actual AAPT",
                      "binary:", AAPT, "To fix this issue you may need to",
                      "edit or delete the helper config file, located at:",
                      helper_.CONFIG]))
        sys.exit()


def get_app_name(apk_file, stdout_=sys.stdout):
    """Extract app name of the provided apk, from its manifest file.
    Return name if it is found, an empty string otherwise.
    """
    app_dump = aapt_command(
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
