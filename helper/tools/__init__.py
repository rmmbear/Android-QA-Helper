import shutil
from pathlib import Path

from helper import ADB, AAPT, exe

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
            f"{version_name} {version_code.group().strip()}"

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


"""
if not _check_adb():
    print("Please place a valid ADB executable (and its DLLs on Windows) into the default adb location (", str(Path(CWD + "/../adb").resolve()))
    print("or edit the helper_config file manually.")
    sys.exit()
if not _check_aapt() in (None, True):
    print("Please place a valid AAPT executable into the default adb location (", str(Path(CWD + "/../aapt").resolve()))
    print("or edit the helper_config file manually.")

    sys.exit()
"""
