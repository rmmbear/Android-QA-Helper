"""
This module is for downloading adb and aapt from Android project repository.

Old repositories:
- https://dl-ssl.google.com/android/repository/repository.xml
- https://dl-ssl.google.com/android/repository/repository-10.xml

Current repositories:
- https://dl-ssl.google.com/android/repository/repository-11.xml
- https://dl-ssl.google.com/android/repository/repository-12.xml

https://docs.python.org/3.8/whatsnew/3.8.html#f-strings-now-support-for-quick-and-easy-debugging
https://docs.python.org/3.8/whatsnew/3.8.html#f-strings-now-support-for-quick-and-easy-debugging
11 and 12 are nearly identical - the only difference is that 12 includes
lldb entries.

Note: there is an automated github project tracking repository changes:
https://github.com/eagletmt/android-repository-history

Note: both 11 and 12 only keep the latest version of platform-tools
If an earlier version is needed, repo bacups from the github project
listed above will need to be used (links should still be working)
"""

import sys
import time
import shutil
import logging
import hashlib
from pathlib import Path
from zipfile import ZipFile
from urllib.parse import urljoin
from argparse import ArgumentParser

import xml.etree.ElementTree as ET
from xml.etree.ElementTree import ParseError as XMLParseError

import requests
from requests.exceptions import InvalidSchema, InvalidURL, MissingSchema

from helper import CWD

VERSION = 0.1
LOGGER = logging.getLogger(__name__)

SUPPORTED_PLATFORMS = {
    "linux":  "linux",
    "win32":  "windows",
    "darwin": "macosx",
}
try:
    HOST_PLATFORM = SUPPORTED_PLATFORMS[sys.platform]
except KeyError:
    HOST_PLATFORM = sys.platform

DEFAULT_DOWNLOAD_DIR = CWD + "/download"
DEFAULT_EXTRACT_DIR = CWD + "/bin"
DEFAULT_REPOSITORY = "https://dl-ssl.google.com/android/repository/repository-12.xml"
USER_AGENT = "".join(
    ["ToolGrabber/", str(VERSION),
     "(+https://github.com/rmmbear/Android-QA-Helper)"
    ]
)

class DownloadIndicator:
    def __init__(self, total_size, write_to=sys.stdout):
        self.total_size = total_size
        self.console = write_to
        self.downloaded = 0
        self.start_time = 0
        self.previous_chunk_time = 0


    def update(self, chunk_size):
        self.downloaded += chunk_size
        time_now = time.time()
        elapsed = time_now - self.previous_chunk_time
        self.previous_chunk_time = time_now
        speed = (chunk_size/elapsed)/1024**2
        if self.total_size:
            percentage = f"{(self.downloaded/self.total_size*100):.2f}%"
        else:
            percentage = f"{self.downloaded/(1024**2)}/? MB"

        self.clear()
        self.console.write(f"{speed:.2f} MiB/s, {percentage}, {time.time() - self.start_time:.2f}s")
        self.console.flush()


    def clear(self):
        # clear line, move cursor to start of the line
        self.console.write("\033[2K\033[1G")


    def __enter__(self):
        self.start_time = time.time()
        self.previous_chunk_time = time.time()
        return self


    def __exit__(self, exc_type, exc_val, exc_tb):
        self.clear()
        time_elapsed = time.time() - self.start_time
        downloaded_mb = self.downloaded/(1024**2)
        self.console.write(f"Downloaded {downloaded_mb:.2f} MBs in {time_elapsed:.2f}s ({downloaded_mb/time_elapsed:.2f} MB/s avg)\n")
        self.console.flush()
        #return False

def download(link, to_file=False, max_retries=3):
    """
    """
    retry_count = 0
    LOGGER.debug("Downloading %s", link)
    #mmm... spagetti
    while True:
        print("Downloading {}... ".format(link))
        try:
            response = requests.get(
                link, headers={"User-agent":USER_AGENT}, stream=True, timeout=10)
        except requests.exceptions.ReadTimeout:
            LOGGER.error("Connection timed out.")
            if retry_count >= max_retries:
                break

            print(" Retrying ({}/{})".format(retry_count, max_retries))
            continue

        if response.status_code != 200:
            LOGGER.error("Received HTTP error code %s", response.status_code)
            # give up if max_retries has been reached or response is 4xx
            if retry_count >= max_retries or str(response.status_code)[0] == '4':
                break

            retry_count += 1
            print(" Retrying({}/{})".format(retry_count, max_retries))
            continue


        if to_file:
            try:
                total_size = int(response.headers["Content-Length"])
            except KeyError:
                total_size = 0

            with DownloadIndicator(total_size) as indicator:
                with open(to_file, mode="wb") as downloaded_file:
                    for chunk in response.iter_content(chunk_size=(1024**2)*3):
                        indicator.update(len(chunk))
                        downloaded_file.write(chunk)

            return to_file

        return response.text

    LOGGER.error("COULD NOT COMPLETE DOWNLOAD")
    return ""


