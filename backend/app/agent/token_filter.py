from app.agent import prompts


class NotFoundFilter:
    """Holds back the start of a streamed answer while it could still be the NOT_FOUND signal.

    The signal is replaced by a friendly refusal at the end, so streaming it would show
    the user an internal code word.
    """

    def __init__(self) -> None:
        self._held = ""
        self._deciding = True

    def feed(self, chunk: str) -> str:
        """Return the text that is now safe to stream (possibly empty)."""
        if not self._deciding:
            return chunk
        self._held += chunk
        if prompts.NOT_FOUND.startswith(self._held.strip()):
            return ""
        self._deciding = False
        return self._release()

    def flush(self) -> str:
        """Call when the reply ends; returns held text unless it was the signal."""
        if self._held.strip() == prompts.NOT_FOUND:
            self._held = ""
        return self._release()

    def _release(self) -> str:
        text, self._held = self._held, ""
        return text
