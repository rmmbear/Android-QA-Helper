"""

Other modules expect that all extraction functions' names start with
'extract_'.
"""
import re
import string
import logging
from collections import OrderedDict

import helper

LOGGER = logging.getLogger(__name__)

SIZE_PREFIXES = {x:1024**y for y, x in enumerate(" KMGTP")}

# source: https://www.khronos.org/registry/OpenGL/index_es.php
# last updated: 2018.01.06
TEXTURE_COMPRESSION_IDS = {
    "GL_AMD_compressed_ATC_texture" : "ATC",
    "GL_ATI_compressed_texture_atitc" : "ATC",
    "GL_ATI_texture_compression_atitc" : "ATC",
    "GL_OES_compressed_ETC1_RGB8_texture" : "ETC1",
    "GL_OES_compressed_ETC2_RGB8_texture" : "ETC2",
    "GL_EXT_texture_compression_s3tc_srgb" : "S3TC (DXTC) - sRGB",
    "GL_EXT_texture_compression_s3tc" : "S3TC (DXTC)",
    "GL_EXT_texture_compression_dxt1" : "DXT1",
    "GL_IMG_texture_compression_pvrtc" : "PVRTC",
    "GL_IMG_texture_compression_pvrtc2" : "PVRTC2",
    "GL_AMD_compressed_3DC_texture" : "3DC",
    "GL_EXT_texture_compression_latc" : "LATC",
    "GL_NV_texture_compression_latc" : "LATC",
    "GL_OES_texture_compression_astc" : "ASTC",
    "GL_KHR_texture_compression_astc_hdr" : "ASTC HDR",
    "GL_KHR_texture_compression_astc_ldr" : "ASTC LDR",
    "GL_KHR_texture_compression_astc_sliced_3d" : "ASTC - sliced 3D",
    "GL_EXT_texture_compression_rgtc" : "RGTC",
    "GL_EXT_texture_compression_bptc" : "BPTC",
}


#shell script for finding executables in PATH
SH_PATH_EXE = """
for dir in ${PATH//:/ }; do
    for file in $dir/*; do
        if [ -x "$file" ]; then
            echo ${file##*/};
        fi;
    done;
done;
""".strip().replace("\n", "")

# shell script for extracting data from each logical cpu
SH_CPU_DATA = """
STARTING_PATH=/sys/devices/system/cpu;
NUM=0;
while true; do
    dir=${STARTING_PATH}/cpu${NUM};
    if [ ! -d "$dir" ]; then
        break;
    else
        echo /// cpu${NUM};
        echo ---- cpufreq ----;
        for file in $dir/cpufreq/*; do
            if [ ! -r "$file" ]; then
                continue;
            fi;
            if [ ! -f "$file" ]; then
                continue;
            fi;

            echo ${file##*/} : $(cat $file);
        done;
        echo ---- topology ----;
        for file in $dir/topology/*; do
            if [ ! -r "$file" ]; then
                continue;
            fi;
            if [ ! -f "$file" ]; then
                continue;
            fi;

            echo ${file##*/} : $(cat $file);
        done;
    fi;
    ((NUM++));
done;
""".strip()


INFO_SOURCES = {
    "getprop" : ("getprop",),
    "iserial" : ("cat", "/sys/class/android_usb/android0/iSerial"),
    "cpuinfo" : ("cat", "/proc/cpuinfo"),
    "max_cpu_freq" : ("cat", "/sys/devices/system/cpu/cpu0/cpufreq/cpuinfo_max_freq"),
    "possible_cpu_cores" : ("cat", "/sys/devices/system/cpu/possible"),
    "surfaceflinger_dump" : ("dumpsys", "SurfaceFlinger"),
    "display_dump" : ("dumpsys", "display"),
    "meminfo" : ("cat", "/proc/meminfo"),
    "kernel_version" : ("cat", "/proc/version"),
    "shell_environment" : ("printenv",),
    "available_commands" : (SH_PATH_EXE,),
    "cpu_data" : (SH_CPU_DATA,),
    "device_features" : ("pm", "list", "features"),
    "device_libraries" : ("pm", "list", "libraries"),
    "system_apps" : ("pm", "list", "packages", "-s"),
    "third-party_apps" : ("pm", "list", "packages", "-3"),
    "screen_size" : ("wm", "size"),
    "screen_density" : ("wm", "density"),
    "internal_sd_space" : ("df", "\"$EXTERNAL_STORAGE\""),
    "external_sd_space" : ("df", "\"$SECONDARY_STORAGE\""),
    #debug info included in debug dump
    "build.prop" : ("cat", "/system/build.prop"),
    "disk_space" : ("df",),
    #debug info included only in full debug dump
    "debug_dumpsys_full" : ("dumpsys",),
    "debug_directory_map" : ("ls", "-alR"),
    "debug_permission_list" : ("pm", "list", "permissions"),
    "debug_device_instrumentation" : ("pm", "list", "instrumentation"),
    }

