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


class App:
    def __init__(self, apk_file):

        #basic info
        self.app_name = ''
        self.host_path = ''

        self.display_name = ''
        self.version_name = ''
        self.version_code = ''

        # requirements
        self.target_sdk = ''
        self.min_sdk = ''
        self.used_permissions = []
        self.used_features = []
        self.supported_abis = []
        self.host_path = apk_file

        self.from_file()


    def _from_device(self, device, limited_init=True):
        raise NotImplementedError()
        dump = device.shell_command("dumpsys", "package", self.app_name,
                                    return_output=True, as_list=False)

        search_group = {
            "version_name" : "(?<=versionName\\=)[!-z]*",
            "version_code" : "(?<=versionCode\\=)[!-z]*",
            "target_sdk" : "(?<=targetSdkVersion\\=)[!-z]*"
            }

        for key, value in search_group.items():
            extracted = re.search(value, dump)
            if extracted:
                self.__dict__[key] = extracted.group().strip()

        # not much can be read from the app while on device
        # so lets get the app to host and check it out!
        if not limited_init:
            apk_path = device.shell_command("pm", "path", self.app_name,
                                            return_output=True, as_list=False)
            apk_path = re.search("(?<=package:).*", apk_path)

            if apk_path:
                self.device_path = apk_path.group().strip()
                local_path = "./" + device.info("Product", "Model") + Path(self.device_path).name
                device.adb_command("pull", self.device_path, local_path)
                self.host_path = local_path
                self.from_file()


    def from_file(self):
        """Load app data from a local apk file."""
        dump = aapt_command("dump", "badging", self.host_path,
                            return_output=True, as_list=False)

        if "error: dump failed" in dump.lower():
            unknown = "Unknown! ({})".format(Path(self.host_path).name)
            self.app_name = unknown
            self.display_name = unknown

        search_group = {
            "app_name" : "(?<=name\\=\\')[^\\']*",
            "display_name" : "(?<=application\\-label\\-en\\-GB\\:\\')[^\\']*",
            "version_name" : "(?<=versionName\\=\\')[^\\']*",
            "version_code" : "(?<=versionCode\\=\\')[^\\']*",
            "min_sdk" : "(?<=sdkVersion\\:\\')[^\\']*",
            "target_sdk" : "(?<=targetSdkVersion\\:\\')[^\\']*",
            "supported_abis" : "(?<=native-code\\: ).*"
            }

        findall_group = {
            "supported_textures" : "(?<=supports\\-gl\\-texture\\:\\')[^\\']*",
            "used_permissions" : "(?<=uses\\-permission\\:\\ name\\=\\')[^\\']*",
            "used_features" : "(?<=uses\\-feature\\:\\ name\\=\\')[^\\']*"
            }

        for key, value in search_group.items():
            extracted = re.search(value, dump)
            if extracted:
                self.__dict__[key] = extracted.group().strip()

        for key, value in findall_group.items():
            extracted = re.findall(value, dump)
            if extracted:
                self.__dict__[key] = extracted

        if self.supported_abis:
            self.supported_abis = self.supported_abis.replace("'", "").strip().split()


    def can_be_installed(self, device):
        """"""
        well_can_it = True
        reasons = []

        # check if device uses a supported Android version
        device_sdk = device.info("OS", "API Level")
        if int(self.min_sdk) > int(device_sdk):
            well_can_it = False
            reasons.append("API level of at least {} is required but the device has {}".format(self.min_sdk, device_sdk))

        # check if device uses supported abis
        uses_one_of_abis = False
        for abi in self.supported_abis:
            if abi in device.info("CPU", "Available ABIs"):
                uses_one_of_abis = True

        if not uses_one_of_abis:
            well_can_it = False
            reasons.append("Device does not use supported abis {}".format(self.supported_abis))

        # check if all features are available
        for feature in self.used_features:
            if feature not in device.device_features:
                well_can_it = False
                reasons.append("Feature '{}' not available on device".format(feature))

        return (well_can_it, reasons)
