"""Time limits for AI requests.

The HTTP libraries only limit single network operations, and each material can
need several calls. These helpers enforce a limit on the whole thing.
"""

import threading
import time

from .errors import AIDeadlineExceeded, AIProviderTimeout


class Deadline:
    """The time budget shared by every AI call made for one user request."""

    def __init__(self, seconds: float):
        self.seconds = seconds
        self._ends_at = time.monotonic() + seconds

    def remaining(self) -> float:
        return max(0.0, self._ends_at - time.monotonic())

    def error(self) -> AIDeadlineExceeded:
        return AIDeadlineExceeded(
            f"Shërbimet AI nuk e përfunduan punën brenda {self.seconds:g} sekondave. "
            "Provo përsëri pas një minute ose me një material më të shkurtër."
        )


def run_with_limit(function, seconds: float):
    """Run ``function`` and stop waiting for it after ``seconds``.

    The abandoned call keeps running in a background thread until its own
    network timeout ends it, but the user is no longer kept waiting.
    """
    outcome = {}

    def work():
        try:
            outcome["result"] = function()
        except BaseException as exc:  # handed over to the caller below
            outcome["error"] = exc

    thread = threading.Thread(target=work, daemon=True)
    thread.start()
    thread.join(seconds)

    if thread.is_alive():
        raise AIProviderTimeout(f"Shërbimi AI nuk u përgjigj brenda {seconds:.0f} sekondave.")
    if "error" in outcome:
        raise outcome["error"]
    return outcome["result"]