NOTABLE_FEATURES = [
    ("Bluetooth", "feature:android.hardware.bluetooth"),
    ("Bluetooth Low-Energy", "feature:android.hardware.bluetooth_le"),
    ("IR Sensor", "feature:android.hardware.consumerir"),
    ("Fingerprint Scanner", "feature:android.hardware.fingerprint"),
    ("NFC", "feature:android.hardware.nfc"),
    ("CDMA Telephony", "feature:android.hardware.telephony.cdma"),
    ("GSM Telephony", "feature:android.hardware.telephony.gsm"),
    ("VR Headtracking", "feature:android.hardware.vr.headtracking"),
    ("VR Mode", "feature:android.software.vr.mode"),
    ("High-Performance VR Mode", "feature:android.hardware.vr.high_performance"),
    ("WiFi-Aware", "feature:android.hardware.wifi.aware"),
    ("WiFi", "feature:android.hardware.wifi"),
]

# information surfaced to the user in device dump
SURFACED_VERBOSE = OrderedDict()
SURFACED_VERBOSE["Identity"] = (
    ("Model", "device_model"),
    ("Manufacturer", "device_manufacturer"),
    ("Device", "device_device"),
    ("Name", "device_name"),
    ("Brand", "device_brand"),
    ("Serial Number", "device_serial_number"),
)
SURFACED_VERBOSE["System"] = (
    ("API Level", "android_api_level"),
    ("Android Version", "android_version"),
    ("Aftermarket Firmware", "aftermarket_firmware"),
    ("Aftermarket Firmware Version", "aftermarket_firmware_version"),
    ("Build ID", "android_build_id"),
    ("Build Fingerprint", "android_build_fingerprint"),
    ("Kernel Version", "kernel_version"),
)
SURFACED_VERBOSE["Chipset"] = (
    ("Board", "board"),
    ("RAM", "ram_capacity"),
    ("GPU Vendor", "gpu_vendor"),
    ("GPU Model", "gpu_model"),
    ("OpenGL ES Version", "gles_version"),
    ("Known Texture Compression Types", "gles_texture_compressions"),
    ("CPU Summary", "cpu_summary"),
    ("CPU Architecture", "cpu_architecture"),
    ("CPU Clock Range", "cpu_clock_range"),
    ("Available ABIs", "cpu_abis"),
    ("CPU Features", "cpu_features"),
    # Some chipsets include multiple CPUs that device switches between depending on power needed for given task
    # in such cases, following entries will be added for each cpu
    # ("CPU# Core Count", "cpu#_core_count"),
    # ("CPU# Clock Range", "cpu#_clock_range"),
    # ("CPU# Clock Jump intervals", "cpu#_clock_intervals"),
)
SURFACED_VERBOSE["Display"] = (
    ("Resolution", "display_resolution"),
    ("Density", "display_density"),
    ("X-DPI", "display_x-dpi"),
    ("Y-DPI", "display_y-dpi"),
    #("Size", "display_physical_size"),
)
SURFACED_VERBOSE["Storage"] = (
    ("Internal Storage Path", "internal_sd_path"),
    ("Internal Storage Space Total", "internal_sd_capacity"),
    ("Internal Storage Space Available", "internal_sd_free"),
    ("SD Card Path", "external_sd_path"),
    ("SD Card Space Total", "external_sd_capacity"),
    ("SD Card Space Available", "external_sd_free"),
)
SURFACED_VERBOSE["Notable Features"] = ((None, "device_notable_features"),)
SURFACED_VERBOSE["Device Features"] = ((None, "device_features"),)
SURFACED_VERBOSE["System Apps"] = ((None, "system_apps"),)
SURFACED_VERBOSE["Third-Party Apps"] = ((None, "third-party_apps"),)
SURFACED_VERBOSE["Shell Commands"] = ((None, "shell_commands"),)
SURFACED_VERBOSE["GLES Extensions"] = ((None, "gles_extensions"),)

