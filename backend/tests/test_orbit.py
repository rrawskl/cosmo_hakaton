import json
from pathlib import Path
from datetime import timedelta
import numpy as np
from backend.app.orbit import propagate, select_elements, in_shadow
from backend.app.schemas import utc

FIX = Path(__file__).parent / "fixtures"


def test_real_omm_iss_geometry():
    element = json.loads((FIX / "celestrak_gp.txt").read_text())[0]
    start = utc(element["EPOCH"])
    result = propagate(element, start, start + timedelta(hours=2))
    assert len(result["points"]) == 121
    assert all(
        350 < p["altitude_km"] < 500 and abs(p["lat"]) < 52 for p in result["points"]
    )
    assert {x["state"] for x in result["intervals"]} == {"sunlight", "shadow"}
    assert result["intervals"][0]["start"] == start.isoformat()
    assert result["intervals"][-1]["end"] == (start + timedelta(hours=2)).isoformat()


def test_vallado_published_sgp4_verification_point():
    # Vallado et al. verification satellite 00005, sgp4 package verification TLE.
    from sgp4.api import Satrec

    sat = Satrec.twoline2rv(
        "1 00005U 58002B   00179.78495062  .00000023  00000-0  28098-4 0  4753",
        "2 00005  34.2682 348.7242 1859667 331.7664  19.3264 10.82419157413667",
    )
    error, r, v = sat.sgp4(sat.jdsatepoch, sat.jdsatepochF)
    assert error == 0
    np.testing.assert_allclose(
        r, [7022.46529266, -1400.08296755, 0.03995155], atol=1e-7
    )


def test_synthetic_shadow_boundaries():
    assert bool(in_shadow([-7000, 0, 0], [1e8, 0, 0]))
    assert not bool(in_shadow([7000, 0, 0], [1e8, 0, 0]))
    assert not bool(in_shadow([-7000, 7000, 0], [1e8, 0, 0]))


def test_synthetic_creation_date_cutoff():
    base = dict(NORAD_CAT_ID=25544, EPOCH="2024-05-10T00:00:00Z")
    late = {**base, "CREATION_DATE": "2024-05-11T00:00:00Z"}
    early = {**base, "CREATION_DATE": "2024-05-10T01:00:00Z"}
    at = utc("2024-05-10T12:00:00Z")
    assert select_elements([late, early, base], at, at) == early
    assert select_elements([late, base], at, at) is None
    assert select_elements([early], at + timedelta(days=4)) is None
