"""
pdf_generator.py — Interview Report PDF Generator

Generates a professional PDF report for a completed interview session
using ReportLab. Includes metadata, per-question scores, and AI analysis.
"""

import io
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
)


def generate_interview_pdf(session):
    """
    Generate a PDF report for the given InterviewSession.
    Returns a BytesIO buffer containing the PDF.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        topMargin=25 * mm, bottomMargin=25 * mm,
        leftMargin=20 * mm, rightMargin=20 * mm,
    )

    styles = getSampleStyleSheet()

    # Custom styles
    styles.add(ParagraphStyle(
        'ReportTitle', parent=styles['Title'],
        fontSize=22, spaceAfter=6, textColor=colors.HexColor('#1e293b'),
    ))
    styles.add(ParagraphStyle(
        'SectionHead', parent=styles['Heading2'],
        fontSize=13, spaceBefore=16, spaceAfter=6,
        textColor=colors.HexColor('#475569'), borderPadding=(0, 0, 2, 0),
    ))
    styles.add(ParagraphStyle(
        'MetaText', parent=styles['Normal'],
        fontSize=9, textColor=colors.HexColor('#64748b'),
    ))
    styles.add(ParagraphStyle(
        'BodyText2', parent=styles['Normal'],
        fontSize=10, leading=14, textColor=colors.HexColor('#334155'),
    ))
    styles.add(ParagraphStyle(
        'QuestionText', parent=styles['Normal'],
        fontSize=10, leading=14, textColor=colors.HexColor('#1e293b'),
        fontName='Helvetica-Bold',
    ))
    styles.add(ParagraphStyle(
        'AnswerText', parent=styles['Normal'],
        fontSize=9, leading=13, textColor=colors.HexColor('#475569'),
        leftIndent=12,
    ))
    styles.add(ParagraphStyle(
        'FeedbackText', parent=styles['Normal'],
        fontSize=9, leading=12, textColor=colors.HexColor('#0369a1'),
        leftIndent=12,
    ))

    elements = []

    # ── Header ──────────────────────────────────────────
    elements.append(Paragraph('🎤 Mock Interview Report', styles['ReportTitle']))
    elements.append(Paragraph('AI Career Companion — Performance Analysis', styles['MetaText']))
    elements.append(Spacer(1, 8))
    elements.append(HRFlowable(width='100%', color=colors.HexColor('#e2e8f0'), thickness=1))
    elements.append(Spacer(1, 12))

    # ── Metadata Table ──────────────────────────────────
    avg_score = session.compute_average_score()
    duration_mins = round(session.time_used / 60, 1) if session.time_used else 'N/A'
    completed = session.completed_at.strftime('%B %d, %Y at %I:%M %p') if session.completed_at else 'Ongoing'

    meta_data = [
        ['Domain', session.domain, 'Date', completed],
        ['Total Questions', str(session.total_questions), 'Duration', f'{duration_mins} min'],
        ['Average Score', f'{avg_score}/10', 'Tab Switches', str(session.tab_switches)],
        ['Status', session.status.capitalize(), 'Session ID', f'#{session.pk}'],
    ]

    meta_table = Table(meta_data, colWidths=[90, 150, 90, 150])
    meta_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (2, 0), (2, -1), 'Helvetica-Bold'),
        ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#475569')),
        ('TEXTCOLOR', (2, 0), (2, -1), colors.HexColor('#475569')),
        ('TEXTCOLOR', (1, 0), (1, -1), colors.HexColor('#1e293b')),
        ('TEXTCOLOR', (3, 0), (3, -1), colors.HexColor('#1e293b')),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f8fafc')),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
        ('ROUNDEDCORNERS', [4, 4, 4, 4]),
    ]))
    elements.append(meta_table)
    elements.append(Spacer(1, 16))

    # ── Score Summary ───────────────────────────────────
    score_color = '#16a34a' if avg_score >= 7 else '#d97706' if avg_score >= 4 else '#dc2626'
    elements.append(Paragraph(
        f'Overall Average Score: <font color="{score_color}" size="16"><b>{avg_score}/10</b></font>',
        styles['SectionHead']
    ))
    elements.append(Spacer(1, 8))

    # ── Per-Question Breakdown ──────────────────────────
    responses = session.responses.all()
    if responses.exists():
        elements.append(Paragraph('📋 Question-by-Question Breakdown', styles['SectionHead']))
        elements.append(Spacer(1, 6))

        for resp in responses:
            sc = resp.score
            sc_color = '#16a34a' if sc >= 7 else '#d97706' if sc >= 4 else '#dc2626'

            elements.append(Paragraph(
                f'Q{resp.question_number}. {resp.question_text} '
                f'<font color="{sc_color}"><b>[{sc}/10]</b></font>',
                styles['QuestionText']
            ))

            answer_display = resp.answer_text if resp.answer_text else '<i>(No answer provided)</i>'
            elements.append(Paragraph(f'Answer: {answer_display}', styles['AnswerText']))

            if resp.feedback:
                elements.append(Paragraph(f'💬 {resp.feedback}', styles['FeedbackText']))

            if resp.strengths:
                elements.append(Paragraph(
                    f'✅ Strengths: {", ".join(resp.strengths)}',
                    styles['FeedbackText']
                ))

            if resp.improvements:
                elements.append(Paragraph(
                    f'💡 Improve: {", ".join(resp.improvements)}',
                    styles['FeedbackText']
                ))

            elements.append(Spacer(1, 10))

    # ── AI Analysis ─────────────────────────────────────
    if session.analysis_text:
        elements.append(Paragraph('📊 AI Performance Analysis', styles['SectionHead']))
        elements.append(Spacer(1, 6))

        # Split analysis into paragraphs for better formatting
        for paragraph in session.analysis_text.split('\n'):
            paragraph = paragraph.strip()
            if paragraph:
                elements.append(Paragraph(paragraph, styles['BodyText2']))
                elements.append(Spacer(1, 4))

    # ── Footer ──────────────────────────────────────────
    elements.append(Spacer(1, 20))
    elements.append(HRFlowable(width='100%', color=colors.HexColor('#e2e8f0'), thickness=1))
    elements.append(Spacer(1, 8))
    elements.append(Paragraph(
        'Generated by AI Career Companion — Mock Interview Module',
        styles['MetaText']
    ))

    doc.build(elements)
    buffer.seek(0)
    return buffer