INFO_KEYS = [
    "aftermarket_firmware",
    "aftermarket_firmware_version",
    "android_api_level",
    "android_build_fingerprint",
    "android_build_id",
    "android_version",
    "anr_trace_path",
    "board",
    "cpu_abis",
    "cpu_architecture",
    "cpu_clock_range",
    "cpu_features",
    "cpu_summary",
    "cpu0_clock_intervals",
    "cpu0_clock_range",
    "cpu0_core_count",
    "cpu0_max_frequency",
    "cpu0_min_frequency",
    #"cpu#_clock_intervals",
    #"cpu#_clock_range",
    #"cpu#_core_count",
    #"cpu#_max_frequency",
    #"cpu#_min_frequency",
    "device_brand",
    "device_device",
    "device_features",
    "device_manufacturer",
    "device_model",
    "device_name",
    "device_notable_features",
    "device_serial_number",
    "display_density",
    #"display_physical_size",
    "display_resolution",
    "display_x-dpi",
    "display_y-dpi",
    "external_sd_capacity",
    "external_sd_free",
    "external_sd_path",
    "gles_extensions",
    "gles_texture_compressions",
    "gles_version",
    "gpu_model",
    "gpu_vendor",
    "internal_sd_capacity",
    "internal_sd_free",
    "internal_sd_path",
    "kernel_version",
    "ram_capacity",
    "shell_commands",
    "system_apps",
    "third-party_apps",
    #"gpu_frequency",
    #"gpu_ram",
    #"ram_type",
]

def abi_to_arch(abi):
    """"""
    if abi not in helper.ABI_TO_ARCH:
        return f"Unknown ({abi})"

    return helper.ABI_TO_ARCH[abi]


def run_extraction_command(device, source_name, use_cache=True, keep_cache=True):
    """Run extraction command and return its output.

    If there is a value stored under the corresponding source name in
    device's _init_cache, that value is then returned instead.
    """
    from helper.device import Device
    try:
        if not use_cache:
            raise KeyError

        return device._init_cache[source_name]
    except KeyError:
        if not isinstance(device, Device):
            return ""

        out = device.shell_command(
            *INFO_SOURCES[source_name], return_output=True, as_list=False)
        if keep_cache:
            device._init_cache[source_name] = out
        return out


def bytes_to_human(byte_size: int) -> str:
    """Convert bytes to human readable size.
    1KB = 1024B
    """
    for power, letter in enumerate(" KMGTPEZY"):
        if byte_size < 1024**(power+1):
            break
    return f"{byte_size/1024**power:.2f}{letter.strip()}B"


