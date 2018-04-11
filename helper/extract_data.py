"""

Other modules expect that all extraction functions' names start with 'extract_'
"""
import re
import helper

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
    "available_commands" : ("ls", "/system/bin"),
    "device_features" : ("pm", "list", "features"),
    "system_apps" : ("pm", "list", "packages", "-s"),
    "third-party_apps" : ("pm", "list", "packages", "-3"),
    "screen_size" : ("wm", "size"),
    "screen_density" : ("wm", "density"),
    "build.prop" : ("cat", "/system/build.prop"),        #debug
    "dumpsys_full" : ("dumpsys",),                       #debug
    }

# list of features that one might be looking for in a device
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
]

# information surfaced to the user in detailed scan
# (short scan shows only serial number, model, manufacturer and device status)
SURFACED_BRIEF = [
    # it follows the following structure:
    # [section name, [(name, corresponding key from INFO_KEYS), ...]]
    # if putting values in sections does not make much sense,
    # the (name, INFO_KEY) tuple can be entered into the config directly
    # without its own section
    ["Identity",
     [("Model", "device_model"),
      ("Manufacturer", "device_manufacturer"),
      ("Device", "device_device"),
     ]
    ],
    ["System",
     [("API Level", "android_api_level"),
      ("Android Version", "android_version"),
      ("Aftermarket Firmware", "aftermarket_firmware"),
     ]
    ],
    ["Chipset",
     [("Board", "board"),
      ("RAM", "ram_capacity"),
      ("CPU Architecture", "cpu_architecture"),
      ("Cores", "cpu_core_count"),
      ("Base Clock Frequency", "cpu_base_frequency"),
      ("GPU Vendor", "gpu_vendor"),
      ("GPU Model", "gpu_model"),
      ("OpenGL ES Version", "gles_version"),
      ("Known Texture Compression Types", "gles_texture_compressions"),
     ]
    ],
    ["Display",
     [("Resolution", "display_resolution"),
      ("Density", "display_density"),
      ("Size", "display_physical_size")
     ]
    ],
    ["Storage",
     [("Internal Storage Space Total", "internal_sd_capacity"),
      ("Internal Storage Space Available", "internal_sd_free"),
      ("SD Card Space Total", "external_sd_capacity"),
      ("SD Card Space Available", "external_sd_free"),
     ]
    ],
    ("Notable Features", "device_notable_features")
]

# information surfaced to the user in dump
# follows the same structure as brief config
SURFACED_VERBOSE = [
    ["Identity",
     [("Model", "device_model"),
      ("Manufacturer", "device_manufacturer"),
      ("Device", "device_device"),
      ("Name", "device_name"),
      ("Brand", "device_brand"),
      ("Serial Number", "device_serial_number"),
     ]
    ],
    ["System",
     [("API Level", "android_api_level"),
      ("Android Version", "android_version"),
      ("Aftermarket Firmware", "aftermarket_firmware"),
      ("Build ID", "android_build_id"),
      ("Build Fingerprint", "android_build_fingerprint"),
      ("Kernel Version", "kernel_version"),
     ]
    ],
    ["Chipset",
     [("Board", "board"),
      ("RAM", "ram_capacity"),
      ("CPU Architecture", "cpu_architecture"),
      ("Cores", "cpu_core_count"),
      ("Min Clock Frequency", "cpu_min_frequency"),
      ("Base Clock Frequency", "cpu_base_frequency"),
      ("Max Clock Frequency", "cpu_max_frequency"),
      ("Available ABIs", "cpu_abis"),
      ("CPU Features", "cpu_features"),
      ("GPU Vendor", "gpu_vendor"),
      ("GPU Model", "gpu_model"),
      ("OpenGL ES Version", "gles_version"),
      ("Known Texture Compression Types", "gles_texture_compressions"),
     ]
    ],
    ["Display",
     [("Resolution", "display_resolution"),
      ("Density", "display_density"),
      ("X-DPI", "display_x-dpi"),
      ("Y-DPI", "display_y-dpi"),
      ("Size", "display_physical_size"),
     ]
    ],
    ["Storage",
     [("Internal Storage Path", "internal_sd_path"),
      ("Internal Storage Space Total", "internal_sd_capacity"),
      ("Internal Storage Space Available", "internal_sd_free"),
      ("SD Card Path", "external_sd_path"),
      ("SD Card Space Total", "external_sd_capacity"),
      ("SD Card Space Available", "external_sd_free"),
     ]
    ],
    ("Notable Features", "device_notable_features"),
    ("Device Features", "device_features"),
    ("System Apps", "system_apps"),
    ("Third-Party Apps", "third-party_apps"),
    ("Shell Commands", "shell_commands"),
]

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
    "cpu_base_frequency",
    "cpu_core_count",
    "cpu_features",
    "cpu_max_frequency",
    "cpu_min_frequency",
    "device_brand",
    "device_device",
    "device_features",
    "device_manufacturer",
    "device_model",
    "device_name",
    "device_notable_features",
    "device_serial_number",
    "display_density",
    "display_physical_size",
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

KNOWN_COMPRESSION_NAMES = {}

