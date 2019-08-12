"""
"""
from pathlib import Path
from . import CWD


CONFIG_VALS = {
    "adb":"",
    "aapt":"",
}
# TODO: replace custom config files (helper, gles textures and cleaner) with cfg module
# TODO: add an interface for editing various configs

CONFIG = Path(CWD, "helper_config")
DEFAULT_ADB = Path(CWD, "bin", "adb")
DEFAULT_AAPT = Path(CWD, "bin", "aapt")
CLEANER_CONFIG = Path(CWD, "cleaner_config")