def generate_sha1_hash(file_path, chunk_size=None):
    """small helper function for generating sha1 checksum"""
    sha1_hash = hashlib.sha1()
    with open(file_path, mode="br") as file:
        chunk = file.read(chunk_size)
        while chunk:
            sha1_hash.update(chunk)
            chunk = file.read(chunk_size)

    return sha1_hash.hexdigest()


def find_packages(repository=DEFAULT_REPOSITORY, api_level="",
                  desired_packages=("build-tool", "platform-tool"),
                  accept_platform=HOST_PLATFORM, disable_previews=False):
    """Find the newest package that matches the api_level requirement.
    Returned dict has the following structure, all values are strings:
    <package type> : {
        api_level : 'x.x.x',
        platform : 'windows' OR 'linux' OR 'macosx',
        url : <direct url to the package>,
        checksum : <sha1 checksum>,
        size : <size in bytes>
    }
    """
    if not repository.startswith("http") and Path(repository).is_file():
        with open(repository, mode="r") as local_xml:
            xml_file = local_xml.read()
    else:
        LOGGER.info("Provided repository string is not a path")
        try:
            xml_file = download(repository)
        except (InvalidSchema, InvalidURL, MissingSchema) as err:
            LOGGER.error("nonexistent file or invalid url, error caught:")
            LOGGER.error(err)
            return {}

    try:
        xml = ET.fromstring(xml_file)
    except XMLParseError as err:
        LOGGER.error("could not parse the file, error caught:")
        LOGGER.error(err)
        return {}

    package_dict = {x:None for x in desired_packages}

    default_ns = xml.tag.split("}", maxsplit=1)[0] + "}"

    # I opted for not doing much of error checking here
    # if any of these elements are missing, it probably means the
    # structure of the repository has changed and this function will
    # need to be rewritten anyway
    # the implementation relies on the fact that the first item in group
    # of packages will be the newest one
    # I'm doing this because the repository structure hasn't changed in years
    for package_group in desired_packages:
        for package in xml.findall(default_ns+package_group):
            tag = package.tag[len(default_ns)::]

            revision = package.find(default_ns+"revision")

            package_api_level = []
            package_api_level.append(revision.find(default_ns+"major").text)
            package_api_level.append(revision.find(default_ns+"minor").text)
            package_api_level.append(revision.find(default_ns+"micro").text)
            preview = revision.find(default_ns+"preview")
            if preview is not None:
                package_api_level.append("rc" + preview.text)
            package_api_level = ".".join(package_api_level)

            if disable_previews and preview is not None:
                continue

            if api_level and package_api_level[:len(api_level)] != api_level:
                continue

            package_info = {}
            package_info["api_level"] = package_api_level

            for archive in package.find(default_ns+"archives"):
                platform = archive.find(default_ns+"host-os").text

                if platform == accept_platform:
                    package_info["platform"] = platform
                    package_info["checksum"] = archive.find(default_ns+"checksum").text
                    package_info["size"] = archive.find(default_ns+"size").text
                    package_info["url"] = archive.find(default_ns+"url").text
                    package_info["url"] = urljoin(repository, package_info["url"])
                    break

            package_dict[tag] = package_info
            break

    return package_dict


def download_package(url, size, checksum, download_to=DEFAULT_DOWNLOAD_DIR):
    """Download tool package.
    Returns path fo the downloaded archive (string).
    """
    package_path = Path(download_to)
    package_path.mkdir(parents=True, exist_ok=True)
    package_path = package_path / url.rsplit("/", maxsplit=1)[-1]

    downloaded_path = download(url, str(package_path), False)
    validated = True

    if downloaded_path:
        local_size = package_path.stat().st_size
        if local_size != int(size):
            LOGGER.error("Size of downloaded package does not match size announced in repo:")
            LOGGER.error("local size %s vs %s remote", local_size, size)
            validated = False

        local_checksum = generate_sha1_hash(str(downloaded_path))
        if local_checksum != checksum:
            LOGGER.error("Checksum of downloaded package differs from one announced in repo:")
            LOGGER.error("local checksum %s vs %s remote", local_checksum, checksum)
            validated = False

        if not validated:
            package_path.unlink()
            downloaded_path = ""

    return downloaded_path


