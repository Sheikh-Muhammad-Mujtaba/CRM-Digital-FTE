from channels.web_form_handler import build_web_event


class DummyPayload:
    customer_id = "c-1"
    customer_name = "Test User"
    customer_email = "test@example.com"
    message = "Need help"


def test_web_event_builder():
    event = build_web_event(DummyPayload())
    assert event["channel"] == "web"
    assert event["customer_email"] == "test@example.com"
