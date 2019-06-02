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
import shutil
import logging
import hashlib
from pathlib import Path
from zipfile import ZipFile
from urllib.parse import urljoin
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
            print("Error: connection timed out.")
            if retry_count >= max_retries:
                break

            print(" Retrying ({}/{})".format(retry_count, max_retries))
            continue

        if response.status_code != 200:
            print("Error: received HTTP status code {}."\
                  .format(response.status_code), end="")
            # give up if max_retries has been reached or response is 4xx
            if retry_count >= max_retries or str(response.status_code)[0] == '4':
                break

            retry_count += 1
            print(" Retrying({}/{})".format(retry_count, max_retries))
            continue

        if to_file:
            with open(to_file, mode="wb") as downloaded_file:
                for chunk in response.iter_content(chunk_size=(1024**2)*3):
                    downloaded_file.write(chunk)

            return to_file

        return response.text

        return str(response.status_code)

    print("\nERROR: COULD NOT COMPLETE DOWNLOAD")
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

#TODO: make this a cli utility
