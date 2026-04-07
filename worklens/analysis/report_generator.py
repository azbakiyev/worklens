"""
Report Generator -- creates PDF automation discovery report.
Uses reportlab for PDF generation, no external dependencies.
"""
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict

logger = logging.getLogger(__name__)


def generate_report(
    suggestions: List[Dict],
    stats: Dict,
    company_name: str = "Компания",
    output_path: str = "",
    hourly_rate: float = 1500.0,
) -> str:
    """
    Generate PDF report with automation suggestions.
    Returns path to generated file.
    """
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.lib.colors import HexColor, white, black
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
            HRFlowable, KeepTogether
        )
        from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    except ImportError:
        return ""

    if not output_path:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = str(Path.home() / "Downloads" / f"WorkLens_Report_{ts}.pdf")

    GREEN  = HexColor("#4caf50")
    DARK   = HexColor("#1a1a1a")
    GRAY   = HexColor("#666666")
    LGRAY  = HexColor("#f5f6fa")
    RED    = HexColor("#ef5350")
    ORANGE = HexColor("#ff9800")

    doc = SimpleDocTemplate(
        output_path, pagesize=A4,
        leftMargin=2*cm, rightMargin=2*cm,
        topMargin=2*cm, bottomMargin=2*cm
    )

    styles = getSampleStyleSheet()
    h1  = ParagraphStyle("h1",  fontSize=22, textColor=GREEN, spaceAfter=4,  fontName="Helvetica-Bold")
    h2  = ParagraphStyle("h2",  fontSize=14, textColor=DARK,  spaceAfter=8,  spaceBefore=16, fontName="Helvetica-Bold")
    h3  = ParagraphStyle("h3",  fontSize=11, textColor=DARK,  spaceAfter=4,  fontName="Helvetica-Bold")
    body= ParagraphStyle("body",fontSize=10, textColor=GRAY,  spaceAfter=6,  leading=16)
    sm  = ParagraphStyle("sm",  fontSize=9,  textColor=GRAY,  spaceAfter=4)
    cen = ParagraphStyle("cen", fontSize=10, textColor=GRAY,  alignment=TA_CENTER)

    story = []

    # ── Cover ─────────────────────────────────────────────────────────────────
    story.append(Spacer(1, 1.5*cm))
    story.append(Paragraph("WorkLens", h1))
    story.append(Paragraph("Отчёт об автоматизации рабочих процессов", ParagraphStyle(
        "sub", fontSize=16, textColor=GRAY, spaceAfter=6
    )))
    story.append(Paragraph(company_name, ParagraphStyle(
        "co", fontSize=13, textColor=DARK, spaceAfter=4, fontName="Helvetica-Bold"
    )))
    story.append(Paragraph(
        datetime.now().strftime("%d %B %Y"),
        ParagraphStyle("dt", fontSize=11, textColor=GRAY, spaceAfter=20)
    ))
    story.append(HRFlowable(width="100%", thickness=2, color=GREEN, spaceAfter=24))

    # ── Executive Summary ─────────────────────────────────────────────────────
    total_hrs = sum(s.get("time_per_week_hours", 0) for s in suggestions)
    total_annual = sum(s.get("roi", {}).get("annual_cost_saved", 0) for s in suggestions)
    total_impl   = sum(s.get("roi", {}).get("implementation_cost", 0) for s in suggestions)

    story.append(Paragraph("Резюме", h2))

    summary_data = [
        ["Показатель", "Значение"],
        ["Выявлено возможностей автоматизации", str(len(suggestions))],
        ["Суммарная рутина в неделю", f"{total_hrs:.1f} часов"],
        ["Потенциальная экономия в год", f"{total_annual:,} тг".replace(",", " ")],
        ["Стоимость внедрения (оценка)", f"{total_impl:,} тг".replace(",", " ")],
        ["Срок окупаемости", f"{round(total_impl / max(total_annual/52, 1))} недель"],
    ]

    t = Table(summary_data, colWidths=[10*cm, 7*cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), GREEN),
        ("TEXTCOLOR",  (0,0), (-1,0), white),
        ("FONTNAME",   (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE",   (0,0), (-1,0), 10),
        ("BACKGROUND", (0,1), (-1,-1), LGRAY),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [white, LGRAY]),
        ("FONTSIZE",   (0,1), (-1,-1), 10),
        ("FONTNAME",   (0,1), (0,-1), "Helvetica-Bold"),
        ("TEXTCOLOR",  (1,1), (1,-1), DARK),
        ("ALIGN",      (1,0), (1,-1), "RIGHT"),
        ("GRID",       (0,0), (-1,-1), 0.5, HexColor("#e0e0e0")),
        ("ROWHEIGHT",  (0,0), (-1,-1), 22),
        ("LEFTPADDING",  (0,0), (-1,-1), 12),
        ("RIGHTPADDING", (0,0), (-1,-1), 12),
    ]))
    story.append(t)
    story.append(Spacer(1, 0.5*cm))

    # ── Data Overview ─────────────────────────────────────────────────────────
    if stats:
        story.append(Paragraph("Данные наблюдения", h2))
        days = stats.get("days_active", 0)
        total_ev = stats.get("total_events", 0)
        hrs_total = round(total_ev * 5 / 3600, 1)

        story.append(Paragraph(
            f"Собрано <b>{total_ev:,}</b> записей активности за <b>{days}</b> рабочих дней "
            f"(~{hrs_total}ч отслеживаемой работы). Анализ приложений:".replace(",", " "),
            body
        ))

        if stats.get("apps"):
            top_apps = stats["apps"][:6]
            total_app_ev = sum(a["events"] for a in top_apps)
            app_data = [["Приложение", "Категория", "Время", "% дня"]]
            for a in top_apps:
                hrs = round(a["events"] * 5 / 3600, 1)
                pct = round(a["events"] / max(total_ev, 1) * 100)
                app_data.append([a["name"], a.get("category",""), f"{hrs}ч", f"{pct}%"])

            at = Table(app_data, colWidths=[6*cm, 4*cm, 3*cm, 4*cm])
            at.setStyle(TableStyle([
                ("BACKGROUND", (0,0), (-1,0), DARK),
                ("TEXTCOLOR",  (0,0), (-1,0), white),
                ("FONTNAME",   (0,0), (-1,0), "Helvetica-Bold"),
                ("FONTSIZE",   (0,0), (-1,-1), 9),
                ("ROWBACKGROUNDS", (0,1), (-1,-1), [white, LGRAY]),
                ("GRID", (0,0), (-1,-1), 0.5, HexColor("#e0e0e0")),
                ("ROWHEIGHT", (0,0), (-1,-1), 20),
                ("LEFTPADDING", (0,0), (-1,-1), 10),
            ]))
            story.append(at)

    story.append(Spacer(1, 0.5*cm))

    # ── Suggestions ───────────────────────────────────────────────────────────
    story.append(Paragraph("Возможности автоматизации", h2))
    story.append(Paragraph(
        "Ниже представлены конкретные процессы, которые можно автоматизировать, "
        "отсортированные по объёму экономии.", body
    ))

    priority_colors = {"high": RED, "medium": ORANGE, "low": GREEN}
    priority_labels = {"high": "ВЫСОКИЙ", "medium": "СРЕДНИЙ", "low": "НИЗКИЙ"}

    for i, sg in enumerate(suggestions, 1):
        roi = sg.get("roi", {})
        pri = sg.get("priority", "medium")
        pri_color = priority_colors.get(pri, ORANGE)
        pri_label = priority_labels.get(pri, pri.upper())

        block = []
        # Title row
        title_data = [[
            Paragraph(f"{i}. {sg.get('title','')}", h3),
            Paragraph(f"● {pri_label}", ParagraphStyle(
                "pri", fontSize=9, textColor=pri_color, fontName="Helvetica-Bold",
                alignment=TA_RIGHT
            ))
        ]]
        tt = Table(title_data, colWidths=[13*cm, 4*cm])
        tt.setStyle(TableStyle([("VALIGN", (0,0), (-1,-1), "MIDDLE")]))
        block.append(tt)

        block.append(Paragraph(sg.get("description",""), body))
        block.append(Paragraph(
            f"<i>Доказательство:</i> {sg.get('evidence','')}",
            ParagraphStyle("ev", fontSize=9, textColor=GRAY, spaceAfter=8, leading=14)
        ))

        # ROI table
        roi_data = [
            ["Рутина/нед", "Экономия/год", "Внедрение", "Окупаемость", "Инструмент"],
            [
                f"{sg.get('time_per_week_hours',0):.1f}ч",
                f"{roi.get('annual_cost_saved',0):,}тг".replace(",", " "),
                f"{roi.get('implementation_cost',0):,}тг".replace(",", " "),
                f"{roi.get('payback_weeks',0)} нед",
                sg.get("automation_tool","")[:22],
            ]
        ]
        rt = Table(roi_data, colWidths=[2.5*cm, 3.5*cm, 3*cm, 3*cm, 5*cm])
        rt.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,0), HexColor("#e8f5e9")),
            ("FONTNAME",   (0,0), (-1,0), "Helvetica-Bold"),
            ("FONTSIZE",   (0,0), (-1,-1), 8),
            ("ALIGN",      (0,0), (-1,-1), "CENTER"),
            ("GRID",       (0,0), (-1,-1), 0.5, HexColor("#c8e6c9")),
            ("ROWHEIGHT",  (0,0), (-1,-1), 18),
            ("BACKGROUND", (0,1), (-1,1), HexColor("#f9fff9")),
            ("TEXTCOLOR",  (1,1), (1,1), GREEN),
            ("FONTNAME",   (1,1), (1,1), "Helvetica-Bold"),
        ]))
        block.append(rt)
        block.append(Spacer(1, 0.3*cm))
        block.append(HRFlowable(width="100%", thickness=0.5, color=HexColor("#e0e0e0"), spaceAfter=10))

        story.append(KeepTogether(block))

    # ── Footer ────────────────────────────────────────────────────────────────
    story.append(Spacer(1, 1*cm))
    story.append(HRFlowable(width="100%", thickness=1, color=GREEN, spaceAfter=8))
    story.append(Paragraph(
        f"Отчёт сгенерирован WorkLens · {datetime.now().strftime('%d.%m.%Y')} · "
        f"Данные хранятся локально на устройстве сотрудника",
        ParagraphStyle("foot", fontSize=8, textColor=GRAY, alignment=TA_CENTER)
    ))

    doc.build(story)
    logger.info(f"Report saved: {output_path}")
    return output_path