def load_compression_names(surfaceflinger_dump):
    """"""
    extensions = []
    for identifier, name in KNOWN_COMPRESSION_NAMES.items():
        if identifier in surfaceflinger_dump:
            extensions.append(name)

    return extensions


def abi_to_arch(abi):
    """"""
    if abi not in helper.ABI_TO_ARCH:
        return "Unknown ({})".format(abi)

    return helper.ABI_TO_ARCH[abi]


def run_extraction_command(device, source_name):
    """Run extraction command and return its output.

    If there is a value stored under the corresponding source name in
    device's _init_cache, that value is then returned instead.
    """
    try:
        return device._init_cache[source_name]
    except KeyError:
        out = device.shell_command(*INFO_SOURCES[source_name], return_output=True, as_list=False)
        device._init_cache[source_name] = out
        return out


def extract_identity(device):
    """"""
    #serial = run_extraction_command(device, "iserial")
    getprop = run_extraction_command(device, "getprop")
    getprop_keys = [
        ("device_serial_number", "(?:\\[ro\\.boot\\.serialno\\]: \\[)([^\\]]*)"),
        ("device_model", "(?:\\[ro\\.product\\.model\\]: \\[)([^\\]]*)"),
        ("device_manufacturer", "(?:\\[ro\\.product\\.manufacturer\\]: \\[)([^\\]]*)"),
        ("device_device", "(?:\\[ro\\.product\\.device\\]: \\[)([^\\]]*)"),
        ("device_name", "(?:\\[ro\\.product\\.name\\]: \\[)([^\\]]*)"),
        ("device_brand", "(?:\\[ro\\.product\\.brand\\]: \\[)([^\\]]*)"),
    ]

    for name, re_string in getprop_keys:
        value = re.search(re_string, getprop)
        if not value:
            continue

        value = value.group(1).strip()
        device.info_dict[name] = value


def extract_os(device):
    """"""
    getprop = run_extraction_command(device, "getprop")
    getprop_keys = [
        ("android_version", "(?:\\[ro\\.build\\.version\\.release\\]\\:\\ \\[)([^\\]]*)"),
        ("android_api_level", "(?:\\[ro\\.build\\.version\\.sdk\\]\\:\\ \\[)([^\\]]*)"),
        ("android_build_id", "(?:\\[ro\\.build\\.id\\]\\:\\ \\[)([^\\]]*)"),
        ("android_build_fingerprint", "(?:\\[ro\\.build\\.fingerprint\\]\\:\\ \\[)([^\\]]*)"),
    ]
    for name, re_string in getprop_keys:
        value = re.search(re_string, getprop)
        if not value:
            continue

        value = value.group(1).strip()
        device.info_dict[name] = value

    kernel_version = run_extraction_command(device, "kernel_version").strip()
    device.info_dict["kernel_version"] = kernel_version

    # check for aftermarket firmware
    fire_os = re.search("(?:\\[ro\\.build\\.mktg\\.fireos\\]: \\[)([^\\]]*)", getprop)
    if fire_os:
        device.info_dict["aftermarket_firmware"] = "FireOS"
        device.info_dict["aftermarket_firmware_version"] = fire_os


def extract_chipset(device):
    """"""
    getprop = run_extraction_command(device, "getprop")

    meminfo = run_extraction_command(device, "meminfo")
    ram = re.search("(?:MemTotal\\:\\s*)([^A-z\\ ]*)", meminfo)
    if ram:
        device.info_dict["ram_capacity"] = ram.group(1).strip()

    abi1 = re.search("(?:\\[ro\\.product\\.cpu\\.abi\\]: \\[)([^\\]]*)", getprop)
    abi2 = re.search("(?:\\[ro\\.product\\.cpu\\.abi2\\]\\: \\[)([^\\]]*)", getprop)
    abilist = re.search("(?:\\[ro\\.product\\.cpu\\.abilist\\]\\: \\[)([^\\]]*)", getprop)
    cpu_arch = None

    if abilist:
        abilist = [x.strip() for x in abilist.group(1).strip().split(",")]
    else:
        abilist = []

    if abi1:
        abi1 = abi1.group(1).strip()
        abilist.append(abi1)
        try:
            cpu_arch = helper.ABI_TO_ARCH[abi1]
        except KeyError:
            pass
    if abi2:
        abi2 = abi2.group(1).strip()
        abilist.append(abi1)

    abilist = set(abilist)
    device.info_dict["cpu_abis"] = list(abilist)

    cpuinfo = run_extraction_command(device, "cpuinfo")
    board = re.search("(?:\\[ro\\.board\\.platform\\]: \\[)([^\\]]*)", getprop)
    if not board:
        for re_ in ["(?:Hardware\\s*?\\:)([^\n\r]*)",
                    "(?:model\\ name\\s*?\\:)([^\n\r]*)",
                    "(?:Processor\\s*?\\:)([^\n\r]*)"]:
            board = re.search(re_, cpuinfo)
            if board:
                break

    cpu_features = re.search("(?:Features\\s*?\\:)([^\\n\\r]*)", cpuinfo)
    if cpu_features:
        cpu_features = [x.strip() for x in cpu_features.group(1).split()]

    if board:
        board = board.group(1).strip()
    device.info_dict["board"] = board
    device.info_dict["cpu_features"] = cpu_features
    device.info_dict["cpu_architecture"] = cpu_arch

    max_frequency = run_extraction_command(device, "max_cpu_freq")
    if max_frequency:
        device.info_dict["cpu_max_frequency"] = max_frequency.strip()

    core_count = run_extraction_command(device, "possible_cpu_cores")
    max_cores = re.search("(?:\\-)([0-9]*)", core_count)
    if max_cores:
        device.info_dict["cpu_core_count"] = str(int(max_cores.group(1).strip()) + 1)


