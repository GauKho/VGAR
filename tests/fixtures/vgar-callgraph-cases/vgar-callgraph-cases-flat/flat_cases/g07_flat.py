"""Group 7 (flat layout): relative import plus a namespace package."""
import nsp.tools.helper as nh
from nsp.tools.helper import shout

from .core import build


def main():
    shout("hi")  # expect: nsp.tools.helper.shout
    nh.whisper("HI")  # expect: nsp.tools.helper.whisper
    return build(1)  # expect: flat_cases.core.build
