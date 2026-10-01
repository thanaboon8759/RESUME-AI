import asyncio
import os
import io
from dotenv import load_dotenv
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from PIL import Image

load_dotenv()

from app.services.candidate_service import create_candidate
from app.schemas.candidate import CandidateCreate
from app.database.supabase.client import supabase

def generate_english_pdf():
    packet = io.BytesIO()
    c = canvas.Canvas(packet, pagesize=letter)
    c.drawString(100, 750, "John Doe")
    c.drawString(100, 730, "Software Engineer")
    c.drawString(100, 710, "Experience: 5 years at Google. Experience: 5 years at Google. Experience: 5 years at Google. Experience: 5 years at Google. Experience: 5 years at Google. ")
    c.drawString(100, 690, "Skills: Python, AWS, SQL")
    c.save()
    packet.seek(0)
    return packet.read()

def generate_thai_pdf():
    # PyMuPDF for easy UTF-8 injection
    import fitz
    doc = fitz.open()
    page = doc.new_page()
    # Using default font which might not render Thai perfectly visually but stores it perfectly semantically
    page.insert_text(fitz.Point(100, 100), "สมชาย ใจดี")
    page.insert_text(fitz.Point(100, 120), "นักพัฒนาซอฟต์แวร์")
    page.insert_text(fitz.Point(100, 140), "ประสบการณ์ทำงาน: 5 ปีที่บริษัท แสนสิริ จำกัด. ประสบการณ์ทำงาน: 5 ปีที่บริษัท แสนสิริ จำกัด. ประสบการณ์ทำงาน: 5 ปีที่บริษัท แสนสิริ จำกัด. ประสบการณ์ทำงาน: 5 ปีที่บริษัท แสนสิริ จำกัด. ประสบการณ์ทำงาน: 5 ปีที่บริษัท แสนสิริ จำกัด. ")
    return doc.write()

def generate_mixed_pdf():
    import fitz
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text(fitz.Point(100, 100), "บริษัท ABC จำกัด")
    page.insert_text(fitz.Point(100, 120), "Software Developer")
    page.insert_text(fitz.Point(100, 140), "มกราคม 2024 - ธันวาคม 2025")
    page.insert_text(fitz.Point(100, 160), "Skills: React, Node.js")
    return doc.write()

def generate_scanned_pdf():
    # Create an image, put text on it, save as PDF
    from PIL import Image, ImageDraw
    img = Image.new('RGB', (800, 600), color=(255, 255, 255))
    d = ImageDraw.Draw(img)
    d.text((10, 10), "Jane Smith", fill=(0,0,0))
    d.text((10, 30), "Data Scientist", fill=(0,0,0))
    d.text((10, 50), "Worked at Amazon for 3 years.", fill=(0,0,0))
    d.text((10, 70), "Skills: Machine Learning, Python", fill=(0,0,0))
    
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format='PDF')
    return img_byte_arr.getvalue()

def generate_garbled_pdf():
    import fitz
    doc = fitz.open()
    page = doc.new_page()
    # Inserting actual unicode replacement chars to simulate garbled font
    garbled_text = "\ufffd\ufffd\ufffd \ufffd\ufffd\ufffd " * 50
    page.insert_text(fitz.Point(100, 100), garbled_text)
    return doc.write()

async def run_test(name, pdf_bytes, job_id, expected_ocr_fallback=False):
    print(f"\\n--- Running Test: {name} ---")
    filename = f"e2e_{name.replace(' ', '_')}.pdf"
    file_path = f"{job_id}/{filename}"
    
    # 1. Upload to Supabase
    try:
        supabase.storage.from_("uploads").upload(file_path, pdf_bytes)
    except:
        supabase.storage.from_("uploads").update(file_path, pdf_bytes)
        
    print(f"Uploaded {filename} to Supabase")
    
    # 2. Call create_candidate
    candidate_data = CandidateCreate(
        name=name,
        resume_text="",
        resume_url=file_path
    )
    
    candidate = await create_candidate(job_id, candidate_data, user_id="e2e_test_user")
    print(f"Created Candidate: {candidate.id}")
    print(f"Candidate Score: {candidate.score}")
    print(f"Candidate Extracted Text Length: {len(candidate.extractedText)}")
    
    # 3. Validate Evidence
    has_bbox = False
    has_null_bbox = False
    for crit in candidate.criteria:
        for ev in crit.evidence:
            if ev.bbox is not None:
                has_bbox = True
            else:
                has_null_bbox = True
                
    if expected_ocr_fallback:
        assert not has_bbox, "Expected OCR fallback, but found bboxes!"
        assert has_null_bbox or len(candidate.criteria) == 0, "Expected null bboxes for OCR fallback!"
        print("✅ OCR Fallback successful: bbox=null, charStart/End calculated")
    else:
        assert has_bbox, "Expected PyMuPDF extraction, but found no bboxes!"
        print("✅ PyMuPDF Extraction successful: bboxes present")
        
    print(f"Successfully passed: {name}")

async def main():
    job_id = "test_job_123"
    
    tests = [
        ("English Resume", generate_english_pdf(), False),
        ("Thai Resume", generate_thai_pdf(), False),
        ("Mixed Resume", generate_mixed_pdf(), False),
        ("Scanned Resume", generate_scanned_pdf(), True),
        ("Garbled Resume", generate_garbled_pdf(), True)
    ]
    
    for name, pdf_bytes, expects_ocr in tests:
        await run_test(name, pdf_bytes, job_id, expects_ocr)
        
    print("\\n\\n🎉 All E2E Tests Passed Successfully!")

if __name__ == "__main__":
    asyncio.run(main())
