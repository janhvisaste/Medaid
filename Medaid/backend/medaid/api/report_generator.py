# report_generator.py - PDF Report Generation
"""
Generate professional PDF medical reports from triage assessments
Migrated from oldMedaidfiles/report_generator.py
"""

import os
from io import BytesIO
from datetime import datetime
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from django.conf import settings


def generate_assessment_pdf(triage_record, user, user_profile=None):
    """
    Generate a comprehensive PDF report for a triage assessment
    
    Args:
        triage_record: TriageRecord instance
        user: User instance
        user_profile: UserProfile instance (optional)
    
    Returns:
        BytesIO object containing the PDF
    """
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter,
                           rightMargin=72, leftMargin=72,
                           topMargin=72, bottomMargin=18)
    
    # Container for the 'Flowable' objects
    elements = []
    
    # Define styles
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='Center', alignment=TA_CENTER))
    styles.add(ParagraphStyle(name='Right', alignment=TA_RIGHT, fontSize=10))
    styles.add(ParagraphStyle(name='SubHeading', fontSize=14, textColor=colors.HexColor('#2c3e50'), 
                             spaceAfter=12, spaceBefore=12, fontName='Helvetica-Bold'))
    
    # Title
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#2c3e50'),
        spaceAfter=30,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    )
    
    elements.append(Paragraph("MEDAID HEALTH ASSESSMENT REPORT", title_style))
    elements.append(Spacer(1, 12))
    
    # Report metadata
    meta_data = [
        ['Report Date:', datetime.now().strftime('%B %d, %Y at %I:%M %p')],
        ['Assessment ID:', f'#{triage_record.id}'],
        ['Assessment Date:', triage_record.created_at.strftime('%B %d, %Y at %I:%M %p')],
    ]
    
    meta_table = Table(meta_data, colWidths=[2*inch, 4*inch])
    meta_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    elements.append(meta_table)
    elements.append(Spacer(1, 20))
    
    # Patient Information Section
    elements.append(Paragraph("PATIENT INFORMATION", styles['SubHeading']))
    
    patient_data = [
        ['Name:', f"{user.first_name} {user.last_name}"],
        ['Email:', user.email],
    ]
    
    if user_profile:
        if user_profile.date_of_birth:
            from datetime import date
            today = date.today()
            age = today.year - user_profile.date_of_birth.year - (
                (today.month, today.day) < (user_profile.date_of_birth.month, user_profile.date_of_birth.day)
            )
            patient_data.append(['Age:', f"{age} years"])
        if user_profile.gender:
            patient_data.append(['Gender:', user_profile.gender.capitalize()])
        if user_profile.phone:
            patient_data.append(['Phone:', user_profile.phone])
    
    patient_table = Table(patient_data, colWidths=[2*inch, 4*inch])
    patient_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LINEBELOW', (0, -1), (-1, -1), 1, colors.grey),
    ]))
    elements.append(patient_table)
    elements.append(Spacer(1, 20))
    
    # Chief Complaint Section
    elements.append(Paragraph("CHIEF COMPLAINT", styles['SubHeading']))
    symptoms_text = Paragraph(triage_record.current_symptoms or "Not specified", styles['Normal'])
    elements.append(symptoms_text)
    elements.append(Spacer(1, 20))
    
    # Assessment Results Section
    elements.append(Paragraph("ASSESSMENT RESULTS", styles['SubHeading']))
    
    # Risk Level with color coding
    risk_colors = {
        'emergency': colors.red,
        'high': colors.orange,
        'medium': colors.yellow,
        'low': colors.green
    }
    risk_color = risk_colors.get(triage_record.risk_level.lower(), colors.grey)
    
    assessment_data = [
        ['Risk Level:', triage_record.risk_level.upper()],
        ['Confidence:', f"{int(triage_record.confidence * 100)}%"],
        ['Assessment Source:', triage_record.assessment_source.replace('_', ' ').title()],
    ]
    
    assessment_table = Table(assessment_data, colWidths=[2*inch, 4*inch])
    assessment_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TEXTCOLOR', (1, 0), (1, 0), risk_color),
        ('FONTNAME', (1, 0), (1, 0), 'Helvetica-Bold'),
    ]))
    elements.append(assessment_table)
    elements.append(Spacer(1, 12))
    
    # Clinical Reasoning
    elements.append(Paragraph("Clinical Reasoning:", styles['Heading3']))
    reasoning_text = Paragraph(triage_record.reasoning or "Assessment completed", styles['Normal'])
    elements.append(reasoning_text)
    elements.append(Spacer(1, 20))
    
    # Possible Conditions
    conditions = triage_record.possible_conditions.all()
    if conditions:
        elements.append(Paragraph("POSSIBLE CONDITIONS", styles['SubHeading']))
        condition_data = [['Condition', 'Confidence']]
        for condition in conditions:
            condition_data.append([
                condition.disease_name,
                f"{int(condition.confidence * 100)}%"
            ])
        
        condition_table = Table(condition_data, colWidths=[4*inch, 2*inch])
        condition_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3498db')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.grey),
        ]))
        elements.append(condition_table)
        elements.append(Spacer(1, 20))
    
    # Recommendations
    recommendations = triage_record.recommendations.all().order_by('priority')
    if recommendations:
        elements.append(Paragraph("RECOMMENDATIONS", styles['SubHeading']))
        
        for idx, rec in enumerate(recommendations, 1):
            rec_text = f"{idx}. {rec.description}"
            elements.append(Paragraph(rec_text, styles['Normal']))
            elements.append(Spacer(1, 6))
        
        elements.append(Spacer(1, 20))
    
    # Past Medical History
    if user_profile and user_profile.past_history:
        conditions_list = user_profile.past_history.get('conditions', [])
        if conditions_list:
            elements.append(Paragraph("PAST MEDICAL HISTORY", styles['SubHeading']))
            history_text = ", ".join(conditions_list)
            elements.append(Paragraph(history_text, styles['Normal']))
            elements.append(Spacer(1, 20))
    
    # Disclaimer
    elements.append(Spacer(1, 30))
    disclaimer_style = ParagraphStyle(
        'Disclaimer',
        parent=styles['Normal'],
        fontSize=8,
        textColor=colors.grey,
        alignment=TA_CENTER
    )
    disclaimer = """
    <b>IMPORTANT DISCLAIMER:</b><br/>
    This assessment is generated by an AI-powered system and should not be considered as a 
    substitute for professional medical advice, diagnosis, or treatment. Always seek the 
    advice of your physician or other qualified health provider with any questions you may 
    have regarding a medical condition. Never disregard professional medical advice or 
    delay in seeking it because of something you have read in this report.
    """
    elements.append(Paragraph(disclaimer, disclaimer_style))
    
    # Footer
    footer_text = f"Generated by Medaid Health Assistant | Report ID: {triage_record.id}"
    elements.append(Spacer(1, 12))
    elements.append(Paragraph(footer_text, styles['Right']))
    
    # Build PDF
    doc.build(elements)
    
    # Get the value of the BytesIO buffer
    pdf_value = buffer.getvalue()
    buffer.close()
    
    return pdf_value


