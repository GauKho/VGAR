"""Group 7: import forms. Targets are the defining module, not the re-exporter."""
import cg_cases.helpers as hp
from cg_cases.g07_imports import make_token

from . import cycle_a
from .star_source import *  # noqa: F403


def main():
    hp.measure("abc")  # expect: cg_cases.helpers.measure
    make_token()  # expect: cg_cases.g07_imports.core.make_token
    star_helper()  # expect: cg_cases.g07_imports.star_source.star_helper  # noqa: F405
    from .lazy import lazy_value

    lazy_value()  # expect: cg_cases.g07_imports.lazy.lazy_value
    return cycle_a.ping_a(1)
