from backend.app.recommendation import recommend


def synthetic_window(status, minutes=0):
    return {
        "factors": [
            dict(
                mechanism="space_weather",
                status=status,
                adverse_minutes=minutes,
                attention_minutes=0,
            )
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
    result = recommend(
        [synthetic_window("insufficient_data")] * 2,
        {"status": "OK", "internal_status": "NORMAL"},
    )
    assert result["status"] == "partial_assessment"
    assert result["window_status"] == "unknown" and result["winner"] is None
