import json
import tempfile
import unittest
from pathlib import Path

from evaluate_models import cer, extraction_metrics, read_records


class EvaluationTests(unittest.TestCase):
    def test_invented_achievements_are_not_grounded(self):
        truth={'full_name':'Mira','skills':[],'experience':[{'company':'Example','role':'Engineer'}]}
        profile={**truth,'experience':[{'company':'Example','role':'Engineer','achievements':['Invented revenue claim']}]}
        scores=extraction_metrics(profile,truth,'Mira Engineer Example')
        self.assertLess(scores['literal_evidence_rate'],1)
        self.assertIn('Invented revenue claim',scores['unmatched_facts'])

    def test_extra_job_reduces_record_precision(self):
        truth={'full_name':'Mira','skills':[],'experience':[{'company':'Example'}]}
        profile={**truth,'experience':[{'company':'Example'},{'company':'Other'}]}
        self.assertEqual(extraction_metrics(profile,truth,'Mira Example Other')['record_precision'],.5)

    def test_multiple_roles_at_same_company_match_once_each(self):
        truth={'full_name':'Mira','skills':[],'experience':[{'company':'Example','role':'Junior'},{'company':'Example','role':'Senior'}]}
        profile={**truth,'experience':list(reversed(truth['experience']))}
        metrics=extraction_metrics(profile,truth,'Mira Example Junior Senior')
        self.assertEqual(metrics['record_precision'],1)
        self.assertEqual(metrics['employment_education_exact'],1)

    def test_torn_append_recovered(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'attempts.jsonl'
            row={'model':'test','sample_id':'one'}
            path.write_bytes((json.dumps(row)+'\n{"model":').encode())
            self.assertEqual(read_records(path),[row])
            self.assertEqual(read_records(path),[row])

    def test_completed_corruption_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'attempts.jsonl'
            path.write_text('broken\n')
            with self.assertRaises(json.JSONDecodeError): read_records(path)

    def test_cer_counts_substitution(self):
        self.assertEqual(cer('abc','axc'),1/3)
        self.assertEqual(cer('สมชาย','สมชาย'),0)


if __name__=='__main__': unittest.main()
