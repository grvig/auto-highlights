"""OBS Studio control over obs-websocket.

Wraps obsws-python so the rest of the recorder deals in start/stop and an
output path, not websocket details. The underlying client is injectable, which
keeps this testable with OBS closed.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_HOST = "localhost"
DEFAULT_PORT = 4455
DEFAULT_TIMEOUT = 5.0

ClientFactory = Callable[..., Any]


class ObsError(Exception):
    """Raised when OBS cannot be reached or refuses a request."""


def _default_client_factory(**kwargs: Any) -> Any:
    # Imported lazily so the module can be imported (and tested) on a machine
    # without obsws-python present.
    import obsws_python

    return obsws_python.ReqClient(**kwargs)


class ObsClient:
    """Start and stop OBS recordings."""

    def __init__(
        self,
        host: str = DEFAULT_HOST,
        port: int = DEFAULT_PORT,
        password: str = "",
        timeout: float = DEFAULT_TIMEOUT,
        client_factory: ClientFactory | None = None,
    ) -> None:
        self.host = host
        self.port = port
        self.password = password
        self.timeout = timeout
        self._client_factory = client_factory or _default_client_factory
        self._client: Any | None = None

    @property
    def connected(self) -> bool:
        return self._client is not None

    def connect(self) -> None:
        """Connect to obs-websocket, or explain clearly why it failed."""
        if self._client is not None:
            return
        logger.info("Connecting to OBS at %s:%s", self.host, self.port)
        try:
            self._client = self._client_factory(
                host=self.host,
                port=self.port,
                password=self.password,
                timeout=self.timeout,
            )
        except Exception as error:  # obsws raises a variety of types
            raise ObsError(
                f"Could not connect to OBS at {self.host}:{self.port} ({error}). "
                "Check OBS is running and its WebSocket server is enabled under "
                "Tools -> WebSocket Server Settings, and that the password matches."
            ) from error
        logger.info("OBS connected (%s)", self._describe_version())

    def _describe_version(self) -> str:
        try:
            version = self._client.get_version()
            return f"OBS {getattr(version, 'obs_version', '?')}"
        except Exception as error:  # diagnostics only, never fatal
            logger.debug("Could not read OBS version: %s", error)
            return "version unknown"

    def _require_client(self) -> Any:
        if self._client is None:
            raise ObsError("Not connected to OBS")
        return self._client

    def set_record_directory(self, directory: Path | str) -> None:
        """Point OBS at the folder clips should land in."""
        client = self._require_client()
        target = str(Path(directory).resolve())
        logger.info("Setting OBS record directory to %s", target)
        try:
            client.set_record_directory(target)
        except Exception as error:
            raise ObsError(f"Could not set OBS record directory: {error}") from error

    def start_recording(self) -> None:
        client = self._require_client()
        logger.info("OBS start recording")
        try:
            client.start_record()
        except Exception as error:
            raise ObsError(f"OBS refused to start recording: {error}") from error

    def stop_recording(self) -> Path | None:
        """Stop recording and return the file OBS wrote, if it reported one."""
        client = self._require_client()
        logger.info("OBS stop recording")
        try:
            response = client.stop_record()
        except Exception as error:
            raise ObsError(f"OBS refused to stop recording: {error}") from error

        raw_path = getattr(response, "output_path", None)
        if raw_path is None:
            logger.warning("OBS did not report an output path for the recording")
            return None
        logger.info("OBS wrote %s", raw_path)
        return Path(raw_path)

    def is_recording(self) -> bool:
        client = self._require_client()
        try:
            status = client.get_record_status()
        except Exception as error:
            raise ObsError(f"Could not read OBS record status: {error}") from error
        return bool(getattr(status, "output_active", False))

    def close(self) -> None:
        """Disconnect. Safe to call when never connected."""
        if self._client is None:
            return
        logger.info("Disconnecting from OBS")
        try:
            disconnect = getattr(self._client, "disconnect", None)
            if callable(disconnect):
                disconnect()
        except Exception as error:
            logger.debug("Error disconnecting from OBS: %s", error)
        finally:
            self._client = None

    def __enter__(self) -> ObsClient:
        self.connect()
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()
