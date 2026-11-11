from datetime import datetime

from clients.sd_ccgp import SdCcgpClient


def test_stable_notice_key_ignores_rotating_list_id():
    title = "山东省威海体育训练中心采购办公软件成交公告"
    pub = "2026-11-09 16:01:09"
    kind = "0302"
    key1 = SdCcgpClient.stable_notice_key(
        title=title,
        publish_time=pub,
        notice_type=kind,
        notice_id="AAA-rotating-1",
    )
    key2 = SdCcgpClient.stable_notice_key(
        title=title,
        publish_time=datetime(2026, 11, 9, 16, 1, 9),
        notice_type=kind,
        notice_id="BBB-rotating-2",
    )
    assert key1 == key2
    assert key1.startswith("tp:")


def test_stable_notice_key_normalizes_whitespace():
    a = SdCcgpClient.stable_notice_key(
        title="青岛 理工 大学 意向",
        publish_time="2026-11-06 11:08:34",
        notice_type="2500",
    )
    b = SdCcgpClient.stable_notice_key(
        title="青岛理工大学意向",
        publish_time="2026-11-06 11:08:34",
        notice_type="2500",
    )
    assert a == b


def test_stable_notice_key_fallback_to_id_hash():
    key = SdCcgpClient.stable_notice_key(
        title="",
        publish_time=None,
        notice_type="0302",
        notice_id="plain-id",
    )
    assert key.startswith("id:")
    assert key == "id:" + SdCcgpClient.notice_key("plain-id")
