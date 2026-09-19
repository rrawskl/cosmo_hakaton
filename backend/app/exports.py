from io import BytesIO
import json
from pathlib import Path
from xml.sax.saxutils import escape
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont


def report(result):
    candidates = [
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("C:/Windows/Fonts/arial.ttf"),
    ]
    font = next((p for p in candidates if p.is_file()), None)
    if font is None:
        raise RuntimeError("Установите DejaVu Sans для кириллического PDF")
    if "Orbital" not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont("Orbital", str(font)))
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="BodyRU",
            fontName="Orbital",
            fontSize=9,
            leading=14,
            spaceAfter=7,
            wordWrap="CJK",
        )
    )
    styles.add(
        ParagraphStyle(
            name="TitleRU",
            fontName="Orbital",
            fontSize=21,
            leading=27,
            spaceAfter=18,
            textColor=colors.HexColor("#14324a"),
        )
    )
    styles.add(
        ParagraphStyle(
            name="HeadingRU",
            fontName="Orbital",
            fontSize=13,
            leading=18,
            spaceBefore=12,
            spaceAfter=8,
        )
    )
    content = []

    def p(text, style="BodyRU"):
        content.append(
            Paragraph(escape(str(text)).replace("\n", "<br/>"), styles[style])
        )

    p("ORBITAL RISK / Отчёт ВКД", "TitleRU")
    p(f"Расчёт {result['id']} • {result['created_at']} • UTC")
    p(f"Версия алгоритма: {result['algorithm_version']}")
    p(json.dumps(result["request"], ensure_ascii=False, indent=2))
    p("Рекомендация", "HeadingRU")
    p(result["recommendation"]["reason"])
    p("Статус: " + result["recommendation"]["status"])
    if result["recommendation"].get("best_indices"):
        p(
            "Лучшие по критериям окна: "
            + ", ".join(str(i + 1) for i in result["recommendation"]["best_indices"])
        )
    for i, score in enumerate(result["recommendation"].get("comparison_scores", [])):
        p(
            f"Окно {i + 1}, критерии сравнения (фактор-минуты, не вероятность риска): "
            + json.dumps(score, ensure_ascii=False)
        )
    if result["recommendation"].get("window_status"):
        p("Исходное окно: " + result["recommendation"]["window_status"])
        p("Уверенность: " + result["recommendation"]["confidence"])
        if result["recommendation"].get("current_proton_status"):
            p(
                "Протоны сейчас (наблюдения GOES): "
                + result["recommendation"]["current_proton_status"]
            )
        for finding in result["recommendation"].get("available_findings", []):
            p(finding)
        if result["recommendation"].get("missing_factors"):
            p("Нет покрытия: " + ", ".join(result["recommendation"]["missing_factors"]))
    for i, w in enumerate(result["windows"]):
        p(f"Окно {i + 1}: {w['start']} — {w['end']}", "HeadingRU")
        p(f"Продолжительность: {w['duration_minutes']} минут")
        for f in w["factors"]:
            p(f"{f['mechanism']}: {f['status']}", "HeadingRU")
            p(f["rule"])
            p(
                f"adverse: {f['adverse_minutes']} мин; attention: {f['attention_minutes']} мин; уверенность: {f['confidence']}"
            )
            for line in f["confidence_reasons"] + f["limitations"]:
                p(line)
            for interval in f["intervals"]:
                p(json.dumps(interval, ensure_ascii=False))
            for fact in f["facts"]:
                p(json.dumps(fact, ensure_ascii=False))
            p("Доказательства: " + ", ".join(f["evidence_ids"]))
    if result.get("protons"):
        snapshot = result["protons"]
        p("Протонная обстановка NOAA GOES (наблюдения)", "HeadingRU")
        p(
            f"{snapshot['status']} · {snapshot['internal_status']} · NOAA {snapshot['noaa_scale']['level']}"
        )
        p(snapshot["message"])
        p(json.dumps(snapshot["source"], ensure_ascii=False))
        p(f"Наблюдение: {snapshot['observed_at']}; получение: {snapshot['fetched_at']}")
        for name, channel in snapshot["channels"].items():
            p(
                name
                + ": "
                + json.dumps(
                    {k: v for k, v in channel.items() if k != "series"},
                    ensure_ascii=False,
                )
            )
        for reason in snapshot["reasons"]:
            p(reason)
    p("Орбита", "HeadingRU")
    if result["orbit"]:
        p(
            json.dumps(
                {k: v for k, v in result["orbit"].items() if k != "points"},
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        p("Недостаточно данных для траектории и света/тени.")
    p("Ограничения", "HeadingRU")
    for line in result["limitations"]:
        p(line)
    p("Наблюдения — отдельно от прогноза", "HeadingRU")
    for observation in result.get("observations", []):
        p(json.dumps(observation, ensure_ascii=False))
    p("Сообщения NOAA", "HeadingRU")
    for warning in result.get("warnings", []):
        p(json.dumps(warning, ensure_ascii=False))
    p("Источники и версии", "HeadingRU")
    for e in result["evidence"]:
        p(json.dumps(e, ensure_ascii=False, indent=2))
    output = BytesIO()

    def footer(canvas, doc):
        canvas.setFont("Orbital", 8)
        canvas.drawString(40, 25, f"Orbital Risk • {result['id']} • {doc.page}")

    SimpleDocTemplate(
        output,
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=45,
        title="Orbital Risk",
        author="Orbital Risk",
    ).build(content, onFirstPage=footer, onLaterPages=footer)
    return output.getvalue()
