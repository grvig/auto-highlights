"""Tests for the HLAE recorder backend, with the game and ffmpeg faked."""

from pathlib import Path

from highlights.engine.moments import HighlightType, Moment, Segment
from highlights.recorder.base import ClipRequest
from highlights.recorder.hlae_backend import LEAD_TICKS, HlaeRecorder


class FakeConsole:
    """Records commands; like HLAE, writes a take's video when one starts."""

    def __init__(self, replies=None):
        self.sent = []
        self.replies = list(replies or [])
        self.write_video = True

    def send_all(self, commands):
        self.sent.extend(commands)
        for command in commands:
            if command.startswith("mirv_streams record name") and self.write_video:
                take = Path(command.split('"')[1])
                (take / "video.mp4").write_bytes(b"frames")

    def read_lines(self, seconds):
        lines, self.replies = self.replies, []
        return lines


class FakeCs2:
    tickrate = 64

    def __init__(self, landings=None, seek_ok=True):
        self.console = FakeConsole()
        self.landings = list(landings or [])
        self.seek_ok = seek_ok
        self.log = []

    def launch(self, args):
        self.log.append(("launch", args[0]))

    def attach_when_ready(self):
        self.log.append(("attach",))

    def attach(self):
        self.log.append(("attach",))

    def stage_demo(self, path):
        return Path(path).stem

    def load_demo(self, name):
        self.log.append(("load", name))

    def seek_to(self, tick):
        self.log.append(("seek", tick))
        return self.seek_ok

    def spectate(self, name):
        self.log.append(("spectate", name))

    def play_ticks(self, ticks):
        self.log.append(("step", ticks))
        return self.landings.pop(0) if self.landings else None

    def quit(self):
        self.log.append(("quit",))


def make_request(tmp_path, pov=None, camera=None):
    moment = Moment(
        round_number=5, highlight_type=HighlightType.KILL, player_steamid="P",
        core_tick=26300, start_tick=26207, end_tick=26527, description="kill",
    )
    return ClipRequest(
        index=1, moment=moment, demo_path=Path("D:/demos/nuke.dem"), player_name="semi",
        output_path=tmp_path / "001_r05_kill_semi.mp4",
        segment=Segment(26207, 26527, pov_steamid=pov), camera_name=camera,
    )


def recorder(tmp_path, cs2, runs):
    return HlaeRecorder(cs2, tmp_path, runner=runs.append, sleeper=lambda s: None)


def test_records_one_take_seeking_before_the_window(tmp_path):
    cs2, runs = FakeCs2(landings=[26528]), []
    clip = recorder(tmp_path, cs2, runs).record_clip(make_request(tmp_path))
    assert clip.succeeded
    assert ("seek", 26207 - LEAD_TICKS) in cs2.log
    assert ("step", 320 + LEAD_TICKS) in cs2.log
    assert ("spectate", "semi") in cs2.log
    assert "mirv_streams record start" in cs2.console.sent
    assert cs2.console.sent[-1] == "host_framerate 0"
    finish = runs[0]
    assert finish[finish.index("-ss") + 1] == "0.500"  # 32 lead ticks
    assert finish[-1].endswith("001_r05_kill_semi.mp4")


def test_victim_cam_spectates_the_victim(tmp_path):
    cs2, runs = FakeCs2(landings=[26527]), []
    recorder(tmp_path, cs2, runs).record_clip(make_request(tmp_path, pov="V", camera="臻咘踔"))
    assert ("spectate", "臻咘踔") in cs2.log


def test_a_take_that_lands_wrong_is_recorded_again(tmp_path):
    cs2, runs = FakeCs2(landings=[12000, 26526]), []
    assert recorder(tmp_path, cs2, runs).record_clip(make_request(tmp_path)).succeeded
    assert [entry for entry in cs2.log if entry[0] == "step"] == [("step", 352)] * 2


def test_each_take_gets_a_fresh_folder(tmp_path):
    cs2, runs = FakeCs2(landings=[1, 26527]), []
    rec = recorder(tmp_path, cs2, runs)
    rec.keep_takes = True
    rec.record_clip(make_request(tmp_path))
    takes = sorted(p.name for p in (tmp_path / "takes").iterdir())
    assert takes == ["001_r05_kill_semi", "001_r05_kill_semi_2"]


def test_the_demo_is_loaded_once_for_many_clips(tmp_path):
    cs2, runs = FakeCs2(landings=[26527, 26527]), []
    rec = recorder(tmp_path, cs2, runs)
    rec.record_clip(make_request(tmp_path))
    rec.record_clip(make_request(tmp_path))
    assert [e for e in cs2.log if e[0] == "load"] == [("load", "nuke")]


def test_failed_seek_becomes_a_failed_clip(tmp_path):
    cs2, runs = FakeCs2(seek_ok=False), []
    clip = recorder(tmp_path, cs2, runs).record_clip(make_request(tmp_path))
    assert not clip.succeeded and "seek" in clip.error
    assert runs == []


def test_open_launches_through_hlae_when_asked(tmp_path):
    cs2 = FakeCs2()
    HlaeRecorder(cs2, tmp_path, launch_args=["HLAE.exe"], sleeper=lambda s: None).open()
    assert cs2.log[:2] == [("launch", "HLAE.exe"), ("attach",)]


def test_close_stops_streams_and_quits(tmp_path):
    cs2 = FakeCs2()
    HlaeRecorder(cs2, tmp_path).close()
    assert "mirv_streams record end" in cs2.console.sent
    assert cs2.log[-1] == ("quit",)


