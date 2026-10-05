import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from automatic_scan import automatic_scan


class Error(Exception):pass


class PipelineTests(unittest.TestCase):
    def engine(self):
        inventory=[{'name':n,'digest':d*64,'capabilities':[c]} for n,d,c in [('extract','a','completion'),('ocr-one','b','vision'),('ocr-two','c','vision')]]
        policy={'id':'fixture','extraction':[{'name':'extract','digest':'a'*64}],
                'ocr':[{'name':'ocr-one','digest':'b'*64},{'name':'ocr-two','digest':'c'*64}]}
        engine=SimpleNamespace(ScanError=Error,ollama=Mock(return_value={'models':inventory}),
                               scan=Mock(return_value={'profile':{'full_name':'Mira','skills':['Python']},'schema_valid':True,'source_text':'Mira Python','warnings':[],'mode':'live'}))
        return engine,policy

    def test_ocr_fallback_keeps_actual_page_model_and_extracts_once(self):
        engine,policy=self.engine()
        def ocr(_,name):
            if name=='ocr-one':raise Error('unavailable')
            return 'Mira Python'
        engine.ocr_image=ocr
        engine.parse_document=lambda filename,data,ocr_runner:(ocr_runner(b'image'),'Image OCR')
        with patch('automatic_scan.load_policy',return_value=policy),patch('automatic_scan.engine_fingerprint',return_value='f'*64):
            result=automatic_scan(engine,'resume.png',b'image')
        self.assertEqual(result['ocr_model'],'ocr-two')
        self.assertEqual(result['filename'],'resume.png')
        self.assertEqual(result['ocr_pages'][0]['attempts'][0]['status'],'error')
        self.assertEqual(result['model'],'extract')
        engine.scan.assert_called_once_with('extracted.txt',b'Mira Python',model='extract')

    def test_text_preview_works_without_policy_or_ollama(self):
        engine,_=self.engine()
        engine.parse_document=lambda filename,data,ocr_runner:('Mira Python','Text extraction')
        with patch('automatic_scan.load_policy') as policy:
            result=automatic_scan(engine,'resume.txt',b'Mira Python',parse_only=True)
        policy.assert_not_called();engine.ollama.assert_not_called();engine.scan.assert_not_called()
        self.assertIsNone(result['profile'])


if __name__=='__main__':unittest.main()
