"""Plan 1565: the needle's stopwatch (contract/SCHEMA-1565.md section 5). Runs `navigator.hold` IN THIS PROCESS with its four
arguments unchanged, with one socket shim that notes the wall clock and the process CPU clock at every send and every receipt.
It reads nothing and changes nothing: the bytes the needle sends, receives and writes are the bytes it would without the shim.
Per turn (one line sent, one line received): `think` runs from the previous receipt (or the connect) to this send, `wait` from
this send to this receipt. Written as JSON lines to --out when the needle returns, then a last line for the tail after the last
receipt. Entry: python -m environment.needle_timer --out needle-time.jsonl -- <the arguments of navigator.hold>"""
import json
import socket
import sys
import time

KEYS = ("turn", "think_wall_s", "think_cpu_s", "wait_wall_s", "wait_cpu_s")


def _now():
    return time.perf_counter(), time.process_time()


class _Book:
    def __init__(self):
        self.mark, self.sent, self.rows = _now(), None, []

    def send(self):
        self.sent = _now()

    def recv(self):
        now = _now()
        self.rows.append(dict(zip(KEYS, (len(self.rows) + 1, self.sent[0] - self.mark[0], self.sent[1] - self.mark[1],
                                          now[0] - self.sent[0], now[1] - self.sent[1]))))
        self.mark = now

    def tail(self):
        now = _now()
        return {"turn": None, "think_wall_s": now[0] - self.mark[0], "think_cpu_s": now[1] - self.mark[1], "wait_wall_s": 0.0,
                "wait_cpu_s": 0.0}


class _File:
    def __init__(self, f, book):
        self._f, self._book = f, book

    def readline(self, *a):
        line = self._f.readline(*a)
        self._book.recv()
        return line

    def __getattr__(self, k):
        return getattr(self._f, k)


class _Sock:
    def __init__(self, s, book):
        self._s, self._book = s, book

    def sendall(self, data, *a):
        self._book.send()
        return self._s.sendall(data, *a)

    def makefile(self, *a, **k):
        return _File(self._s.makefile(*a, **k), self._book)

    def __getattr__(self, k):
        return getattr(self._s, k)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return self._s.__exit__(*exc)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    out, rest = argv[argv.index("--out") + 1], argv[argv.index("--") + 1:]
    book, real = _Book(), socket.create_connection
    socket.create_connection = lambda *a, **k: (setattr(book, "mark", _now()), _Sock(real(*a, **k), book))[1]
    from navigator import hold
    try:
        return hold.main(rest)
    finally:
        with open(out, "w") as f:
            for r in book.rows + [book.tail()]:
                f.write(json.dumps(r) + "\n")


if __name__ == "__main__":
    sys.exit(main())
