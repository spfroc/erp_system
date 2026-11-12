from utils import strip_surrogates


def test_plain_text_unchanged():
    assert strip_surrogates("泉易采平台") == "泉易采平台"


def test_drops_lone_surrogate():
    raw = "泉\ud835采"
    cleaned = strip_surrogates(raw)
    assert cleaned == "泉采"
    cleaned.encode("utf-8")


def test_keeps_surrogate_pair_as_scalar():
    raw = "\ud835\udc00"
    cleaned = strip_surrogates(raw)
    assert cleaned == "\U0001d400"
    cleaned.encode("utf-8")
