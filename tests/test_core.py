import threading

import pytest

from gvm import animations
from gvm.bd45r import BD45R, Mode
from gvm.colors import gradient, parse_color
from gvm.config import FixtureConfig, RigConfig, find_config
from gvm.controller import Controller


class FakeDmx:
    def __init__(self):
        self.channels = {}

    def set(self, channel, value):
        assert 0 <= value <= 255
        self.channels[channel] = value


def test_parse_color():
    assert parse_color("red") == (255, 0, 0)
    assert parse_color("#FF8800") == (255, 136, 0)
    assert parse_color("1,2,3") == (1, 2, 3)
    assert parse_color("hue:120") == (0, 255, 0)
    with pytest.raises(ValueError):
        parse_color("chartreuse-ish")


def test_gradient_endpoints():
    g = gradient([(255, 0, 0), (0, 0, 255)], 33)
    assert len(g) == 33 and g[0] == (255, 0, 0) and g[-1] == (0, 0, 255)
    assert gradient([(1, 2, 3)], 5) == [(1, 2, 3)] * 5


@pytest.mark.parametrize("name", list(animations.PIXEL_EFFECTS))
def test_pixel_effects_render(name):
    for t in (0, 0.5, 3.7, 60):
        frame = animations.PIXEL_EFFECTS[name][0](animations.Options(speed=7))(t, 33)
        assert len(frame) == 33 and all(0 <= v <= 255 for c in frame for v in c)


def test_rig_effect_stops_and_goes_dark():
    dmx = FakeDmx()
    tubes = [BD45R(dmx, 1, Mode.CCT_RGB, 1), BD45R(dmx, 232, Mode.CCT_RGB, 1)]
    stop = threading.Event()
    threading.Timer(0.3, stop.set).start()
    animations.run("table-pingpong", tubes, animations.Options(seconds=0), stop)
    assert all(v == 0 for ch, v in dmx.channels.items() if (ch - 1) % 7 == 0)  # every INT channel


def test_pixel_effect_rejects_whole_tube_mode():
    with pytest.raises(ValueError):
        animations.run("meteor", [BD45R(FakeDmx(), 1, Mode.CCT_RGB, 33)], animations.Options(seconds=0.1))


def test_find_config_prefers_env(tmp_path, monkeypatch):
    cfg = tmp_path / "rig.toml"
    cfg.write_text('[[fixture]]\nname = "a"\naddress = 1\n')
    monkeypatch.setenv("GVM_CONFIG", str(cfg))
    assert find_config() == cfg
    assert [f.name for f in RigConfig.load(cfg).fixtures] == ["a"]


def test_menu_settings_and_setup_guide():
    from gvm import setup_guide

    tube = BD45R(None, 232, Mode.CCT_RGB, 1, "tube2")
    assert tube.menu_settings() == {"CONTROL": "DMX", "DMX ADDR": "232", "DMX MODE": "CCT&RGB", "DMX PIXEL": "1"}
    assert "DMX PIXEL" not in BD45R(None, 1, Mode.PIXEL_FX).menu_settings()
    text = setup_guide.render_text([tube])
    assert "232" in text and "CCT&RGB" in text and "terminator" in text
    assert setup_guide.guide([tube])["tubes"][0]["set_on_light"]["DMX ADDR"] == "232"


def test_controller_state_roundtrip(tmp_path):
    ctl = Controller(RigConfig(fixtures=[FixtureConfig("t", 1, Mode.CCT_RGB, 1)]), tmp_path / "u.bin")
    ctl.save_state(bytes([7]) * 512)
    assert ctl.load_state() == bytes([7]) * 512
    assert [f.segments for f in ctl.layout()] == [33]