def df_parser(df_output: str) -> list:
    """For some infuriating reason, some vendors opt to include a
    version of df that does not accept any options, so we need to
    manually detect size formatting used in the output.
    May they burn in hell forever.

    Return list of four-element tuples. All sizes are in bytes,
    tuple[0] = file system
    tuple[1] = total space
    tuple[2] = used space
    tuple[3] = free space
    """
    #TODO: do a second pass on this function
    df_output = [x.split() for x in df_output.splitlines()]
    index_row = [x.lower() for x in df_output.pop(0)]

    string_to_size = {
        "1k-blocks":1024,
        "1024-blocks":1024,
        "512-blocks":512,
    }
    known_size_multiplier = 0
    for name, size in string_to_size.items():
        if name in index_row:
            known_size_multiplier = size
    # assume human-readable values if header does not reveal block size

    total_column, used_column, free_column = None, None, None
    for index, column_name in enumerate(index_row):
        column_name = column_name.lower()

        if column_name in ["1k-blocks", "512-blocks", "1024-blocks", "size"]:
            total_column = index
        if column_name in ["used", "%used"]:
            used_column = index
        if column_name in ["free", "available", "avail"]:
            free_column = index

    # check for missing columns
    if sum((int(bool(x)) for x in (total_column, used_column, free_column))) < 3:
        LOGGER.error("Could not find indices of all columns")
        LOGGER.error("size: %s, used: %s, free: %s", total_column, used_column, free_column)
        LOGGER.error("Index row is: %s", index_row)

    re_search = re.compile("([0-9.]+)([%A-z]*)")
    lines = []
    accepted_chars = string.ascii_lowercase + string.digits + ",.%"
    accepted_chars = set(accepted_chars)
    for row in df_output:
        if not row:
            continue
        #TODO: improve error-checking
        if "denied" in row:
            lines.append((row[0], -1, -1, -1))
            continue

        if total_column:
            total_val = row[total_column].lower()
            # if returns non-empty set, the string contained invalid characters
            if set(total_val) - accepted_chars:
                total_val = ""
        if used_column:
            used_val = row[used_column].lower()
            if set(used_val) - accepted_chars:
                used_val = ""
        if free_column:
            free_val = row[free_column].lower()
            if set(free_val) - accepted_chars:
                free_val = ""

        # convert values to bytes
        #TODO: and third, and fourth pass on this
        # this if-else soup is somehow easier to understand than my previous solution
        if total_val:
            if known_size_multiplier:
                total_val = float(total_val)* known_size_multiplier
            else:
                total_val, total_unit = re_search.search(row[total_column]).groups()
                if total_unit:
                    total_val = float(total_val) * SIZE_PREFIXES[total_unit.upper()]
        else:
            total_val = -1

        if used_val:
            #TODO:subtract available from total instead of calculating from percentages
            if "%" in used_val:
                used_val = re_search.search(used_val).group(1)
                used_val = float(used_val) * total_val / 100
            elif known_size_multiplier:
                used_val = float(used_val) * known_size_multiplier
            else:
                used_val, used_unit = re_search.search(used_val).groups()
                if used_unit:
                    used_val = float(used_val) * SIZE_PREFIXES[used_unit.upper()]
        else:
            used_val = -1

        if free_val:
            if known_size_multiplier:
                free_val = float(free_val) * known_size_multiplier
            else:
                free_val, free_unit = re_search.search(free_val).groups()
                if free_unit:
                    free_val = float(free_val) * SIZE_PREFIXES[free_unit.upper()]
        else:
            free_val = -1

        lines.append((row[0], int(total_val), int(used_val), int(free_val)))

    return lines


