"""开头大字卡：只在前几秒出现、位于字幕上方，且为空时不改变渲染路径。"""

import os
from unittest.mock import patch

import numpy as np
import pytest
from moviepy import ColorClip, CompositeVideoClip
from pydantic import ValidationError

from app.models.schema import VideoParams
from app.services import video as vd
from app.utils import utils

FONT = os.path.join(utils.font_dir(), "BeVietnamPro-Bold.ttf").replace("\\", "/")
WIDTH, HEIGHT = 540, 960


def _yellow_mask(frame):
    r, g, b = (frame[..., i].astype(int) for i in range(3))
    return (r > 200) & (g > 180) & (b < 140)


@pytest.mark.parametrize("text", ["", "   ", None])
def test_empty_hook_text_renders_nothing(text):
    assert vd.create_hook_card_clip(text, FONT, WIDTH, HEIGHT, 2.0) is None


def test_hook_card_shows_only_during_its_seconds_above_subtitles():
    card = vd.create_hook_card_clip("SAY LESS. GET MORE.", FONT, WIDTH, HEIGHT, 2.0)
    assert card.start == 0
    assert card.duration == pytest.approx(2.0)
    assert card.w <= WIDTH * vd.HOOK_CARD_MAX_WIDTH_RATIO

    base = ColorClip(size=(WIDTH, HEIGHT), color=(0, 0, 255), duration=3)
    video = CompositeVideoClip([base, card])
    during = _yellow_mask(video.get_frame(0.5))
    after = _yellow_mask(video.get_frame(2.5))

    assert during.sum() > 500
    assert after.sum() == 0
    rows = np.where(during.any(axis=1))[0]
    # 字卡整体位于画面上半部到中部，不进入 66% 以下的字幕区域。
    assert rows.max() < HEIGHT * 0.6


def test_long_hook_text_wraps_inside_the_frame():
    card = vd.create_hook_card_clip(
        "Stop asking for the big thing first, ask for something tiny",
        FONT,
        WIDTH,
        HEIGHT,
        2.0,
    )
    assert card.w <= WIDTH
    assert card.h < HEIGHT / 2


def test_pipe_forces_line_breaks():
    with patch.object(vd, "wrap_text", wraps=vd.wrap_text) as wrap:
        vd.create_hook_card_clip("STOP  TALKING. | ASK THIS.", FONT, WIDTH, HEIGHT, 2.0)
    # wrap_text 遇到硬换行会按行递归调用自身，第一次调用才是完整输入。
    assert wrap.call_args_list[0].args[0] == "STOP TALKING.\nASK THIS."
    assert vd.create_hook_card_clip(" | ", FONT, WIDTH, HEIGHT, 2.0) is None


def test_manual_line_stays_on_one_line_by_shrinking_font():
    with patch.object(vd, "TextClip", wraps=vd.TextClip) as text_clip:
        vd.create_hook_card_clip("STOP TALKING. | ASK THIS.", FONT, WIDTH, HEIGHT, 2.0)
    kwargs = text_clip.call_args.kwargs
    assert kwargs["text"] == "STOP TALKING.\nASK THIS."
    base = int(WIDTH * vd.HOOK_CARD_FONT_WIDTH_RATIO)
    assert int(base * vd.HOOK_CARD_MIN_FONT_SCALE) <= kwargs["font_size"] <= base


def test_hook_fields_are_validated():
    params = VideoParams(video_subject="x", hook_text="SAY LESS", hook_duration=3)
    assert params.hook_text == "SAY LESS"
    assert VideoParams(video_subject="x").hook_text == ""
    with pytest.raises(ValidationError):
        VideoParams(video_subject="x", hook_duration=0)
    with pytest.raises(ValidationError):
        VideoParams(video_subject="x", hook_text="x" * 121)


class _FakeClip:
    def __init__(self, duration=5):
        self.duration = duration
        self.fps = 44100

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()

    def close(self):
        pass

    def with_effects(self, _effects):
        return self

    def with_audio(self, _audio):
        return self


@pytest.mark.parametrize(
    ("hook_text", "hook_duration", "video_duration", "expected"),
    [("SAY LESS", 2.0, 30, 2.0), ("SAY LESS", 4.0, 3, 3.0), ("", 2.0, 30, None)],
)
def test_generate_video_adds_card_without_subtitles(
    hook_text, hook_duration, video_duration, expected
):
    params = VideoParams(
        video_subject="x",
        subtitle_enabled=False,
        bgm_type="",
        font_name="BeVietnamPro-Bold.ttf",
        hook_text=hook_text,
        hook_duration=hook_duration,
    )
    card = object()
    with (
        patch.object(vd, "_open_video_clip_quietly", return_value=_FakeClip(video_duration)),
        patch.object(vd, "AudioFileClip", return_value=_FakeClip()),
        patch.object(vd, "create_hook_card_clip", return_value=card) as make_card,
        patch.object(vd, "CompositeVideoClip", return_value=_FakeClip(video_duration)) as compose,
        patch.object(vd, "_write_videofile_with_codec_fallback") as writer,
        patch.object(vd, "_get_configured_video_codec", return_value="libx264"),
    ):
        assert vd.generate_video(
            video_path="combined.mp4",
            audio_path="voice.mp3",
            subtitle_path="",
            output_file="final.mp4",
            params=params,
        )
    writer.assert_called_once()
    if expected is None:
        make_card.assert_not_called()
        compose.assert_not_called()
    else:
        assert make_card.call_args.kwargs["duration"] == pytest.approx(expected)
        assert make_card.call_args.kwargs["font_path"].endswith("BeVietnamPro-Bold.ttf")
        assert compose.call_args.args[0][1] is card
