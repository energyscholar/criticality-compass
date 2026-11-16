"""Plan 1553: the dial as a delay line (contract/SCHEMA-1553.md section 2). Pure; imports only dataclasses.
A position commanded at index c is in force from index c + lag on. The track only grows: there is no operation that
removes, replaces or hastens an arrival."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Track:
    lag: int
    arrivals: tuple   # ((arrival index, position tuple), ...) in the order commanded


def start(lag, pos):
    return Track(lag, ((0, tuple(pos)),))


def command(track, index, pos):
    return Track(track.lag, track.arrivals + ((index + track.lag, tuple(pos)),))


def commanded(track):
    return list(track.arrivals[-1][1])


def at(track, index):
    for i, pos in reversed(track.arrivals):
        if i <= index:
            return list(pos)


def runs(track, lo, hi):
    out = [[lo, at(track, lo)]]
    for i, pos in track.arrivals:
        if lo < i < hi and list(pos) != out[-1][1]:
            out.append([i, list(pos)])
    return out