def extract_identity(device):
    """
    """
    #serial = run_extraction_command(device, "iserial")
    propnames = OrderedDict([
        # OS
        ("[ro.build.version.release]", "android_version"),
        ("[ro.build.version.sdk]", "android_api_level"),
        ("[ro.build.id]", "android_build_id"),
        ("[ro.build.fingerprint]", "android_build_fingerprint"),
        # AFTERMARKET OS
        # only one of these will be available, if any at all
        ("[ro.build.version.fireos]", "aftermarket_firmware"),
        ("[ro.miui.ui.version.name]", "aftermarket_firmware"),
        ("[ro.oxygen.version]", "aftermarket_firmware"),
        ("[ro.build.version.opporom]", "aftermarket_firmware"),
        ("[ro.cm.version]", "aftermarket_firmware"),
        ("[ro.lineage.version]", "aftermarket_firmware"),
        ("[ro.aokp.version]", "aftermarket_firmware"),
        ("[ro.pa.version]", "aftermarket_firmware"),
        ("[ro.omni.version]", "aftermarket_firmware"),
        ("[ro.rr.version]", "aftermarket_firmware"),
        ("[ro.modversion]", "aftermarket_firmware_version"),
        # AliOS, LeWaOS, Baidu Yi, CopperheadOS
        # IDENTITY
        # Sony devices specify human-readable model name in prop key [ro.semc.product.name]
        ("[ro.boot.serialno]", "device_serial_number"),
        ("[ro.product.model]", "device_model"),
        ("[ro.product.manufacturer]", "device_manufacturer"),
        ("[ro.product.device]", "device_device"),
        ("[ro.product.name]", "device_name"),
        ("[ro.product.brand]", "device_brand"),
        # CPU
        ("[ro.product.cpu.abi]", "abi1"),
        ("[ro.product.cpu.abi2]", "abi2"),
        ("[ro.product.cpu.abilist]", "abilist"),
        ("[ro.board.platform]", "board"),
        # PATHS
        ("[dalvik.vm.stack-trace-file]", "anr_trace_path"),
        ("[internal_sd_path]", "internal_sd_path"),
        ("[external_sd_path]", "external_sd_path"),
        # OTHER
        ("[ro.boot.hardware.ddr]", "ram_type"),
        ("[ro.sf.lcd_density]", "display_density"),
    ])

    getprop = run_extraction_command(device, "getprop").splitlines()
    continued_value = list()
    multiline_prop = False
    for line in getprop:
        if not line:
            continue

        if multiline_prop:
            # prop name is kept from last loop
            prop_value += line.strip()
        else:
            prop_name, prop_value = line.split(": ", maxsplit=1)

        if prop_value[-1] != "]":
            multiline_prop = True
            continue

        multiline_prop = False

        prop_value = prop_value.strip("\n\r []")
        if not prop_value:
            continue
        try:
            destination = propnames[prop_name]
        except KeyError:
            continue

        device.info_dict[destination] = prop_value.strip()

    if device.info_dict["aftermarket_firmware"] is None:
        if device.info_dict["aftermarket_firmware_version"] is not None:
            device.info_dict["aftermarket_firmware"] = "Unknown OS"
        else:
            device.info_dict["aftermarket_firmware"] = "-none-"
            device.info_dict["aftermarket_firmware_version"] = "-none-"

    all_abis = []
    for abi in ["abi1", "abi2", "abilist"]:
        if abi in device.info_dict:
            all_abis.extend([x.strip() for x in device.info_dict[abi].split(",")])

    cpu_arch = abi_to_arch(all_abis[0])
    device.info_dict["cpu_architecture"] = cpu_arch

    all_abis = set(all_abis) # removes duplicates
    device.info_dict["cpu_abis"] = list(all_abis)

    kernel_version = run_extraction_command(device, "kernel_version").strip()
    device.info_dict["kernel_version"] = kernel_version


def extract_chipset(device):
    """"""
    meminfo = run_extraction_command(device, "meminfo")
    ram = re.search("(?:MemTotal\\:\\s*)([^A-z\\ ]*)", meminfo)
    if ram:
        device.info_dict["ram_capacity"] = ram.group(1).strip()

    cpuinfo = run_extraction_command(device, "cpuinfo")
    for re_ in ("(?:Hardware\\s*?\\:)([^\\n\\r]*)",
                "(?:model\\ name\\s*?\\:)([^\\n\\r]*)",
                #"(?:Processor\\s*?\\:)([^\\n\\r]*)",
               ):
        board = re.search(re_, cpuinfo)
        if board:
            board = board.group(1).strip()
            device.info_dict["board"] = board
            break

    cpu_features = re.search("(?:Features\\s*?\\:)([^\\n\\r]*)", cpuinfo)
    if cpu_features:
        cpu_features = [x.strip() for x in cpu_features.group(1).split()]

    device.info_dict["cpu_features"] = cpu_features


