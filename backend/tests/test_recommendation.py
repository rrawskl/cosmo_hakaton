from backend.app.recommendation import recommend


def synthetic_window(status, minutes=0):
    return {
        "factors": [
            dict(
                mechanism="space_weather",
                status=status,
                adverse_minutes=minutes,
                attention_minutes=0,
            ),
            dict(
                mechanism="protons",
                status="favorable",
                adverse_minutes=0,
                attention_minutes=0,
            ),
        ]
    }


def test_synthetic_tie():
    assert (
        recommend([synthetic_window("favorable"), synthetic_window("favorable")])[
            "status"
        ]
        == "equal"
    )


def test_synthetic_incomplete_cannot_win():
    assert (
        recommend(
            [synthetic_window("insufficient_data"), synthetic_window("adverse", 10)]
        )["winner"]
        is None
    )


def test_synthetic_adverse_cannot_be_compensated():
    assert (
        recommend([synthetic_window("adverse", 1), synthetic_window("attention")])[
            "winner"
        ]
        == 1
    )


def test_missing_illumination_does_not_block_available_result():
    windows = []
    for _ in range(2):
        windows.append(
            {
                "factors": [
                    dict(
                        mechanism="space_weather",
                        status="favorable",
                        adverse_minutes=0,
                        attention_minutes=0,
                    ),
                    dict(
                        mechanism="protons",
                        status="favorable",
                        adverse_minutes=0,
                        attention_minutes=0,
                    ),
                    dict(
                        mechanism="illumination",
                        status="insufficient_data",
                        adverse_minutes=0,
                        attention_minutes=0,
                    ),
                ]
            }
        )
    assert recommend(windows)["status"] == "equal"


def test_partial_result_reports_available_factor_without_picking_winner():
    missing = synthetic_window("insufficient_data")
    missing["factors"].append(
        dict(
            mechanism="protons",
            status="attention",
            adverse_minutes=0,
            attention_minutes=60,
        )
    )
    result = recommend([missing, missing])
    assert result["status"] == "partial_assessment"
    assert result["window_status"] == "attention"
    assert result["winner"] is None and result["missing_factors"]


def test_current_observation_does_not_claim_future_is_safe():
    missing = synthetic_window("insufficient_data")
    missing["factors"][1]["status"] = "insufficient_data"
    result = recommend(
        [missing] * 2,
        {"status": "OK", "internal_status": "NORMAL"},
    )
    assert result["status"] == "partial_assessment"
    assert result["window_status"] == "unknown" and result["winner"] is None


def test_two_best_are_not_all_equal():
    result = recommend(
        [
            synthetic_window("favorable"),
            synthetic_window("favorable"),
            synthetic_window("adverse", 60),
        ]
    )
    assert result["status"] == "tied_best"
    assert result["best_indices"] == [0, 1] and result["winner"] is None
    assert result["comparison_scores"][2]["adverse_factor_minutes"] == 60


def test_missing_mechanism_is_not_complete():
    w = synthetic_window("favorable")
    w["factors"].pop()
    result = recommend([w, w])
    assert result["status"] == "partial_assessment"
    assert result["window_status"] == "unknown"
    assert result["missing_factors"] == ["Протонная обстановка"]


def test_empty_windows_are_not_favorable():
    assert recommend([])["status"] == "insufficient_data"


def test_less_attention_selects_unique_winner():
    windows = [synthetic_window("attention") for _ in range(3)]
    for w, minutes in zip(windows, [60, 30, 90]):
        w["factors"][0]["attention_minutes"] = minutes
    result = recommend(windows)
    assert result["status"] == "preferred"
    assert result["winner"] == 1 and result["best_indices"] == [1]
