"""Module for analyzing apk packages with aapt"""
import re
import logging
from pathlib import Path
from argparse import ArgumentParser
import helper

VERSION = 0.1
LOGGER = logging.getLogger(__name__)
AAPT = helper.AAPT

# last updated: 2017.07.19
# https://developer.android.com/reference/android/Manifest.permission.html
ANDROID_DANGEROUS_PERMISSIONS = """
android.permission.ACCESS_COARSE_LOCATION
android.permission.ACCESS_FINE_LOCATION
com.android.voicemail.permission.ADD_VOICEMAIL
android.permission.ANSWER_PHONE_CALLS
android.permission.BODY_SENSORS
android.permission.CALL_PHONE
android.permission.CAMERA
android.permission.GET_ACCOUNTS
android.permission.PROCESS_OUTGOING_CALLS
android.permission.READ_CALENDAR
android.permission.READ_CALL_LOG
android.permission.READ_CONTACTS
android.permission.READ_EXTERNAL_STORAGE
android.permission.READ_PHONE_NUMBERS
android.permission.READ_PHONE_STATE
android.permission.READ_SMS
android.permission.RECEIVE_MMS
android.permission.RECEIVE_SMS
android.permission.RECEIVE_WAP_PUSH
android.permission.RECORD_AUDIO
android.permission.SEND_SMS
android.permission.USE_SIP
android.permission.WRITE_CALENDAR
android.permission.WRITE_CALL_LOG
android.permission.WRITE_CONTACTS
android.permission.WRITE_EXTERNAL_STORAGE
""".strip().splitlines()

# API Level: Android Version, Version Code, Human Readable Name
# https://developer.android.com/guide/topics/manifest/uses-sdk-element.html
# Last updated: 2018.09.29
API_LEVEL_MATRIX = {
    #29 : ("next", "next", "next"),
    28 : ("9", "P", "Pie"),
    27 : ("8.1", "O_MR1", "Oreo"),
    26 : ("8.0", "O", "Oreo"),
    25 : ("7.1", "N_MR1", "Nougat"),
    24 : ("7.0", "N", "Nougat"),
    23 : ("6.0", "M", "Marshmallow"),
    22 : ("5.1", "LOLLIPOP_MR1", "Lollipop"),
    21 : ("5.0", "LOLLIPOP", "Lollipop"),
    20 : ("4.4W", "KITKAT_WATCH", "KitKat Watch"),
    19 : ("4.4", "KITKAT", "KitKat"),
    18 : ("4.3", "JELLY_BEAN_MR2", "Jelly Bean"),
    17 : ("4.2", "JELLY_BEAN_MR1", "Jelly Bean"),
    16 : ("4.1", "JELLY_BEAN", "Jelly Bean"),
    15 : ("4.0.3", "ICE_CREAM_SANDWICH_MR1", "Ice Cream Sandwich"),
    14 : ("4.0", "ICE_CREAM_SANDWICH", "Ice Cream Sandwich"),
    13 : ("3.2", "HONEYCOMB_MR2", "Honeycomb"),
    12 : ("3.1", "HONEYCOMB_MR1", "Honeycomb"),
    11 : ("3.0", "HONEYCOMB", "Honeycomb"),
    10 : ("2.3.3", "GINGERBREAD_MR1", "Gingerbread"),
    9  : ("2.3", "GINGERBREAD", "Gingerbread"),
    8  : ("2.2", "FROYO", "Froyo"),
    7  : ("2.1", "ECLAIR_MR1", "Eclair"),
    6  : ("2.0.1", "ECLAIR_0_1", "Eclair"),
    5  : ("2.0", "ECLAIR", "Eclair"),
    4  : ("1.6", "DONUT", "Donut"),
    3  : ("1.5", "CUPCAKE", "Cupcake"),
    2  : ("1.1", "BASE_1_1", "Base"),
    1  : ("1.0", "BASE", "Base")
}


def aapt_command(*args, **kwargs):
    """Execute AAPT command."""
    return helper.exe(AAPT, *args, **kwargs)


