from app.game import score_for_guess
def test_score_increases_with_time():
    assert score_for_guess(60,1)>score_for_guess(10,1)
def test_round_bonus():
    assert score_for_guess(20,3)>score_for_guess(20,1)
def test_score_has_floor():
    assert score_for_guess(-10,1)>=10
