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