def test_consecutive_clips_use_fresh_presets(tmp_path):
    cs2, runs = FakeCs2(landings=[26527, 26527]), []
    rec = recorder(tmp_path, cs2, runs)
    rec.record_clip(make_request(tmp_path))
    rec.record_clip(make_request(tmp_path))
    presets = [c.split()[-1] for c in cs2.console.sent if c.startswith("mirv_streams record screen settings")]
    assert presets == ["ahtake1", "ahtake2"]


def test_hlae_errors_fail_the_clip_with_hlaes_own_words(tmp_path):
    cs2, runs = FakeCs2(landings=[26527]), []
    cs2.console.replies = ["AFXERROR: There is already a setting named ahtake1"]
    clip = recorder(tmp_path, cs2, runs).record_clip(make_request(tmp_path))
    assert not clip.succeeded
    assert "already a setting" in clip.error
    assert not any(e[0] == "step" for e in cs2.log)


def test_a_take_without_video_is_reported_not_muxed(tmp_path):
    cs2, runs = FakeCs2(landings=[26527]), []
    cs2.console.write_video = False
    clip = recorder(tmp_path, cs2, runs).record_clip(make_request(tmp_path))
    assert not clip.succeeded and "no video" in clip.error
    assert runs == []


def test_raw_takes_are_removed_once_the_clip_is_finished(tmp_path):
    cs2, runs = FakeCs2(landings=[1, 26527]), []
    assert recorder(tmp_path, cs2, runs).record_clip(make_request(tmp_path)).succeeded
    assert list((tmp_path / "takes").iterdir()) == []


def test_raw_takes_are_kept_when_a_clip_fails(tmp_path):
    cs2, runs = FakeCs2(landings=[26527]), []
    cs2.console.write_video = False
    recorder(tmp_path, cs2, runs).record_clip(make_request(tmp_path))
    assert [p.name for p in (tmp_path / "takes").iterdir()] == ["001_r05_kill_semi"]


def test_ramped_clips_render_faster_and_finish_with_their_ramps(tmp_path):
    from dataclasses import replace

    cs2, runs = FakeCs2(landings=[26527]), []
    request = make_request(tmp_path)
    ramped = replace(request.segment, ramps=((26399, 26431),), ramp_speed=0.4)
    rec = recorder(tmp_path, cs2, runs)
    rec.record_clip(replace(request, segment=ramped))
    assert "host_framerate 150" in cs2.console.sent
    graph = runs[0][runs[0].index("-filter_complex") + 1]
    assert "trim=start=3:end=3.5" in graph  # ticks 192-224 into the clip


def test_plain_clips_render_at_the_normal_rate(tmp_path):
    cs2, runs = FakeCs2(landings=[26527]), []
    recorder(tmp_path, cs2, runs).record_clip(make_request(tmp_path))
    assert "host_framerate 60" in cs2.console.sent


def test_close_puts_the_players_settings_back_before_quitting(tmp_path):
    cs2 = FakeCs2()
    HlaeRecorder(cs2, tmp_path, restore_commands=["hud_showtargetid 1"]).close()
    assert cs2.console.sent[-1] == "hud_showtargetid 1"
    assert cs2.log[-1] == ("quit",)


def test_hlae_is_noted_as_working_after_its_first_good_clip_only(tmp_path):
    cs2, runs, calls = FakeCs2(landings=[26527, 26527]), [], []
    rec = HlaeRecorder(cs2, tmp_path, runner=runs.append, sleeper=lambda s: None,
                       on_working=lambda: calls.append(1))
    rec.record_clip(make_request(tmp_path))
    rec.record_clip(make_request(tmp_path))
    assert calls == [1]


def test_a_failed_clip_does_not_note_hlae_as_working(tmp_path):
    calls = []
    rec = HlaeRecorder(FakeCs2(seek_ok=False), tmp_path, runner=[].append, sleeper=lambda s: None,
                       on_working=lambda: calls.append(1))
    assert not rec.record_clip(make_request(tmp_path)).succeeded
    assert calls == []


def test_failing_to_note_hlae_works_does_not_fail_the_clip(tmp_path):
    def broken():
        raise OSError("read-only")
    rec = HlaeRecorder(FakeCs2(landings=[26527]), tmp_path, runner=[].append, sleeper=lambda s: None,
                       on_working=broken)
    assert rec.record_clip(make_request(tmp_path)).succeeded


def test_an_unhookable_build_marks_the_backend_unusable(tmp_path):
    from highlights.recorder.cs2_controller import HookUnsupported

    class Unhookable(FakeCs2):
        def load_demo(self, name, settle_seconds=3.0):
            raise HookUnsupported("HLAE cannot hook CS2 build 26798866 yet")

    rec = HlaeRecorder(Unhookable(), tmp_path, runner=[].append, sleeper=lambda s: None)
    assert rec.unusable is None
    clip = rec.record_clip(make_request(tmp_path))
    assert not clip.succeeded and "cannot hook" in clip.error
    assert rec.unusable == clip.error


def test_a_game_that_drops_the_console_ends_the_run_cleanly(tmp_path):
    from highlights.recorder.cs2_console import ConsoleError

    class Crashed(FakeCs2):
        def load_demo(self, name, settle_seconds=3.0):
            raise ConsoleError("Console connection failed: [WinError 10054] connection reset")

    rec = HlaeRecorder(Crashed(), tmp_path, runner=[].append, sleeper=lambda s: None)
    clip = rec.record_clip(make_request(tmp_path))  # no exception escapes
    assert not clip.succeeded and "stopped answering" in clip.error
    assert rec.unusable == clip.error
