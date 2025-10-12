import sys
import pathlib


def _ensure_src_in_path():
    root = pathlib.Path(__file__).resolve().parent
    src = root / "src"
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))


def main():
    _ensure_src_in_path()
    # Import here so src/ is on sys.path when modules are loaded
    from hubs_api import cli
    cli()


if __name__ == "__main__":
    main()


