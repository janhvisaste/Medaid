from celery import shared_task
from .models import MedicalReport, MedicalTest, AbnormalResult
from .report_processor import get_report_processor
from .report_generator import summarize_medical_report_with_llm

@shared_task
def process_medical_report_task(report_id, gender, age):
    try:
        report = MedicalReport.objects.get(id=report_id)
        
        # Read file bytes directly from storage to not clog memory on upload
        file_bytes = report.file.read()
        file_type_str = 'pdf' if 'pdf' in report.file_type else 'image'
        
        processor = get_report_processor()
        result = processor.process_report(file_bytes, file_type_str, gender, age)
        
        if not result.get('success'):
            report.status = 'failed'
            report.save()
            return
            
        extracted_text = result.get('extracted_text', '')
        llm_summary = None
        if extracted_text:
            llm_summary = summarize_medical_report_with_llm(extracted_text)
            
        structured_data = result.get('structured_data', {})
        if llm_summary and llm_summary.get('success'):
            structured_data['llm_summary'] = llm_summary.get('summary', '')
            structured_data['llm_key_findings'] = llm_summary.get('key_findings', [])
            structured_data['llm_abnormalities'] = llm_summary.get('abnormalities', [])
            structured_data['llm_risk_indicators'] = llm_summary.get('risk_indicators', [])
            structured_data['llm_suggested_focus'] = llm_summary.get('suggested_focus', '')
            
        report.extracted_text = extracted_text
        report.structured_data = structured_data
        report.status = 'completed'
        report.save()
        
        # Save medical tests and abnormal results
        for param, value in result.get('structured_data', {}).items():
            interpretation = result.get('interpretations', {}).get(param, {})
            
            test = MedicalTest.objects.create(
                medical_report=report,
                test_name=param.replace('_', ' ').title(),
                test_value=value,
                test_unit=interpretation.get('unit', ''),
                reference_range=f"{interpretation.get('normal_range', ['', ''])[0]} - {interpretation.get('normal_range', ['', ''])[1]}",
                is_abnormal=interpretation.get('status') != 'Normal'
            )
            
            if interpretation.get('status') != 'Normal':
                AbnormalResult.objects.create(
                    medical_test=test,
                    status=interpretation.get('status', 'Unknown'),
                    concern_level=interpretation.get('concern_level', 'Low'),
                    interpretation=interpretation.get('interpretation', '')
                )
    except Exception as e:
        print(f"Task failed: {e}")
        try:
            r = MedicalReport.objects.get(id=report_id)
            r.status = 'failed'
            r.save()
        except:
            pass
