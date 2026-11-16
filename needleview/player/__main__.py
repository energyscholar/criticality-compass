"""The only module that opens a file: the command `python -m needleview.player`."""
import argparse
import sys

from needleview.player.page import render
from needleview.player.stream import events, refused


def load(run, world, label, path, truth):
    """read `path` as UTF-8 and cut it into events. A path that cannot be read is a refused run, never an exception."""
    try:
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
    except UnicodeDecodeError:
        return refused(run, world, label, "the file is not valid UTF-8")
    except (OSError, ValueError) as e:
        return refused(run, world, label, f"the file could not be read ({type(e).__name__})")
    return events(run, world, label, text, truth)


def _items(parser, raw):
    out, seen = [], set()
    for item in raw:
        left, sep, path = item.partition("=")
        world, slash, label = left.partition("/")
        if not (sep and slash and world and label and path):
            parser.error(f"{item!r} is not WORLD/RUN=PATH")
        if (world, label) in seen:
            parser.error(f"{world}/{label} is given twice")
        seen.add((world, label))
        out.append((world, label, path))
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(prog="needleview.player", description="Show needle reports as one animated HTML page.")
    parser.add_argument("--out", required=True, help="the HTML file to write")
    parser.add_argument("--truth", action="store_true", help="show the truth from a scored verdict file, in the SYSTEM zone")
    parser.add_argument("items", nargs="+", metavar="ITEM", help="WORLD/RUN=PATH")
    try:
        args = parser.parse_args(argv)
        triples = _items(parser, args.items)
    except SystemExit as e:
        return e.code if isinstance(e.code, int) else 2
    stream = ()
    for i, (world, label, path) in enumerate(triples):
        stream += load(i, world, label, path, args.truth)
    page = render(stream)
    try:
        with open(args.out, "wb") as fh:
            fh.write(page.encode("utf-8"))
    except OSError as e:
        print(f"needleview.player: cannot write the output ({type(e).__name__})", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