def extract_tools(package_path, package_type, platform, extract_to=DEFAULT_EXTRACT_DIR):
    """
    """
    Path(extract_to).mkdir(parents=True, exist_ok=True)
    include = {
        "build-tool": {
            "windows": ("aapt.exe",),
            "macosx":  ("aapt", "lib64/libc++.so"),
            "linux":   ("aapt", "lib64/libc++.so")
        },
        "platform-tool": {
            "windows": ("adb.exe", "AdbWinApi.dll", "AdbWinUsbApi.dll"),
            "macosx":  ("adb",),
            "linux":   ("adb",)
        }
    }
    extract_path = Path(extract_to)
    extract_path.mkdir(parents=True, exist_ok=True)
    files_to_extract = include[package_type][platform]
    files_in_archive = []

    with ZipFile(package_path) as archive:
        for zip_filename in archive.namelist():
            for filename in files_to_extract:
                if zip_filename.endswith(filename):
                    files_in_archive.append(zip_filename)
                    break

        if len(files_to_extract) != len(files_in_archive):
            LOGGER.error("Archive does not contain all of required files!")
            LOGGER.error("expected %s", files_to_extract)
            LOGGER.error("found %s", files_in_archive)
            return ""

        for src, dest, in zip(files_in_archive, files_to_extract):
            dest_path = extract_path / dest
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            with dest_path.open(mode="bw") as dest_file:
                with archive.open(src) as src_file:
                    shutil.copyfileobj(src_file, dest_file)

            dest_path.chmod(0o775)

    return str(extract_path)


def main(arguments=None):
    parser = ArgumentParser(prog="ToolGrabber")
    parser.add_argument(
        "--tool", choices=["adb", "aapt", "all"], default="all",
        help="Pick which tool will be downloaded. Defaults to 'all' (will download both adb and aapt).")
    parser.add_argument(
        "--download-dir", nargs=1, type=str, default=DEFAULT_DOWNLOAD_DIR, metavar="DIR",
        help=f"Place downloaded archives in specified directory, instead of in '{DEFAULT_DOWNLOAD_DIR}'")
    parser.add_argument(
        "--extract-dir", nargs=1, type=str, default=DEFAULT_EXTRACT_DIR, metavar="DIR",
        help=f"Place extracted tools in specified directory, instead of in'{DEFAULT_EXTRACT_DIR}'")
    parser.add_argument(
        "--disable-previews", action="store_true",
        help="""Disable preview builds (also know as 'release candidates', abbreviated to rc).
                By default an rc build will be picked if it is the newest availablebuilds""")
    parser.add_argument(
        "--no-extract", action="store_true",
        help="""Do not extract tools from downloaded packages.""")
    parser.add_argument(
        "--platform", choices=["windows", "macosx", "linux"], default=HOST_PLATFORM,
        help=f"""Download packages meant for specified OS instead of the host's OS
                 Detected OS for this host: {HOST_PLATFORM}""")
    parser.add_argument(
        "--api-level", nargs=1, default="", type=str, metavar="X[.X[.X]]",
        help="""Make grabber retrieve packages matching the specified API level (newest package
                is picked when API level is not specified). This value must be provided in this
                format: <major>.<minor>.<micro> Micro and minor can be left out - grabber will
                then pick the newest _matching_ package. Note that latest available version of
                either packages should be fine for most uses""")
    parser.add_argument(
        "--repository", nargs=1, default=DEFAULT_REPOSITORY, metavar="XML",
        help=f"""Make grabber use the provided repository file instead of the
                 default one ({DEFAULT_REPOSITORY})""")

    args = parser.parse_args(arguments)

    if args.platform not in ["windows", "linux", "macosx"]:
        LOGGER.error("Platform is not supported: %s", HOST_PLATFORM)

    tool_to_package = {
        "adb":("platform-tool",),
        "aapt":("build-tool",),
        "all":("platform-tool", "build-tool"),
    }
    desired_packages = tool_to_package[args.tool]
    known_packages = find_packages(
        args.repository, args.api_level, desired_packages, args.platform, args.disable_previews
    )

    downloaded_packages = []
    for package_type, package_dict in known_packages.items():
        if not package_dict:
            LOGGER.error("Could not find any matching %s package", package_type)
            continue

        package_path = download_package(
            package_dict["url"], package_dict["size"], package_dict["checksum"],
            download_to=args.download_dir)

        if not package_path:
            continue

        if args.no_extract:
            downloaded_packages.append(package_path)
            continue

        tool_path = extract_tools(
            package_path, package_type, package_dict["platform"], args.extract_dir)
        if tool_path:
            downloaded_packages.append(package_type)

    if downloaded_packages:
        print("DONE! Your tools can be found in:")
        print(args.extract_dir)
