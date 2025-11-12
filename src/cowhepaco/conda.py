import platform
import tarfile
import backports.zstd as zstd
import zipfile

SYSTEM = {
    "linux": "linux",
    "darwin": "osx",
    "windows": "win",
    "freebsd": "freebsd",
    "emscripten": "emscripten",
    "wasi": "wasi",
}

MACHINE = {
    "x86_64": "64",
    "amd64": "64",
    "aarch64": "aarch64",
    "arm64": "arm64",
}


def get_conda_platform():
    """
    Determine the conda platform string.

    Returns:
        str: The conda platform string.
    """
    system = platform.system().lower()
    machine = platform.machine().lower()
    return f"{SYSTEM[system]}-{MACHINE[machine]}"


def iter_files(package_filename):
    """
    Iterates over the files in a conda package.

    Args:
        package_filename (str): The path to the conda package.

    Yields:
        A file-like object for each file in the package.
    """
    if package_filename.endswith(".conda"):
        conda = zipfile.ZipFile(package_filename)
        for fileinfo in conda.filelist:
            if fileinfo.filename.startswith("pkg-"):
                break
        else:
            raise ValueError("pkg not found")
        pkg = conda.open(fileinfo)
        if fileinfo.filename.endswith(".zst"):
            pkg = zstd.open(pkg)
        tar = tarfile.open(fileobj=pkg, mode="r|*")
    else:
        tar = tarfile.open(package_filename, mode="r|*")
    for info in tar:
        if info.name.startswith("info/"):
            continue
        if info.isfile():
            file = tar.extractfile(info)
            file.raw.name = info.name
            yield file
        else:
            pass