def extract_cpu(device):
    """"""
    cpu_dict = {}
    phys_cpu_dict = {}
    max_frequency = 0
    min_frequency = 99999999999


    shell_out = run_extraction_command(device, "cpu_data")
    if not shell_out:
        return

    shell_out = shell_out.split("/// cpu")[1::]

    for cpu in shell_out:
        cpu = cpu.strip().splitlines()
        cpu_id = int(cpu[0].strip())
        cpu_dict[cpu_id] = {}

        for line in cpu[1::]:
            if line.startswith("----"):
                continue

            line = line.strip().split(" : ", maxsplit=1)
            if len(line) != 2:
                if len(line) == 1 and not line[0]:
                    #skip empty lines
                    continue

                LOGGER.warning("Unexpected output found while extracting cpu data: %s", str([line]))
                # above is most likely happening when cores are put to sleep - those files then become unavailable
                # first core should always be awake
                #TODO: Ivestigate whether similar can happen when cpus are suddenly switched in multi-cpu chipset
                # it most likely does
                #TODO: which probably means that info from only one cpu can be scanned at a time
                # grumble grumble

                # update: 2018.09.19 - the answer is "depends", need more compat data
                continue
            cpu_dict[cpu_id][line[0]] = line[1]

    current_id = 0
    phys_id = 0
    while True:
        try:
            cpu_dict[current_id]
        except KeyError:
            break
        current_cpu_dict = cpu_dict[current_id]

        try:
            current_cpu_dict['cpuinfo_max_freq']
            current_cpu_dict['cpuinfo_min_freq']
            current_cpu_dict['scaling_available_frequencies']
        except KeyError:
            current_cpu_dict = {}

        if not current_cpu_dict:
            count = 0
            broken_name = "_unknown{}"

            n_broken_name = broken_name.format(count)
            while n_broken_name in phys_cpu_dict:
                count += 1
                n_broken_name = broken_name.format(count)

            broken_name = n_broken_name

            phys_cpu_dict[broken_name] = {
                'max_frequency':0,
                'min_frequency':0,
                'clock_range':"Unknown",
                'clock_intervals':"Unknown",
                'cores':"Unknown",
            }

            unknown_cores = 1
            while True:
                try:
                    cpu_dict[current_id + unknown_cores]
                except KeyError:
                    break

                next_dict = cpu_dict[current_id + unknown_cores]
                try:
                    current_cpu_dict['cpuinfo_max_freq']
                    current_cpu_dict['cpuinfo_min_freq']
                    current_cpu_dict['scaling_available_frequencies']
                    if next_dict:
                        break
                except KeyError:
                    pass

                unknown_cores += 1


            phys_cpu_dict[broken_name]['core_count'] = unknown_cores
            current_id += unknown_cores
            continue

        phys_id = cpu_dict[current_id]['physical_package_id']

        phys_cpu_dict[phys_id] = {}
        phys_cpu_dict[phys_id]['max_frequency'] = int(current_cpu_dict['cpuinfo_max_freq'].strip()) / (1000000)
        phys_cpu_dict[phys_id]['min_frequency'] = int(current_cpu_dict['cpuinfo_min_freq'].strip()) / (1000000)
        phys_cpu_dict[phys_id]['clock_range'] = " - ".join([str(int(current_cpu_dict['cpuinfo_min_freq']) / (1000000)), str(int(current_cpu_dict['cpuinfo_max_freq']) / (1000000))]) + " GHz"
        phys_cpu_dict[phys_id]['clock_intervals'] = [int(x.strip()) for x in current_cpu_dict['scaling_available_frequencies'].strip().split(" ")]
        x, y = current_cpu_dict['core_siblings_list'].strip().split("-", maxsplit=1)
        phys_cpu_dict[phys_id]['cores'] = [z for z in range(int(x), int(y)+1)]
        phys_cpu_dict[phys_id]['core_count'] = len(phys_cpu_dict[phys_id]['cores'])

        current_id = phys_cpu_dict[phys_id]['cores'][-1] + 1

    device.info_dict["cpu_summary"] = []
    for cpu_id, cpu in phys_cpu_dict.items():
        device.info_dict[f"cpu{cpu_id}_max_frequency"] = cpu["max_frequency"]
        if cpu["max_frequency"] > max_frequency:
            max_frequency = cpu["max_frequency"]
        device.info_dict[f"cpu{cpu_id}_min_frequency"] = cpu["min_frequency"]
        if cpu["min_frequency"] < min_frequency:
            min_frequency = cpu["min_frequency"]

        device.info_dict[f"cpu{cpu_id}_clock_intervals"] = cpu["clock_intervals"]
        device.info_dict[f"cpu{cpu_id}_core_count"] = cpu["core_count"]

        device.info_dict["cpu_summary"].append(
            "{}-core {} GHz".format(cpu["core_count"], cpu["max_frequency"]))

    device.info_dict["cpu_clock_range"] = " - ".join(
        [str(min_frequency), str(max_frequency)]) + " GHz"


    #"cpu_clock_range",
    #"cpu_max_frequency",
    #"cpu_min_frequency",
    #"cpu_summary",

    #"cpu#_clock_intervals",
    #"cpu#_clock_range",
    #"cpu#_core_count",


