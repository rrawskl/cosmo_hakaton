def recommend(windows):
    if len(windows) < 2:
        return dict(
            status="insufficient_data",
            winner=None,
            reason="Горизонт 0 минут: доступно одно начало. Для сравнения расширьте период поиска.",
        )
    if any(
        any(f["status"] == "insufficient_data" for f in w["factors"]) for w in windows
    ):
        return dict(
            status="insufficient_data",
            winner=None,
            reason="Критичные данные неполны хотя бы для одного окна. Уверенный выбор невозможен; отдельные воздействия показаны в сравнении.",
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
        )
    i = indices[0]
    return dict(
        status="adverse" if best[0] else "preferred",
        winner=i,
        reason=f"Окно {i + 1}: меньше пересечений по порядку adverse → длительность adverse → attention. Это сравнение внешних воздействий, не разрешение ВКД.",
        decisive_factors=windows[i]["factors"],
    )
