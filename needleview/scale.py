"""The two forms of a y scale. A span of zero is its own form, so nothing is ever added to it."""
from dataclasses import dataclass
from typing import Union


@dataclass(frozen=True)
class Affine:
    lo: float
    hi: float
    top: float
    height: float

    def y(self, v):
        return self.top + self.height - (v - self.lo) / (self.hi - self.lo) * self.height


@dataclass(frozen=True)
class Flat:
    top: float
    height: float

    def y(self, v):
        return self.top + self.height / 2.0


def scale(lo, hi, top, height) -> Union[Affine, Flat]:
    """lo <= hi by construction (a min and a max of the same numbers): equal is Flat, otherwise Affine."""
    if hi > lo:
        return Affine(lo, hi, top, height)
    return Flat(top, height)
