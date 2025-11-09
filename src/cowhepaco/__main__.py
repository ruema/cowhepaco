import re
import json
import argparse
import urllib.request
import zipfile
from pathlib import Path
from .conda import iter_files


def read_entry_points(wheel):
    for fileinfo in wheel.filelist:
        if fileinfo.filename.endswith(".dist-info/entry_points.txt"):
            break
    else:
        return {}
    result = {}
    in_scripts = False
    for line in wheel.open(fileinfo):
        line = line.strip().decode()
        if line.startswith("["):
            in_scripts = line == "[console_scripts]"
        elif in_scripts:
            name, _, script = line.partition("=")
            result[name.strip()] = script.strip()
    return result


def compare(files, wheel):
    names_seen = set()
    errors = []
    entry_points = read_entry_points(wheel)
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
        elif "bin" in file.name.split("/"):
            name = file.name.partition("bin/")[-1]
            if name not in entry_points:
                errors.append(("outside", file.name))
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
    filename = f"{package_name_normalized}-{package_version}-"
    try:
        response = urllib.request.urlopen(request)
    except urllib.error.HTTPError as error:
        return None
    files = json.loads(response.read())["files"]
    found = {}
    for file in files:
        if file["filename"].startswith(filename):
            stem = file["filename"].rsplit(".", 1)[0]
            file_tag = stem[len(filename) :]
            found[file_tag] = file
    if tag in found:
        return found[tag]
    if "py3-none-any" in found:
        return found["py3-none-any"]
    if tag in found:
        return found[tag]
    python_tag, abi_tag, rest = tag.split("_", 2)
    for file_tag, file in found.items():
        if file_tag.startswith(f"{python_tag}_{abi_tag}_"):
            if "manylinux" in file_tag and "x86_64" in file_tag:
                return file
    return None


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


def download_and_compare(package_path, conda_package_name):
    package_name, version, tag = get_wheel_filename(conda_package_name)
    if package_name is None:
        print(f"{conda_package_name}: wheel name not found")
        return
    wheel_info = get_pypi_wheel_url(package_name, version, tag)
    if wheel_info is None:
        print(
            f"{conda_package_name}: wheel package not found ({package_name}, {version}, {tag})"
        )
        return
    filename = package_path / "broken" / Path(wheel_info["filename"]).name
    filename.parent.mkdir(exist_ok=True, parents=True)
    try:
        response = urllib.request.urlopen(wheel_info["url"])
    except urllib.error.HTTPError as error:
        print(
            f"{conda_package_name}: wheel package not found ({package_name}, {version}, {tag}, {wheel_info['url']}, {error})"
        )
        return
    data = response.read()
    with open(filename, "wb") as file:
        file.write(data)
    files = iter_files(conda_package_name)
    wheel = zipfile.ZipFile(filename)
    errors = compare(files, wheel)
    if errors:
        print(f"{conda_package_name}: {errors}")
        return
    print(f"{conda_package_name}: ok")
    filename.rename(filename.parent / ".." / filename.name)


def main():
    parser = argparse.ArgumentParser(description="Compares conda and wheel packages.")
    parser.add_argument(
        "conda_package_name", nargs="+", help="The name of the package."
    )
    parser.add_argument(
        "--package-dir",
        type=Path,
        default=Path("packages"),
        help="Path to the package directory.",
    )
    args = parser.parse_args()
    for conda_package_name in args.conda_package_name:
        download_and_compare(args.package_dir, conda_package_name)


if __name__ == "__main__":
    main()
