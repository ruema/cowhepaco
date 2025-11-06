import argparse
import sqlite3
import shutil
import re
import hashlib
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

def create_database(index_dir: Path):
    conn = sqlite3.connect(index_dir / DATABASE_FILENAME)
    cursor = conn.cursor()
    # For idempotency, we can use ALTER TABLE, but for this simple script,
    # we'll just recreate the table if needed (assuming a fresh start).
    # A more robust solution would use a migration tool.
    cursor.execute("DROP TABLE IF EXISTS packages")
    cursor.execute('''
        CREATE TABLE packages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            version TEXT NOT NULL,
            path TEXT NOT NULL,
            sha256 TEXT NOT NULL,
            UNIQUE(name, version)
        )
    ''')
    conn.commit()
    conn.close()

def normalize(name):
    return re.sub(r"[-_.]+", "-", name).lower()

def calculate_sha256(path: Path) -> str:
    """Calculates the SHA256 hash of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            # Reading in chunks is more efficient for large files
            chunk = f.read(8192)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()

def update_index(index_dir: Path):
    """
    Updates the simple index HTML files.
    """
    db_path = index_dir / DATABASE_FILENAME
    simple_dir = index_dir / 'simple'
    simple_dir.mkdir(exist_ok=True)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT name, path, sha256 FROM packages")
    rows = cursor.fetchall()
    conn.close()

    packages = defaultdict(list)
    for name, path, sha256 in rows:
        packages[name].append((path, sha256))

    items = [
        HTML_ITEM.format(
            href=normalize(name) + "/index.html",
            name=normalize(name),
        )
        for name in packages
    ]

    # Generate main index.html
    main_index_path = simple_dir / 'index.html'
    with open(main_index_path, 'w') as f:
        f.write(HTML_TEMPLATE.format(title="Index", items="\n".join(items)))
    print(f"Generated main index at: {main_index_path}")

    # Generate project-specific index.html files
    for name, files in packages.items():
        normalized_name = normalize(name)
        project_dir = simple_dir / normalized_name
        project_dir.mkdir(exist_ok=True)
        project_index_path = project_dir / 'index.html'
        items = [
            HTML_ITEM.format(
                href=f"{Path('..') / '..' / path}#sha265={sha256}",
                name=Path(path).name,
            )
            for path, sha256 in files
        ]
        with open(project_index_path, 'w') as f:
            f.write(HTML_TEMPLATE.format(title="Index", items="\n".join(items)))
        print(f"Generated index for {name} at: {project_index_path}")

def add_wheel(wheel_path: Path, index_dir: Path):
    """
    Adds a wheel file to the index.
    """
    if not wheel_path.is_file():
        raise FileNotFoundError(f"Wheel file not found: {wheel_path}")

    name, _, version = wheel_path.name.partition('-')

    files_dir = index_dir / 'files'
    files_dir.mkdir(exist_ok=True, parents=True)
    destination_path = files_dir / wheel_path.name
    shutil.copy(wheel_path, destination_path)
    print(f"Copied wheel to: {destination_path}")

    sha256 = calculate_sha256(destination_path)

    db_path = index_dir / DATABASE_FILENAME
    if not db_path.is_file():
        index_dir.mkdir(exist_ok=True, parents=True)
        create_database(index_dir)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO packages (name, version, path, sha256) VALUES (?, ?, ?, ?)",
            (name, version, str(destination_path.relative_to(index_dir)), sha256)
        )
        conn.commit()
        print(f"Added {name}-{version} to the database with sha256: {sha256}")
    except sqlite3.IntegrityError:
        print(f"Package {name}-{version} already exists in the database.")
    finally:
        conn.close()
    
    update_index(index_dir)


def main():
    parser = argparse.ArgumentParser(description="Manage a PEP 503 index.")
    subparsers = parser.add_subparsers(dest="command")

    add_parser = subparsers.add_parser("add", help="Add a wheel file to the index.")
    add_parser.add_argument("wheel_path", nargs="+", type=Path, help="Path to the wheel file.")
    add_parser.add_argument("--index-dir", type=Path, default=Path("pep503-index"), help="Path to the index directory.")

    update_parser = subparsers.add_parser("update", help="Update the index HTML files.")
    update_parser.add_argument("--index-dir", type=Path, default=Path("pep503-index"), help="Path to the index directory.")
    
    args = parser.parse_args()
    if args.command == "add":
        try:
            for path in args.wheel_path:
                add_wheel(path, args.index_dir)
        except (FileNotFoundError, ValueError) as e:
            print(f"Error: {e}")
    elif args.command == "update":
        update_index(args.index_dir)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