class App:
    def __init__(self, apk_file):

        #basic info
        self.host_path = apk_file
        self.app_name = ''

        self.display_name = 'Unknown'
        self.version_name = 'Unknown'
        self.version_code = 'Unknown'

        self.launchable_activity = ''

        # requirements
        self.min_sdk = '0'
        self.max_sdk = '0'
        self.target_sdk = '0'
        self.used_permissions = {}
        #self.used_libraries = {}
        #self.used_opt_libraries = {}
        self.used_implied_features = ()
        self.used_opt_features = ()
        self.used_features = ()
        self.supported_abis = ()
        self.supported_texture_compressions = ()

        self.from_file()


    def from_device(self, device, limited_init=True):
        raise NotImplementedError()
        # TODO: implement initialization from device
        dump = device.shell_command("dumpsys", "package", self.app_name,
                                    return_output=True, as_list=False)

        search_group = {
            "version_name" : "(?:versionName\\=)([!-z]*)",
            "version_code" : "(?:versionCode\\=)([!-z]*)",
            "target_sdk" : "(?:targetSdkVersion\\=)([!-z]*)",
            "device_path" : "(?:codePath\\=)([!-z]*)",
            }

        for key, value in search_group.items():
            extracted = re.search(value, dump)
            if extracted:
                self.__dict__[key] = extracted.group(1).strip()

        # not much can be read from the app while on device
        # so lets get the app to host and check it out!
        if not limited_init:
            apk_path = device.shell_command(
                "pm", "path", self.app_name, return_output=True, as_list=False)
            apk_path = re.search("(?:package\\:)(.*)", apk_path)

            if apk_path:
                self.device_path = apk_path.group().strip()
                local_path = f"./{device.filename}"
                device.adb_command("pull", self.device_path, local_path)
                self.host_path = local_path
                self.from_file()


    def from_file(self):
        """Load app data from a local apk file."""
        dump = aapt_command("dump", "badging", self.host_path,
                            return_output=True, as_list=False)

        if "error: dump failed" in dump.lower():
            unknown = "Unknown! ({Path(self.host_path).name})"
            self.app_name = unknown
            self.display_name = unknown

        search_group = {
            "app_name" : "(?:name\\=\\')([^\\']*)",
            "display_name" : "(?:^application\\:\\ label\\=\\')([^\\']*)",
            "version_name" : "(?:versionName\\=\\')([^\\']*)",
            "version_code" : "(?:versionCode\\=\\')([^\\']*)",
            "min_sdk" : "(?:^sdkVersion\\:\\')([^\\']*)",
            "target_sdk" : "(?:^targetSdkVersion\\:\\')([^\\']*)",
            "max_sdk" : "(?:^maxSdkVersion\\=\\')([^\\']*)",
            "supported_abis" : "(?:^native-code\\:\\ )(.*)",
            "launchable_activity" : "(?:launchable\\-activity\\:\\ name=\\')([^\\']*)",
            }

        findall_group = {
            "supported_texture_compressions" : "(?:supports\\-gl\\-texture\\:\\')([^\\']*)",
            "used_permissions" : "(?:uses\\-permission\\:\\ name\\=\\')([^\\']*)(?:.*max\\-sdkVersion\\=\\')?([^\\']*)",
            "used_implied_features" : "(?:uses\\-implied\\-feature\\:\\ name\\=\\')([^\\']*)(?:.*reason\\=\\')?([^\\']*)",
            "used_opt_features" : "(?:uses\\-feature\\-not\\-required\\:\\ name\\=\\')([^\\']*)",
            "used_features" : "(?:uses\\-feature\\:\\ name\\=\\')([^\\']*)",
            }

        for key, value in search_group.items():
            extracted = re.search(value, dump, re.M)
            if extracted:
                self.__dict__[key] = extracted.group(1).strip()

        for key, value in findall_group.items():
            extracted = re.findall(value, dump, re.M)
            if extracted:
                self.__dict__[key] = extracted

        if self.supported_abis:
            self.supported_abis = self.supported_abis.replace("'", "").strip().split()

        if self.used_implied_features:
            self.used_implied_features = dict(self.used_implied_features)

        if self.used_permissions:
            self.used_permissions = dict(self.used_permissions)


    def check_compatibility(self, device):
        """Check if specified device meets app's requirements.

        Apps installed on devices not supporting their ABIs or texture
        compressions will most likely crash on launch.

        If a device's Android version is below the app's minimum, the
        installation will be blocked by package manager.

        Apps may malfunction if installed on a device without features
        specified by the app. Depending on the feature, this could mean
        the app crashing or certain functionality being inaccessible by
        the user.
        """
        compatible = True
        reasons = []
        # Ensure the necessary data is available
        device.extract_data(limit_to=("os", "chipset", "gpu", "features"))

        # check if device uses a supported Android version
        device_sdk = device.info_dict["android_api_level"]
        if int(self.min_sdk):
            if int(self.min_sdk) > int(device_sdk):
                compatible = False
                reasons.append(
                    f"API level of at least {self.min_sdk} is required but "
                    f"the device uses {device_sdk}")

        if int(self.max_sdk):
            if int(device_sdk) > int(self.max_sdk):
                compatible = False
                reasons.append(
                    f"API level of at most {self.max_sdk} is allowed but "
                    f"the device uses {device_sdk}")

        # check if device uses one of supported abis
        if self.supported_abis:
            device_abis = device.info_dict["cpu_abis"]
            unique_abis = set(list(device_abis) + self.supported_abis)
            all_abis = list(device_abis) + self.supported_abis

            # if len(unique_abis) == len(all_abis), then there is
            # no overlap between device's and app's abis
            if not len(unique_abis) < len(all_abis):
                compatible = False
                reasons.append(
                    f"Device does not use supported abis ({self.supported_abis})")

        # check if device uses one of supported texture compressions
        if self.supported_texture_compressions:
            unique_textures = set(list(device.info_dict["gles_extensions"] \
                                  + self.supported_texture_compressions))
            all_textures = list(device.info_dict["gles_extensions"]) \
                           + self.supported_texture_compressions

            # just like with abis
            if not len(unique_textures) < len(all_textures):
                compatible = False
                reasons.append(
                    f"Device does not use supported texture compressions"
                    f"{self.supported_texture_compressions}")

        # check if all features are available
        for feature in self.used_features:
            if feature not in device.info_dict["device_features"]:
                compatible = False
                reasons.append(
                    f"Feature {feature} not available on device")

        return (compatible, reasons)


    def get_report(self, extended=False, indent=4):
        """Return a formatted string containing all known app info."""
        lines = []
        lines.append(f"{self.display_name}  v. {self.version_name} ({self.version_code})")
        lines.append(f"App ID: {self.app_name}")

        if not extended:
            return "\n".join(lines)

        #TODO: replace this mess with a loop
        # keep a list of strings and join them all at the end


        target_version = API_LEVEL_MATRIX[int(self.target_sdk)][0]
        target_version_name = API_LEVEL_MATRIX[int(self.target_sdk)][2]
        lines.append(
            f"Targeted Android version: {target_version} "
            f"({target_version_name} API Level {self.target_sdk})")

        lowest_version = API_LEVEL_MATRIX[int(self.min_sdk)][0]
        lowest_version_name = API_LEVEL_MATRIX[int(self.min_sdk)][2]
        lines.append(
            f"Lowest supported version: {lowest_version} "
            f"({lowest_version_name} API Level {self.min_sdk})")

        lines.append(f"Supported CPU ABIs: {', '.join(self.supported_abis)}")

        lines.append("Used texture compressions:")
        for compression in self.supported_texture_compressions:
            lines.append(f"{indent*' '}{compression}")

        lines.append("Required features:")
        for req_feature in self.used_features:
            lines.append(f"{indent*' '}{req_feature}")

        lines.append("Optional features:")
        for opt_feature in self.used_opt_features:
            lines.append(f"{indent*' '}{opt_feature}")

        used_dangerous = set(ANDROID_DANGEROUS_PERMISSIONS).intersection(self.used_permissions)

        lines.append("Required dangerous permissions:")
        for dang_permission in used_dangerous:
            lines.append(f"{indent*' '}{dang_permission}")

        lines.append("Required permissions:")
        for permission in self.used_permissions:
            if permission in used_dangerous:
                continue

            lines.append(f"{indent*' '}{permission}")

        return "\n".join(lines)


def main(arguments=None):
    parser = ArgumentParser(prog="ApkInspector")
    parser.add_argument("apk")
    parser.add_argument(
        "-v", "--version", action="version", version="%(prog)s {}".format(VERSION))

    arg = parser.parse_args(arguments)

    if not Path(arg.apk).is_file:
        print("ERROR: provided path is not a file")
        print(f"     : {arg.apk}")
        return

    args = parser.parse_args(arguments)
    print(App(args.apk).get_report(True))


if __name__ == "__main__":
    main()