def generate_health_passport_pdf(user, user_profile, triage_records, medical_reports):
    """
    Generate comprehensive health passport PDF with full medical history
    
    Args:
        user: User instance
        user_profile: UserProfile instance
        triage_records: QuerySet of TriageRecord instances
        medical_reports: QuerySet of MedicalReport instances
    
    Returns:
        BytesIO object containing the PDF
    """
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter,
                           rightMargin=72, leftMargin=72,
                           topMargin=72, bottomMargin=18)
    
    elements = []
    styles = getSampleStyleSheet()
    
    # Title
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#2c3e50'),
        spaceAfter=30,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    )
    
    elements.append(Paragraph("MEDAID HEALTH PASSPORT", title_style))
    elements.append(Paragraph(f"Patient: {user.first_name} {user.last_name}", styles['Center']))
    elements.append(Spacer(1, 30))
    
    # Patient Summary
    elements.append(Paragraph("PATIENT SUMMARY", styles['Heading2']))
    elements.append(Paragraph(f"Total Consultations: {triage_records.count()}", styles['Normal']))
    elements.append(Paragraph(f"Medical Reports Uploaded: {medical_reports.count()}", styles['Normal']))
    elements.append(Spacer(1, 20))
    
    # Recent Assessments
    elements.append(Paragraph("RECENT ASSESSMENTS", styles['Heading2']))
    for record in triage_records[:5]:
        elements.append(Paragraph(
            f"<b>{record.created_at.strftime('%B %d, %Y')}</b> - {record.risk_level.upper()} Risk",
            styles['Normal']
        ))
        elements.append(Paragraph(f"Symptoms: {record.current_symptoms[:100]}...", styles['Normal']))
        elements.append(Spacer(1, 10))
    
    # Build PDF
    doc.build(elements)
    
    pdf_value = buffer.getvalue()
    buffer.close()
    
    return pdf_value
