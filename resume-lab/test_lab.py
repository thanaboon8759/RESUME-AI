import io
import json
import unittest
from unittest.mock import patch

from server import ScanError, atomic_skills, ocr_image, parse_document, scan


class ResumeLabTests(unittest.TestCase):
    def test_grouped_skill_lists_are_split_without_new_terms(self):
        self.assertEqual(atomic_skills(['Tools: Git, Docker', 'Python; C++', 'Docker']), ['Git','Docker','Python','C++'])
        self.assertEqual(atomic_skills(['ISO 9001:2015','C++ std::vector']),['ISO 9001:2015','C++ std::vector'])

    def test_utf8_thai_preview_never_calls_model(self):
        with patch('server.ollama') as api:
            result = scan('resume.txt', 'สมชาย Python'.encode(), parse_only=True)
        api.assert_not_called()
        self.assertEqual(result['source_text'], 'สมชาย Python')
        self.assertIsNone(result['profile'])
        self.assertIsNone(result['schema_valid'])

    def test_invalid_model_output_never_creates_candidate(self):
        with patch('server.ollama', return_value={'message': {'content': '{}'}}):
            with self.assertRaisesRegex(ScanError, 'schema validation'):
                scan('resume.txt', b'Mira Python', model='test')

    def test_ocr_preview_records_model_without_creating_profile(self):
        with patch('server.parse_document', return_value=('Mira Python', 'Image OCR')):
            result = scan('resume.png', b'fixture', ocr_model='ocr-fixture', parse_only=True)
        self.assertTrue(result['ocr_used'])
        self.assertEqual(result['ocr_model'], 'ocr-fixture')
        self.assertIsNone(result['profile'])

    def test_typhoon_json_wrapper_is_unwrapped(self):
        with patch('server.ollama', return_value={'message': {'content': '{"text":"Mira Python"}'}}):
            self.assertEqual(ocr_image(b'fixture', 'ocr-fixture'), 'Mira Python')

    def test_natural_text_wrapper_and_ocr_budget(self):
        with patch('server.ollama', return_value={'message': {'content': json.dumps({'natural_text':'สมชาย\nPython'})}}) as api:
            self.assertEqual(ocr_image(b'fixture','ocr-fixture'), 'สมชาย\nPython')
        self.assertEqual(api.call_args.args[1]['options']['num_ctx'],8192)

    def test_truncated_ocr_is_not_success(self):
        for response in [{'message':{'content':'{"natural'}},
                         {'message':{'content':'Mira'},'done_reason':'length'},
                         {'message':{'content':'{"unexpected":"Mira"}'}}]:
            with self.subTest(response=response), patch('server.ollama',return_value=response):
                with self.assertRaises(ScanError):
                    ocr_image(b'fixture','ocr-fixture')

    def test_scanned_pdf_renders_before_ocr(self):
        from PIL import Image
        document = io.BytesIO()
        Image.new('RGB', (200, 200), 'white').save(document, format='PDF')
        with patch('server.ocr_image', return_value='Thai resume transcription') as ocr:
            text, route = parse_document('scan.pdf', document.getvalue(), 'vision-model')
        self.assertEqual(text, 'Thai resume transcription')
        self.assertEqual(route, 'PDF text + OCR')
        self.assertTrue(ocr.call_args.args[0].startswith(b'\x89PNG'))

    def test_model_failure_propagates(self):
        with patch('server.ollama', side_effect=ScanError('offline')):
            with self.assertRaisesRegex(ScanError, 'offline'):
                scan('resume.txt', b'Mira Python', model='test')

    def test_live_result_is_validated_and_inferences_removed(self):
        response = {'message': {'content': json.dumps({'full_name': 'Mira', 'contact_email':None,'contact_phone':None,'languages':[],'skills': ['Python','Rust'],'experience':[],'education':[]})}}
        with patch('server.ollama', return_value=response):
            result = scan('resume.txt', b'Mira Python', model='fixture')
        self.assertTrue(result['schema_valid'])
        self.assertEqual(result['profile']['implicit_skills'], [])
        self.assertIsNone(result['profile']['extraction_confidence'])
        self.assertEqual(result['skill_evidence'], [{'skill':'Python','literal_match':True},{'skill':'Rust','literal_match':False}])

    def test_incomplete_profile_is_not_schema_valid(self):
        with patch('server.ollama',return_value={'message':{'content':'{"full_name":"Mira"}'}}):
            with self.assertRaisesRegex(ScanError,'schema validation'):
                scan('resume.txt',b'Mira',model='fixture')

    def test_empty_and_unsupported_files_rejected(self):
        for name, data in [('empty.txt',b''),('bad.exe',b'abc'),('fake.pdf',b'not a PDF')]:
            with self.subTest(name=name), self.assertRaises(ScanError):
                parse_document(name,data)

    def test_large_text_rejected_without_truncation(self):
        with self.assertRaisesRegex(ScanError, '60,000'):
            parse_document('long.txt', b'a' * 60001)

    def test_docx_table_text_is_preserved(self):
        from docx import Document
        doc = Document(); doc.add_paragraph('Mira')
        doc.add_table(rows=1, cols=1).cell(0,0).text = 'Python'
        content = io.BytesIO(); doc.save(content)
        text, _ = parse_document('resume.docx', content.getvalue())
        self.assertIn('Mira', text); self.assertIn('Python', text)

    def test_digital_pdf(self):
        from reportlab.pdfgen import canvas
        content = io.BytesIO(); pdf = canvas.Canvas(content)
        pdf.drawString(50,700,'Mira Example - Python SQL Docker - Software Engineer at Example Studio 2022 to 2025')
        pdf.save()
        text, route = parse_document('resume.pdf', content.getvalue())
        self.assertIn('Python',text); self.assertEqual(route,'Text extraction')


if __name__ == '__main__':
    unittest.main()
