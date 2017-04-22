import random
import string
from pathlib import Path

import helper as helper_
import helper.main as main_
import helper.device as device_

FULL_DEVICE_CONFIG = helper_.BASE + "/tests/full_config"
DEVICE_CONFIG = {
    "ls /system/bin"                        :"available_commands",
    "cat /proc/meminfo"                     :"meminfo",
    "wm size"                               :"screen_size",
    "wm density"                            :"screen_density",
    "getprop"                               :"getprop",
    "cat /sys/devices/system/cpu/cpu0/cpufreq/cpuinfo_max_freq" :"cpu_freq",
    "cat /proc/cpuinfo"                     :"cpuinfo",
    "cat /sys/devices/system/cpu/present"   :"cpu_cores",
    "dumpsys SurfaceFlinger"                :"surfaceflinger_dump",
    "printenv"                              :"shell_environment"
    }


def get_nonexistent_path():
    """Generate a path that does not exist"""
    chars = string.ascii_letters + string.digits
    base = Path()
    while True:
        nonexistent_path = base / "".join(
            [chars[random.randrange(0, len(chars)-1)] for i in range(16)])
        if not nonexistent_path.exists():
            return str(nonexistent_path.resolve())


def dump_devices(directory):
    """Function for dumping device information used in device initiation.
    Dumped files can be used with TestDeviceInit.test_full().
    """
    print("Before continuing, please remember that ALL dumped files may contain",
          "sensitive data. Please pay special attention to the 'getprop' file",
          "which almost certainly will contain data you do not want people to",
          "see.",)
    input("Press enter to continue")

    Path(directory).mkdir(exist_ok=True)

    for device in device_.get_devices():
        device_id = device.info["Product"]["Model"] + "_" + device.info["Product"]["Manufacturer"]
        device_dir = Path(directory, device_id + "_DUMP")
        device_dir.mkdir(exist_ok=True)
        print()
        print("Dumping", device_id)

        for command, filename in DEVICE_CONFIG.items():
            output = device.shell_command(command, return_output=True,
                                          as_list=False)

            with Path(device_dir, filename).open(mode="w", encoding="utf-8") as dump_file:
                dump_file.write(output)

        print("Device dumped to", str(device_dir.resolve()))
