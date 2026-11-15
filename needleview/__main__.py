"""The only module that opens a file."""
from needleview.report import Unreadable, parse


def load(label, path, truth):
    """read `path` as UTF-8 and parse it. A path that cannot be read gives an Unreadable, never an exception."""
    try:
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
    except UnicodeDecodeError:
        return Unreadable(label, "the file is not valid UTF-8")
    except (OSError, ValueError) as e:
        return Unreadable(label, f"the file could not be read ({type(e).__name__})")
    return parse(label, text, truth)
