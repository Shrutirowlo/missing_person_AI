"""Shared AI-layer primitives.

Nothing here trains, modifies, or regenerates models. Adapters only
*load* the ORIGINAL artifacts read-only and call the ORIGINAL pipelines.
"""


class AIMissingDependency(Exception):
    """Raised when a required ORIGINAL artifact is absent.

    The adapter stays explicit: callers must surface this instead of
    silently substituting another model.
    """


class AINotAvailable(Exception):
    """Raised when an adapter cannot run (missing files, failed init)."""
