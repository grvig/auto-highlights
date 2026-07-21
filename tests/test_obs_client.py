"""Tests for the OBS websocket wrapper, using a fake obs-websocket client."""

import logging
from pathlib import Path
from types import SimpleNamespace

import pytest

from highlights.recorder.obs_client import ObsClient, ObsError


class FakeObs:
    """Stands in for obsws_python.ReqClient."""

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.started = False
        self.stopped = False
        self.directory = None
        self.disconnected = False
        self.output_path = "C:/clips/out.mkv"

    def get_version(self):
        return SimpleNamespace(obs_version="30.1.2")

    def set_record_directory(self, recordDirectory):  # noqa: N803 - obs API name
        self.directory = recordDirectory

    def start_record(self):
        self.started = True

    def stop_record(self):
        self.stopped = True
        return SimpleNamespace(output_path=self.output_path)

    def get_record_status(self):
        return SimpleNamespace(output_active=self.started and not self.stopped)

    def disconnect(self):
        self.disconnected = True


def make_client(fake=None, **kwargs):
    fake = fake or FakeObs()
    client = ObsClient(
        password="secret", client_factory=lambda **kw: fake, **kwargs
    )
    return client, fake


def test_connect_passes_credentials_and_logs_version(caplog):
    holder = {}

    def factory(**kwargs):
        holder.update(kwargs)
        return FakeObs(**kwargs)

    client = ObsClient(port=4455, password="pw", client_factory=factory)
    with caplog.at_level(logging.INFO):
        client.connect()
    assert holder["port"] == 4455
    assert holder["password"] == "pw"
    assert "30.1.2" in caplog.text


def test_connect_failure_mentions_websocket_settings():
    def failing_factory(**kwargs):
        raise OSError("connection refused")

    client = ObsClient(client_factory=failing_factory)
    with pytest.raises(ObsError, match="WebSocket Server Settings"):
        client.connect()


def test_start_and_stop_recording_returns_path():
    client, fake = make_client()
    client.connect()
    client.start_recording()
    assert fake.started
    path = client.stop_recording()
    assert fake.stopped
    assert path == Path("C:/clips/out.mkv")


def test_stop_without_reported_path_returns_none(caplog):
    fake = FakeObs()

    def stop():
        return SimpleNamespace()

    fake.stop_record = stop
    client, _ = make_client(fake)
    client.connect()
    with caplog.at_level(logging.WARNING):
        assert client.stop_recording() is None
    assert "did not report an output path" in caplog.text


def test_operations_require_a_connection():
    client = ObsClient(client_factory=lambda **kw: FakeObs())
    with pytest.raises(ObsError, match="Not connected"):
        client.start_recording()


def test_set_record_directory_resolves_path(tmp_path):
    client, fake = make_client()
    client.connect()
    client.set_record_directory(tmp_path)
    assert Path(fake.directory) == tmp_path.resolve()


def test_is_recording_reflects_status():
    client, _ = make_client()
    client.connect()
    assert not client.is_recording()
    client.start_recording()
    assert client.is_recording()


def test_obs_errors_are_wrapped():
    fake = FakeObs()

    def boom():
        raise RuntimeError("obs exploded")

    fake.start_record = boom
    client, _ = make_client(fake)
    client.connect()
    with pytest.raises(ObsError, match="refused to start"):
        client.start_recording()


def test_context_manager_disconnects():
    client, fake = make_client()
    with client:
        assert client.connected
    assert fake.disconnected
    assert not client.connected


def test_close_is_safe_when_never_connected():
    ObsClient(client_factory=lambda **kw: FakeObs()).close()
