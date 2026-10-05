import unittest
from schemas.models import CandidateProfile
from source_facts import refine


class SourceRepairTests(unittest.TestCase):
    def test_existing_company_not_changed_to_other_employer(self):
        for separator in ['|','\u2013','\u2014','-']:
            p=CandidateProfile(full_name='Mira',experience=[{'company':'Acme','role':'Engineer','start_date':'2010','end_date':'2012'}, {'company':'Acme 2','role':'Engineer','start_date':'2020','end_date':'2024'}])
            refine(p,f'Engineer {separator} Acme\n2010 - 2012\nEngineer | Acme 2\n2020 - 2024')
            self.assertEqual(p.experience[0].company,'Acme')
            self.assertEqual(p.experience[0].start_date,'2010')

    def test_numeric_achievement_is_not_date_range(self):
        p=CandidateProfile(full_name='Mira',experience=[{'company':'Acme','role':'Engineer','start_date':'2010','end_date':'2012'}])
        refine(p,'Engineer | Acme\nProcessed 2000 - 3000 requests\n2010 - 2012')
        self.assertEqual(p.experience[0].start_date,'2010')
        self.assertEqual(p.experience[0].end_date,'2012')

    def test_degree_requires_local_nonconflicting_source(self):
        for source in ['Another Academy\nDiploma in Computing\n\n\n\nAcademy', 'Academy\nDiploma in Computing']:
            p=CandidateProfile(full_name='Mira',education=[{'institution':'Academy','degree':'MSc','field_of_study':'Diploma in Computing'}])
            self.assertEqual(refine(p,source),[])

    def test_alias_restored_only_from_exact_name_line(self):
        p=CandidateProfile(full_name='มณี ทดสอบ')
        changes=refine(p,'มณี ทดสอบ (Manee Test)\nPython')
        self.assertEqual(p.full_name,'มณี ทดสอบ (Manee Test)')
        self.assertEqual(changes[0]['source'],p.full_name)
        p=CandidateProfile(full_name='Mira')
        self.assertEqual(refine(p,'Mira is a developer\nMira (one)\nMira (two)'),[])

    def test_company_suffix_and_dates_preserve_printed_spelling(self):
        p=CandidateProfile(full_name='Mira',experience=[{'company':'Example Team','role':'Engineer','start_date':'2021-01-01','end_date':'Present'}])
        refine(p,'Mira\nEngineer | Example Team 7\nม.ค. 2561 – ปัจจุบัน')
        self.assertEqual(p.experience[0].company,'Example Team 7')
        self.assertEqual(p.experience[0].start_date,'ม.ค. 2561')
        self.assertEqual(p.experience[0].end_date,'ปัจจุบัน')

    def test_absent_dates_not_taken_from_next_job(self):
        p=CandidateProfile(full_name='Mira',experience=[{'company':'Alpha','role':'Engineer'}, {'company':'Beta','role':'Intern'}])
        refine(p,'Engineer\nAlpha\nBeta\nIntern\n2018 - 2019')
        self.assertIsNone(p.experience[0].start_date)

    def test_missing_degree_repaired_from_combined_source_field(self):
        p=CandidateProfile(full_name='Mira',education=[{'institution':'Academy','field_of_study':'Diploma in Computing'}])
        refine(p,'Academy\nDiploma in Computing')
        self.assertEqual(p.education[0].degree,'Diploma')
        self.assertEqual(p.education[0].field_of_study,'Computing')

    def test_degree_not_repaired_from_unsupported_model_text(self):
        p=CandidateProfile(full_name='Mira',education=[{'institution':'Academy','degree':'Master of Science in Chemistry'}])
        self.assertEqual(refine(p,'Academy'),[])


if __name__=='__main__':unittest.main()
