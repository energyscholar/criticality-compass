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


def _usage(parser, items):
    out = []
    for item in items:
        label, sep, path = item.partition("=")
        if not sep:
            label = path = item
        if not label or not path:
            parser.error(f"an empty LABEL or PATH in {item!r}")
        out.append((label, path))
    return out


def main(argv=None):
    import argparse
    import sys

    from needleview.draw import render

    parser = argparse.ArgumentParser(prog="needleview", description="Draw needle reports as one static HTML page.")
    parser.add_argument("--out", required=True, help="the HTML file to write")
    parser.add_argument("--truth", action="store_true", help="overlay the truth from a scored verdict file")
    parser.add_argument("items", nargs="+", metavar="ITEM", help="PATH, or LABEL=PATH")
    try:
        args = parser.parse_args(argv)
        pairs = _usage(parser, args.items)
    except SystemExit as e:
        return e.code if isinstance(e.code, int) else 2
    page = render([load(label, path, args.truth) for label, path in pairs])
    try:
        with open(args.out, "wb") as fh:
            fh.write(page.encode("utf-8"))
    except OSError as e:
        print(f"needleview: cannot write the output ({type(e).__name__})", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
