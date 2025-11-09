import argparse
import shutil
import re
from pathlib import Path
from collections import defaultdict

DATABASE_FILENAME = "metadata.db"
HTML_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>{title}</title>
</head>
<body>
    <h1>{title}</h1>
{items}
</body>
</html>
"""
HTML_ITEM = '    <a href="{href}">{name}</a><br>'


def normalize(name):
    return re.sub(r"[-_.]+", "-", name).lower()


def update_index(index_dir: Path, files_dir: Path):
    """
    Updates the simple index HTML files.
    """
    simple_dir = index_dir / "simple"
    simple_dir.mkdir(exist_ok=True)

    packages = defaultdict(list)
    for file in files_dir.rglob("*.whl"):
        name, _, version = file.name.partition("-")
        packages[normalize(name)].append(file)

    items = [
        HTML_ITEM.format(
            href=f"{name}/index.html",
            name=name,
        )
        for name in packages
    ]

    # Generate main index.html
    main_index_path = simple_dir / "index.html"
    with open(main_index_path, "w") as f:
        f.write(HTML_TEMPLATE.format(title="Index", items="\n".join(items)))
    print(f"Generated main index at: {main_index_path}")

    # Generate project-specific index.html files
    for name, files in packages.items():
        project_dir = simple_dir / name
        project_dir.mkdir(exist_ok=True)
        project_index_path = project_dir / "index.html"
        items = [
            HTML_ITEM.format(
                href=file.relative_to(project_dir),
                name=file.name,
            )
            for file in files
        ]
        with open(project_index_path, "w") as f:
            f.write(HTML_TEMPLATE.format(title="Index", items="\n".join(items)))
        print(f"Generated index for {name} at: {project_index_path}")


def add_wheel(wheel_path: Path, index_dir: Path):
    """
    Adds a wheel file to the index.
    """
    if not wheel_path.is_file():
        raise FileNotFoundError(f"Wheel file not found: {wheel_path}")

    files_dir = index_dir / "files"
    files_dir.mkdir(exist_ok=True, parents=True)
    destination_path = files_dir / wheel_path.name
    shutil.copy(wheel_path, destination_path)
    print(f"Copied wheel to: {destination_path}")
    update_index(index_dir, files_dir)


def main():
    parser = argparse.ArgumentParser(description="Manage a PEP 503 index.")
    subparsers = parser.add_subparsers(dest="command")

    add_parser = subparsers.add_parser("add", help="Add a wheel file to the index.")
    add_parser.add_argument(
        "wheel_path", nargs="+", type=Path, help="Path to the wheel file."
    )
    add_parser.add_argument(
        "--index-dir",
        type=Path,
        default=Path("pep503-index"),
        help="Path to the index directory.",
    )

    update_parser = subparsers.add_parser("update", help="Update the index HTML files.")
    update_parser.add_argument(
        "--index-dir",
        type=Path,
        default=Path("pep503-index"),
        help="Path to the index directory.",
    )

    args = parser.parse_args()
    if args.command == "add":
        try:
            for path in args.wheel_path:
                add_wheel(path, args.index_dir)
        except (FileNotFoundError, ValueError) as e:
            print(f"Error: {e}")
    elif args.command == "update":
        update_index(args.index_dir, args.index_dir / "files")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
