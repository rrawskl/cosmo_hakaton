"""SGP4 TEME -> ITRS/WGS84; geocentric Sun transformed to TEME.

Eclipse uses a cylindrical Earth umbra, no penumbra/refraction. Sampling bounds
transition accuracy to 60 s. Illumination is a work condition, never a risk score.
"""

from datetime import timedelta
import numpy as np
from sgp4.api import Satrec
from sgp4 import omm
from astropy import units as u
from astropy.coordinates import (
    TEME,
    ITRS,
    CartesianRepresentation,
    get_sun,
    EarthLocation,
)
from astropy.time import Time
from astropy.utils import iers
from .schemas import utc

iers.conf.auto_download = False
iers.conf.auto_max_age = None


def select_elements(elements, at, cutoff=None):
    candidates = [
        e
        for e in elements
        if int(e.get("NORAD_CAT_ID", 0)) == 25544
        and utc(e["EPOCH"]) <= at
        and abs((at - utc(e["EPOCH"])).total_seconds()) <= 3 * 86400
        and (
            cutoff is None
            or (e.get("CREATION_DATE") and utc(e["CREATION_DATE"]) <= cutoff)
        )
    ]
    return max(candidates, key=lambda e: utc(e["EPOCH"])) if candidates else None


def in_shadow(position, sun):
    r, s = np.asarray(position), np.asarray(sun)
    direction = s / np.linalg.norm(s, axis=-1, keepdims=True)
    projection = np.sum(r * direction, axis=-1)
    distance = np.linalg.norm(r - projection[..., None] * direction, axis=-1)
    return (projection < 0) & (distance < 6378.137)


def propagate(element, start, end, step=60):
    if (
        max(
            abs((start - utc(element["EPOCH"])).total_seconds()),
            abs((end - utc(element["EPOCH"])).total_seconds()),
        )
        > 3 * 86400
    ):
        raise ValueError("Элементы удалены от окна более чем на 72 часа")
    fields = dict(element)
    fields.update(
        CENTER_NAME="EARTH",
        REF_FRAME="TEME",
        TIME_SYSTEM="UTC",
        MEAN_ELEMENT_THEORY="SGP4",
    )
    satellite = Satrec()
    omm.initialize(satellite, fields)
    dates = [
        start + timedelta(seconds=s)
        for s in range(0, int((end - start).total_seconds()), step)
    ] + [end]
    times = Time(dates)
    errors, positions, velocities = satellite.sgp4_array(times.jd1, times.jd2)
    if np.any(errors):
        raise ValueError(f"SGP4 вернул коды ошибок {sorted(set(errors.tolist()))}")
    teme = TEME(CartesianRepresentation(positions.T * u.km), obstime=times)
    itrs = teme.transform_to(ITRS(obstime=times))
    geo = EarthLocation.from_geocentric(*itrs.cartesian.xyz).to_geodetic()
    sun = (
        get_sun(times).transform_to(TEME(obstime=times)).cartesian.xyz.to_value(u.km).T
    )
    shadows = in_shadow(positions, sun)
    points = [
        dict(
            time=t.isoformat(),
            lat=float(geo.lat.deg[i]),
            lon=float(geo.lon.deg[i]),
            altitude_km=float(geo.height.to_value(u.km)[i]),
            shadow=bool(shadows[i]),
        )
        for i, t in enumerate(dates)
    ]
    intervals = []
    for i in range(len(points) - 1):
        state = "shadow" if points[i]["shadow"] else "sunlight"
        if intervals and intervals[-1]["state"] == state:
            intervals[-1]["end"] = points[i + 1]["time"]
        else:
            intervals.append(
                dict(start=points[i]["time"], end=points[i + 1]["time"], state=state)
            )
    return dict(
        points=points,
        intervals=intervals,
        epoch=element["EPOCH"],
        element=element,
        step_seconds=step,
        coordinates="SGP4/WGS72 TEME → Astropy ITRS → WGS84",
        limitations=[
            "Цилиндрическая тень Земли, без полутени; точность переходов до 60 секунд.",
            "IERS из закреплённого astropy-iers-data, без сетевого обновления.",
            "Освещённость — условие работ; допустимый режим не задан, оценка опасности не выполняется.",
        ],
    )
