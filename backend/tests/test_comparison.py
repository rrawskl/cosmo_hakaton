from scripts.compare_historical import compare_case


def test_real_storm_comparison_matches_published_bins():
    case = compare_case("storm.txt")
    assert case["cutoff"] == "2024-05-10T12:30:00+00:00"
    assert [w["kp_max"] for w in case["windows"]] == [4.33, 5.33, 8.33]
    assert [w["kp_ge5_minutes"] for w in case["windows"]] == [0, 240, 360]
    assert all(w["s1_probability_max"] == 55 for w in case["windows"])
    assert case["recommendation"]["status"] == "equal"


def test_real_control_is_quiet_only_for_kp():
    case = compare_case("quiet.txt")
    assert all(w["kp_ge5_minutes"] == 0 for w in case["windows"])
    assert all(w["weather_status"] == "attention" for w in case["windows"])
    assert all(w["s1_probability_max"] == 5 for w in case["windows"])
