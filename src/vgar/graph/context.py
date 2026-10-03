"""M1 import compatibility for the shared context contract.

Define context models in vgar.contracts.context so producer and consumers use
the same classes and validators. Existing vgar.graph.context imports remain valid.
"""

from vgar.contracts.context import ContextItem, ContextPayload, SourceRange


__all__ = ["SourceRange", "ContextItem", "ContextPayload"]
