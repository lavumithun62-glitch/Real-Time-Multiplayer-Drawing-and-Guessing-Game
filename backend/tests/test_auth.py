from app.auth import create_player_token, verify_player_token


def test_player_token_is_bound_to_player_and_room():
    token = create_player_token(12, "abc123")
    assert verify_player_token(token, 12, "ABC123")
    assert not verify_player_token(token, 13, "ABC123")
    assert not verify_player_token(token, 12, "OTHER1")
    assert not verify_player_token("not-a-token", 12, "ABC123")


def test_player_token_is_bound_to_room_and_player():
    from app.auth import create_player_token, verify_player_token
    token = create_player_token(123, "ABC123")
    assert verify_player_token(token, 123, "ABC123") is True
    assert verify_player_token(token, 124, "ABC123") is False
    assert verify_player_token(token, 123, "OTHER1") is False
