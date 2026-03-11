from easy_ecom.domain.services.stock_policy import stock_deltas


def test_stock_deltas_on_hand_only_for_supported_types() -> None:
    assert stock_deltas("IN", 5).on_hand == 5
    assert stock_deltas("ADJUST", 2).on_hand == 2
    assert stock_deltas("ADJUST+", 3).on_hand == 3
    assert stock_deltas("OUT", 4).on_hand == -4


def test_stock_deltas_tracks_pending_inbound_separately() -> None:
    pending = stock_deltas("INBOUND_PENDING", 6)
    received = stock_deltas("INBOUND_RECEIVED", 2)

    assert pending.on_hand == 0
    assert pending.incoming == 6
    assert received.on_hand == 0
    assert received.incoming == -2


def test_stock_deltas_unknown_type_no_effect() -> None:
    delta = stock_deltas("SOME_UNKNOWN", 9)
    assert delta.on_hand == 0
    assert delta.incoming == 0
    assert delta.reserved == 0
