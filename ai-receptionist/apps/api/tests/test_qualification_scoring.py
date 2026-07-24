from app.modules.conversation.qualification import score_answer


def test_boolean_true_scores() -> None:
    config = {"scoring": {"true": 30, "false": 0}}
    assert score_answer(config, True) == 30
    assert score_answer(config, False) == 0


def test_choice_scoring_matches_lowercased_key() -> None:
    config = {"scoring": {"has_deadline": 30}}
    assert score_answer(config, "has_deadline") == 30
    assert score_answer(config, "HAS_DEADLINE") == 30


def test_unmatched_answer_scores_zero() -> None:
    config = {"scoring": {"true": 30}}
    assert score_answer(config, "something else") == 0


def test_no_scoring_config_scores_zero() -> None:
    assert score_answer({}, True) == 0
    assert score_answer({"question": "What happened?"}, "a long free-text answer") == 0