def extract_gpu(device):
    """"""
    gpu_vendor, gpu_model, gles_version = [None for x in range(3)]
    dumpsys = run_extraction_command(device, "surfaceflinger_dump")
    gpu_line = re.search("(?:GLES\\:)([^\n\r]*)", dumpsys)

    if gpu_line:
        gpu_vendor, gpu_model, gles_version = gpu_line.group(1).strip().split(",")

    gles_extensions = re.search("(?:GLES\\:[^\\r\\n]*)(?:\\s*)([^\\r\\n]*)", dumpsys)

    if gles_extensions:
        gles_extensions = gles_extensions.group(1).strip().split(" ")

        device.info_dict["gles_texture_compressions"] = []

        for extension in gles_extensions:
            try:
                device.info_dict["gles_texture_compressions"].append(
                    TEXTURE_COMPRESSION_IDS[extension])
            except KeyError:
                # extension is not a type of texture compression, continue
                continue

    device.info_dict["gpu_vendor"] = gpu_vendor
    device.info_dict["gpu_model"] = gpu_model
    device.info_dict["gles_version"] = gles_version


def extract_display(device):
    """"""
    getprop = run_extraction_command(device, "getprop")
    density = re.search("(?:\\[ro\\.sf\\.lcd_density\\]: \\[)([^\\]]*)", getprop)

    dumpsys = run_extraction_command(device, "surfaceflinger_dump")
    x_dpi = re.search("(?:x-dpi)([^\\n]*)", dumpsys)
    y_dpi = re.search("(?:y-dpi)([^\\n]*)", dumpsys)
    resolution = re.search("(?:Display\\[0\\] :)([^,]*)", dumpsys)

    if not resolution:
        wm_output = run_extraction_command(device, "screen_size")
        resolution = re.search("(?:Physical size:)([^\\n]*)", wm_output)

    if not density:
        wm_output = run_extraction_command(device, "screen_density")
        density = re.search("(?:Physical\\ density\\:)([0-9A-z]*)", wm_output)

    if resolution:
        resolution = resolution.group(1).strip()
    if density:
        density = density.group(1).strip()
    if x_dpi:
        x_dpi = x_dpi.group(1).strip()
    if y_dpi:
        y_dpi = y_dpi.group(1).strip()

    device.info_dict["display_density"] = density
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
    internal_sd = device.info_dict["internal_sd_path"]
    getprop = run_extraction_command(device, "getprop")
    trace_path = re.search("(?:\\[dalvik\\.vm\\.stack\\-trace\\-file\\]: \\[)([^\\]]*)", getprop)

    if not device.is_dir(internal_sd):
        internal_sd = re.search("(?:\\[internal\\_sd\\_path\\]: \\[)([^\\]]*)", getprop)

    external_sd = re.search("(?:\\[external\\_sd\\_path\\]: \\[)([^\\]]*)", getprop)
    shell_env = run_extraction_command(device, "shell_environment")

    if not device.is_dir(internal_sd):
        internal_sd = re.search("(?:EXTERNAL_STORAGE=)([^\n]*)", shell_env)

    if not device.is_dir(external_sd):
        external_sd = re.search("(?:SECONDARY_STORAGE=)([^\n]*)", shell_env)

    device.info_dict["internal_sd_path"] = internal_sd
    device.info_dict["external_sd_path"] = external_sd.group(1)
    device.info_dict["anr_trace_path"] = trace_path.group(1)


def extract_available_commands(device):
    """Extract a list of available shell commands."""
    device.info_dict["shell_commands"] = []

    for command in run_extraction_command(device, "available_commands").splitlines():
        if "permission denied" in command:
            continue

        device.info_dict["shell_commands"].append(command.strip())


def extract_installed_packages(device):
    """Extract a list of installed system and third-party packages."""
    device.info_dict["third-party_apps"] = []

    for package in run_extraction_command(device, "third-party_apps").splitlines():
        try:
            app = package.split("package:", maxsplit=1)[1]
        except IndexError:
            continue

        device.info_dict["third-party_apps"].append(app.strip())

    if device.info_dict["system_apps"]:
        # system apps can generally only be disabled, downgraded or updated
        # and do not need to be re-checked
        return

    device.info_dict["system_apps"] = []

    for package in run_extraction_command(device, "system_apps").splitlines():
        try:
            app = package.split("package:", maxsplit=1)[1]
        except IndexError:
            continue

        device.info_dict["system_apps"].append(app.strip())
