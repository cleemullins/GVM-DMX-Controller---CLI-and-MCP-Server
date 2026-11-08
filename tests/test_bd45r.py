import pytest

from gvm.bd45r import BD45R, Mode, green_magenta, hue, kelvin, percent, speed
from gvm.config import FixtureConfig, _check_overlaps


class FakeDmx:
    def __init__(self):
        self.channels = {}

    def set(self, channel, value):
        assert 0 <= value <= 255
        self.channels[channel] = value


def test_encodings():
    assert (percent(0), percent(50), percent(100)) == (0, 128, 255)
    assert (kelvin(2700), kelvin(10000)) == (0, 255)
    assert green_magenta(0) == 128
    assert hue(360) == 255
    assert (speed(1), speed(10)) == (5, 95)
    with pytest.raises(ValueError):
        kelvin(2000)


def test_cct_rgb_whole_tube():
    dmx = FakeDmx()
    tube = BD45R(dmx, 8, Mode.CCT_RGB, 33)
    assert tube.footprint == 7 and tube.last_channel == 14
    tube.cct(100, 10000)
    assert dmx.channels == {8: 255, 9: 255, 10: 128, 11: 0}
    tube.rgb(50, 255, 0, 10)
    assert [dmx.channels[c] for c in range(11, 15)] == [255, 255, 0, 10]
    assert dmx.channels[8] == 128


def test_segments():
    dmx = FakeDmx()
    tube = BD45R(dmx, 1, Mode.RGB, pixel=1)
    assert tube.segments == 33 and tube.last_channel == 132
    tube.rgb(100, 1, 2, 3, segment=33)
    assert dmx.channels == {129: 255, 130: 1, 131: 2, 132: 3}


def test_reverse_flips_segments():
    tube = BD45R(FakeDmx(), 1, Mode.RGB, pixel=1, reverse=True)
    assert tube.channel("int", 1) == 129
    assert tube.channel("int", 33) == 1


def test_mode_rejects_missing_channel():
    with pytest.raises(ValueError):
        BD45R(FakeDmx(), 1, Mode.CCT).rgb(50, 1, 2, 3)


def test_effect_and_parse():
    dmx = FakeDmx()
    BD45R(dmx, 1, Mode.EFFECT).effect("candle", 100, 3, temperature=2700)
    assert dmx.channels == {1: 255, 2: 35, 3: 0, 4: 25, 5: 0}
    assert Mode.parse("cct&rgb") is Mode.CCT_RGB
    assert Mode.parse("PIXEL FX") is Mode.PIXEL_FX


def test_fixture_spec():
    f = FixtureConfig.parse("tube1:1:CCT&RGB:1:reverse")
    assert (f.name, f.address, f.mode, f.pixel, f.reverse) == ("tube1", 1, Mode.CCT_RGB, 1, True)
    f = FixtureConfig.parse("t2:16")
    assert (f.mode, f.pixel, f.reverse) == (Mode.CCT_RGB, 33, False)
    with pytest.raises(ValueError):
        FixtureConfig.parse("t3:1:RGB:1:backwards")


def test_overlap_detected():
    dmx = FakeDmx()
    with pytest.raises(ValueError):
        _check_overlaps([BD45R(dmx, 1, Mode.CCT_RGB), BD45R(dmx, 5, Mode.CCT_RGB)])
