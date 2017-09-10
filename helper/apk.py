"""Module for analyzing apk packages with aapt"""
import re
import sys
from pathlib import Path

import helper as helper_

AAPT = helper_.AAPT

# last updated: 2017.07.19
# https://developer.android.com/reference/android/Manifest.permission.html
ANDROID_DANGEROUS_PERMISSIONS = """android.permission.ACCESS_COARSE_LOCATION
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
android.permission.WRITE_EXTERNAL_STORAGE""".splitlines()


def aapt_command(*args, stdout_=sys.stdout, **kwargs):
    """Execute an AAPT command, and return -- or don't -- its result."""
    try:
        return helper_.exe(AAPT, *args, **kwargs)
    except FileNotFoundError:
        stdout_.write("".join(["Helper expected AAPT to be located in '", AAPT,
                               "' but could not find it.\n"]))
        sys.exit()
    except (PermissionError, OSError):
        stdout_.write(
            " ".join(["Helper could not launch AAPT. Please make sure the",
                      "following path is correct and points to an actual AAPT",
                      "binary:", AAPT, "To fix this issue you may need to",
                      "edit or delete the helper config file, located at:",
                      helper_.CONFIG]))
        sys.exit()


class App:
    def __init__(self, apk_file):

        #basic info
        self.host_path = apk_file
        self.app_name = ''

        self.display_name = 'Unknown'
        self.version_name = 'Unknown'
        self.version_code = 'Unknown'
        self.is_game = False

        self.launchable_activity = ''

        # requirements
        self.min_sdk = '0'
        self.max_sdk = '0'
        self.target_sdk = '0'
        self.used_permissions = ()
        self.used_implied_features = ()
        self.used_not_required_features = ()
        self.used_features = ()
        self.supported_abis = ()
        self.supported_texture_compressions = ()

        self.from_file()


    def _from_device(self, device, limited_init=True):
        raise NotImplementedError()
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
            apk_path = device.shell_command("pm", "path", self.app_name,
                                            return_output=True, as_list=False)
            apk_path = re.search("(?:package\\:)(.*)", apk_path)

            if apk_path:
                self.device_path = apk_path.group().strip()
                local_path = "".join(["./", device.info("Product", "Model"),
                                      Path(self.device_path).name])
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
            "app_name" : "(?:name\\=\\')([^\\']*)",
            "display_name" : "(?:application\\:\\ label\\=\\')([^\\']*)",
            "version_name" : "(?:versionName\\=\\')([^\\']*)",
            "version_code" : "(?:versionCode\\=\\')([^\\']*)",
            "min_sdk" : "(?:sdkVersion\\:\\')([^\\']*)",
            "target_sdk" : "(?:targetSdkVersion\\:\\')([^\\']*)",
            "max_sdk" : "(?:maxSdkVersion\\=\\')([^\\']*)",
            "supported_abis" : "(?:native-code\\:\\ )(.*)",
            "is_game" : "(application\\-isGame)",
            "launchable_activity" : "(?:launchable\\-activity\\:\\ name=\\')([^\\']*)",
            }

        findall_group = {
            "supported_texture_compressions" : "(?:supports\\-gl\\-texture\\:\\')([^\\']*)",
            "used_permissions" : "(?:uses\\-permission\\:\\ name\\=\\')([^\\']*)(?:.*maxSdkVersion\\=\\')?([^\\']*)",
            "used_implied_features" : "(?:uses\\-implied\\-feature\\:\\ name\\=\\')([^\\']*)(?:.*reason\\=\\')?([^\\']*)",
            "used_not_required_features" : "(?:uses\\-feature\\-not\\-required\\:\\ name\\=\\')([^\\']*)",
            "used_features" : "(?:uses\\-feature\\:\\ name\\=\\')([^\\']*)",
            }

        for key, value in search_group.items():
            extracted = re.search(value, dump)
            if extracted:
                self.__dict__[key] = extracted.group(1).strip()

        for key, value in findall_group.items():
            extracted = re.findall(value, dump)
            if extracted:
                self.__dict__[key] = extracted

        if self.supported_abis:
            self.supported_abis = self.supported_abis.replace("'", "").strip().split()


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
        device.device_init(limit_init=("device_features",
                                       "surfaceflinger_dump", "getprop"))

        # check if device uses a supported Android version
        device_sdk = device.info("OS", "API Level")
        if int(self.min_sdk) > int(device_sdk):
            compatible = False
            reasons.append(" ".join(["API level of at least", self.min_sdk,
                                     "is required but the device has",
                                     device_sdk]))

        if int(self.max_sdk) and device_sdk > int(self.max_sdk):
            compatible = False
            reasons.append(" ".join(["API level of at most", self.max_sdk,
                                     "is allowed but the device has",
                                     device_sdk]))

        # check if device uses one of supported abis
        if self.supported_abis:
            device_abis = device._info["CPU"]["Available ABIs"]
            unique_abis = set(list(device_abis) + self.supported_abis)
            all_abis = list(device_abis) + self.supported_abis

            # if len(unique_abis) == len(all_abis), then there is
            # no overlap between device's and app's abis
            if not len(unique_abis) < len(all_abis):
                compatible = False
                reasons.append(
                    " ".join(["Device does not use supported abis",
                              str(self.supported_abis)]))

        # check if device uses one of supported texture compressions
        if self.supported_texture_compressions:
            unique_textures = set(list(device.gles_extensions) \
                                  + self.supported_texture_compressions)
            all_textures = list(device.gles_extensions) \
                           + self.supported_texture_compressions

            # just like with abis
            if not len(unique_textures) < len(all_textures):
                compatible = False
                reasons.append(
                    " ".join(["Device does not use supported texture",
                              "compressions",
                              str(self.supported_texture_compressions)]))

        # check if all features are available
        for feature in self.used_features:
            if feature not in device.device_features:
                compatible = False
                reasons.append(" ".join(["Feature", feature,
                                         "not available on device"]))

        for feature, implied_reason in self.used_implied_features:
            if feature not in device.device_features:
                compatible = False
                reasons.append(" ".join(["Feature", feature,
                                         "not available on device"]))

        return (compatible, reasons)
