import re
import json
import argparse
import urllib.request
import zipfile
from pathlib import Path
from .conda import iter_files


def compare(files, wheel):
    names_seen = set()
    errors = []
    for file in files:
        if "site-packages" in file.name.split("/"):
            name = file.name.partition("site-packages/")[-1]
            names_seen.add(name)
            try:
                data = wheel.open(name).read()
            except KeyError:
                if file.name.endswith(".pyc"):
                    continue
                errors.append(("not found", name))
            else:
                if file.read() != data:
                    errors.append(("differ", name))
        else:
            errors.append(("outside", file.name))
    not_found = (
        set(info.filename for info in wheel.filelist if not info.is_dir()) - names_seen
    )
    for file in not_found:
        errors.append(("additional", file))
    return [
        (mode, name)
        for mode, name in errors
        if not name.split("/")[0].endswith(".dist-info")
    ]


def get_pypi_wheel_url(package_name, package_version, tag):
    package_name_normalized = re.sub("[-._]+", "_", package_name).lower()
    url = f"https://pypi.org/simple/{package_name_normalized}"
    request = urllib.request.Request(
        url, headers={"Accept": "application/vnd.pypi.simple.v1+json"}
    )
    filename = f"{package_name_normalized}-{package_version}-{tag}.whl"
    response = urllib.request.urlopen(request)
    files = json.loads(response.read())["files"]
    for file in files:
        print(file["filename"], filename)
        if file["filename"] == filename:
            return file


def get_wheel_filename(conda_package_name):
    package_name = None
    version = None
    tag = None
    files = iter_files(conda_package_name)
    for file in files:
        if file.name.endswith("/METADATA"):
            lines = file.read().decode().split("\n")
            for line in lines:
                if line.startswith("Name:"):
                    package_name = line.split(":", 1)[1].strip()
                elif line.startswith("Version:"):
                    version = line.split(":", 1)[1].strip()
                    break
        if file.name.endswith("/WHEEL"):
            lines = file.read().decode().split("\n")
            for line in lines:
                if line.startswith("Tag:"):
                    tag = line.split(":", 1)[1].strip()
    return package_name, version, tag


def main():
    parser = argparse.ArgumentParser(description="Compares conda and wheel packages.")
    parser.add_argument("conda_package_name", help="The name of the package.")
    args = parser.parse_args()
    package_name, version, tag = get_wheel_filename(args.conda_package_name)
    wheel_info = get_pypi_wheel_url(package_name, version, tag)
    filename = Path(wheel_info["filename"]).name
    response = urllib.request.urlopen(wheel_info["url"])
    data = response.read()
    with open(filename, "wb") as file:
        file.write(data)
    files = iter_files(args.conda_package_name)
    wheel = zipfile.ZipFile(filename)
    print(compare(files, wheel))


if __name__ == "__main__":
    main()