# example cpu_dict entry
"""
'affected_cpus': '0 1 2 3'
'cpuinfo_max_freq': '1300000'
'cpuinfo_min_freq': '598000'
'cpuinfo_transition_latency': '1000'
'related_cpus': '0 1 2 3'
'scaling_available_frequencies': '1300000 1196000 1040000 747500 598000'
'scaling_available_governors': 'userspace powersave hotplug performance'
'scaling_cur_freq': '598000'
'scaling_driver': 'mt-cpufreq'
'scaling_governor': 'hotplug'
'scaling_min_freq': '598000'
'scaling_setspeed': '<unsupported>'
'core_id': '0'
'core_siblings': 'f'
'core_siblings_list': '0-3'
'physical_package_id': '0'
'thread_siblings': '1'
'thread_siblings_list': '0'
"""


def extract_gpu(device):
    """"""
    gpu_vendor, gpu_model, gles_version = [None for x in range(3)]
    dumpsys = run_extraction_command(device, "surfaceflinger_dump")
    gpu_line = re.search("(?:GLES\\:)([^\n\r]*)", dumpsys)

    if gpu_line:
        gpu_vendor, gpu_model, gles_version = gpu_line.group(1).strip().split(",", 2)
        device.info_dict["gpu_vendor"] = gpu_vendor.strip()
        device.info_dict["gpu_model"] = gpu_model.strip()
        device.info_dict["gles_version"] = gles_version.strip()

    gles_extensions = re.search("(?:GLES\\:[^\\r\\n]*)(?:\\s*)([^\\r\\n]*)", dumpsys)

    if gles_extensions:
        gles_extensions = gles_extensions.group(1).strip().split(" ")

        device.info_dict["gles_texture_compressions"] = []
        device.info_dict["gles_extensions"] = gles_extensions
        for extension in gles_extensions:
            try:
                device.info_dict["gles_texture_compressions"].append(
                    TEXTURE_COMPRESSION_IDS[extension])
            except KeyError:
                # extension is not a known type of texture compression, continue
                continue


def extract_display(device):
    """"""
    dumpsys = run_extraction_command(device, "surfaceflinger_dump")
    x_dpi = re.search("(?:x-dpi\\s*\\:\\s*)([^\\n]*)", dumpsys)
    y_dpi = re.search("(?:y-dpi\\s*\\:\\s*)([^\\n]*)", dumpsys)
    resolution = re.search("(?:Display\\[0\\] :)([^,]*)", dumpsys)

    if not resolution:
        wm_output = run_extraction_command(device, "screen_size")
        resolution = re.search("(?:Physical size:)([^\\n]*)", wm_output)

    if device.info_dict["display_density"] is None:
        wm_output = run_extraction_command(device, "screen_density")
        density = re.search("(?:Physical\\ density\\:)([0-9A-z]*)", wm_output)
        if density:
            density = density.group(1)
            device.info_dict["display_density"] = density

    if resolution:
        resolution = resolution.group(1).strip()
    if x_dpi:
        x_dpi = x_dpi.group(1).strip()
    if y_dpi:
        y_dpi = y_dpi.group(1).strip()


    device.info_dict["display_resolution"] = resolution
    device.info_dict["display_x-dpi"] = x_dpi
    device.info_dict["display_y-dpi"] = y_dpi


