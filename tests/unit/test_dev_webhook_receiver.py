from scripts.dev_webhook_receiver import format_received


def test_format_received_pretty_prints_json_body():
    body = b'{"type": "high_queue", "severity": "warning"}'

    out = format_received("/webhook", body)

    assert "[webhook] POST /webhook" in out
    assert '"type": "high_queue"' in out
    assert '"severity": "warning"' in out


def test_format_received_falls_back_to_raw_text_for_non_json():
    out = format_received("/slack", b"not json")

    assert "[webhook] POST /slack" in out
    assert "not json" in out
