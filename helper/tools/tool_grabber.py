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
import hashlib
import logging
import requests

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


#TODO: actually write the code for fetching packages
#TODO: step1: scan the whole repository for packages with matching versions
#TODO: step2: download that package
#TODO: step3: extract the needed tools from the package
#TODO: make this a cli utility
