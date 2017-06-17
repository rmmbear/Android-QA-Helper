import random
import string
from pathlib import Path

import helper.main as main_
import helper.device as device_


def get_nonexistent_path():
    """Generate a path that does not exist"""
    chars = string.ascii_letters + string.digits
    base = Path()
    while True:
        nonexistent_path = base / "".join(
            [chars[random.randrange(0, len(chars)-1)] for i in range(16)])
        if not nonexistent_path.exists():
            return str(nonexistent_path.resolve())


def dump_devices(device, directory="."):
    """Function for dumping device information used in device initiation.
    Dumped files can be used with TestDeviceInit.test_full().
    """
    Path(directory).mkdir(exist_ok=True)

    device_id = "".join([device.info("Product", "Manufacturer"), "_",
                         device.info("Product", "Model")])
    device_dir = Path(directory, (device_id + "_DUMP").replace(" ", "_"))
    device_dir.mkdir(exist_ok=True)
    print()
    print("Dumping", device_id)

    for info_source in device_.INFO_EXTRACTION_CONFIG:
        try:
            args = info_source[0]
        except IndexError:
            args = ()

        filename = info_source[-1]

        output = device.shell_command(*args, return_output=True, as_list=False)

        with Path(device_dir, filename).open(mode="w", encoding="utf-8") as dump_file:
            dump_file.write(output)

    print("Device dumped to", str(device_dir.resolve()))
