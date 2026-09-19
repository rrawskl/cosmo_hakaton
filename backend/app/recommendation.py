def recommend(windows, current_protons=None):
    critical = {"space_weather", "protons"}
    labels = {"space_weather": "Космическая погода", "protons": "Протонная обстановка"}
    initial = [f for f in windows[0]["factors"] if f["mechanism"] in critical]
    known = [f for f in initial if f["status"] != "insufficient_data"]
    summary = dict(
        window_status="adverse"
        if any(f["status"] == "adverse" for f in known)
        else "attention"
        if any(f["status"] == "attention" for f in known)
        else "favorable"
        if len(known) == len(initial)
        else "unknown",
        confidence="limited" if len(known) < len(initial) else "source_forecast",
        available_findings=[f"{labels[f['mechanism']]}: {f['status']}" for f in known],
        missing_factors=[
            labels[f["mechanism"]]
            for f in initial
            if f["status"] == "insufficient_data"
        ],
        current_proton_status=current_protons.get("internal_status")
        if current_protons and current_protons.get("status") == "OK"
        else None,
    )
    if any(
        any(
            f["mechanism"] in critical and f["status"] == "insufficient_data"
            for f in w["factors"]
        )
        for w in windows
    ):
        summary["confidence"] = "limited"
        return dict(
            status="partial_assessment"
            if known or summary["current_proton_status"]
            else "insufficient_data",
            winner=None,
            reason="Космическая погода или протонный прогноз неполны хотя бы для одного окна. Уверенный выбор невозможен; доступные воздействия показаны в сравнении.",
            **summary,
        )

    if len(windows) < 2:
        return dict(
            status="single_window",
            winner=None,
            reason="Исходное окно оценено. Для сравнения альтернатив увеличьте горизонт поиска.",
            **summary,
        )

    def score(w):
        factors = [f for f in w["factors"] if f["mechanism"] != "illumination"]
        return (
            any(f["status"] == "adverse" for f in factors),
            sum(f["adverse_minutes"] for f in factors),
            sum(f["attention_minutes"] for f in factors),
        )

    scores = [score(w) for w in windows]
    best = min(scores)
    indices = [i for i, s in enumerate(scores) if s == best]
    if len(indices) > 1:
        return dict(
            status="equal",
            winner=None,
            reason="Варианты равнозначны по доступным данным и правилам; искусственный победитель не выбран.",
            **summary,
        )
    i = indices[0]
    return dict(
        status="adverse" if best[0] else "preferred",
        winner=i,
        reason=f"Окно {i + 1}: меньше пересечений по порядку adverse → длительность adverse → attention. Это сравнение внешних воздействий, не разрешение ВКД.",
        decisive_factors=windows[i]["factors"],
        **summary,
    )