def extract_features(device):
    """"""
    feature_list = run_extraction_command(device, "device_features")
    device.info_dict["device_notable_features"] = []

    for feature_name, feature_string in NOTABLE_FEATURES:
        if feature_string in feature_list:
            device.info_dict["device_notable_features"].append(feature_name)

    all_features = re.findall("(?:^feature:)([a-zA-Z0-9\\_\\.\\=]*)", feature_list, re.M)
    device.info_dict["device_features"] = all_features


def extract_storage(device):
    """Extract list of various paths."""
    internal_sd = None
    external_sd = None
    shell_env = run_extraction_command(device, "shell_environment")

    try:
        internal_sd = re.search("(?:EXTERNAL_STORAGE=)([^\\s]*)", shell_env).group(1)
    except AttributeError:
        pass
    try:
        external_sd = re.search("(?:SECONDARY_STORAGE=)([^\\s]*)", shell_env).group(1)
    except AttributeError:
        pass

    # TODO: Some devices specify only the directory containing the trace file and not the file itself
    # Check whether there is any difference in traces on those devices

    if not device.is_dir(internal_sd):
        guesses = ["/mnt/sdcard", "/storage/emulated/legacy", "/mnt/shell/emulated/0"]

        for guess in guesses:
            if device.is_dir(guess):
                internal_sd = guess
                break

    device.info_dict["internal_sd_path"] = internal_sd
    device.info_dict["external_sd_path"] = external_sd

    external_sd_space = run_extraction_command(device, "external_sd_space")
    if "no such file or directory" in external_sd_space.lower() or \
       "permission denied" in external_sd_space:
        filesystem, size, used, free = ["Unavailable" for x in range(4)]
    else:
        filesystem, size, used, free = df_parser(external_sd_space.strip())[0]

    device.info_dict["external_sd_capacity"] = size
    device.info_dict["external_sd_free"] = free

    internal_sd_space = run_extraction_command(device, "internal_sd_space")
    if "no such file or directory" in internal_sd_space.lower() or \
       "permission denied" in internal_sd_space:
        filesystem, size, used, free = ["Unavailable" for x in range(4)]
    else:
        filesystem, size, used, free = df_parser(internal_sd_space.strip())[0]

    device.info_dict["internal_sd_capacity"] = size
    device.info_dict["internal_sd_free"] = free


def extract_available_commands(device):
    """Extract a list of available shell commands."""
    device.info_dict["shell_commands"] = []

    commands = run_extraction_command(device, "available_commands").splitlines()
    device.info_dict["shell_commands"] = [x for x in commands if x]


def extract_installed_packages(device):
    """Extract a list of installed system and third-party packages."""
    extract_system_packages(device)
    extract_thirdparty_packages(device)


def extract_system_packages(device):
    """"""
    if device.info_dict["system_apps"]:
        # system apps can generally only be disabled, downgraded or updated
        # and do not need to be re-checked
        return

    device.info_dict["system_apps"] = []

    for package in run_extraction_command(device, "system_apps").splitlines():
        if not package:
            continue
        try:
            app = package.split("package:", maxsplit=1)[1]
        except IndexError:
            LOGGER.warning("Could not split system package line: %s", package)
            continue

        device.info_dict["system_apps"].append(app.strip())


def extract_thirdparty_packages(device):
    """"""
    device.info_dict["third-party_apps"] = []
    count = 0
    for line in run_extraction_command(device, "third-party_apps", use_cache=False, keep_cache=False).splitlines():
        if not line:
            continue
        try:
            app = line.split("package:", maxsplit=1)[1]
        except IndexError:
            LOGGER.warning("Could not split thirdparty package line: %s", line)
            continue

        device.info_dict["third-party_apps"].append(app.strip())
        count += 1

    if count == 0:
        device.info_dict["third-party_apps"] = "-none-"
