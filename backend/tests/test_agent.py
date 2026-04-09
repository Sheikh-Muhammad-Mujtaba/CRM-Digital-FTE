from agent.formatters import format_for_channel


def test_whatsapp_formatter_truncates():
    text = "x" * 500
    assert len(format_for_channel("whatsapp", text)) == 400
