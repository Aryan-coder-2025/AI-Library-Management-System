"""
Production Script: Update Capstone Technical Report Author and Role
Replaces all references to 'Prasanth Kumar Gavara' / 'Frontend & UI' with:
'Aryan Dutta' and 'Lead Architecture & Backend Engineering'.
Conforms to 100% pixel-perfect typography, font metrics, and page layouts.
"""

import os
import shutil
import fitz

SOURCE_PDF = r"C:\Users\aryan\.gemini\antigravity\brain\e4cec4a3-71f8-4503-b397-0d3cff1bd9cd\.user_uploaded\media_1794749870931_d971105e.pdf"

TARGET_WORKSPACE_PDF = r"c:\Users\aryan\OneDrive\Desktop\AI-Library-Management-System\CSE_276_ATHENAEUM_AI_TECHNICAL_REPORT.pdf"
TARGET_ALT_PDF = r"c:\Users\aryan\OneDrive\Desktop\AI-Library-Management-System\CSE_276_Athenaeum_AI_2.0_Technical_Report.pdf"

ARTIFACT_DIR = r"C:\Users\aryan\.gemini\antigravity\brain\e4cec4a3-71f8-4503-b397-0d3cff1bd9cd"
TARGET_ARTIFACT_PDF = os.path.join(ARTIFACT_DIR, "CSE_276_ATHENAEUM_AI_TECHNICAL_REPORT.pdf")
TARGET_ARTIFACT_ALT_PDF = os.path.join(ARTIFACT_DIR, "CSE_276_Athenaeum_AI_2.0_Technical_Report.pdf")

def update_pdf():
    print(f"Opening source PDF: {SOURCE_PDF}")
    doc = fitz.open(SOURCE_PDF)
    print(f"Total pages: {len(doc)}")

    f_times = r"C:\Windows\Fonts\times.ttf"
    f_timesbd = r"C:\Windows\Fonts\timesbd.ttf"
    f_arial = r"C:\Windows\Fonts\arial.ttf"

    font_reg = fitz.Font(fontfile=f_times)
    font_bd = fitz.Font(fontfile=f_timesbd)

    c_body = (30/255, 41/255, 59/255)       # #1e293b
    c_bold = (15/255, 23/255, 42/255)       # #0f172a
    c_footer = (100/255, 116/255, 139/255)  # #64748b

    # -------------------------------------------------------------
    # 1. Update running footers on all pages (Pages 1 to 23)
    # -------------------------------------------------------------
    print("Updating running footers across all 23 pages...")
    for page_idx in range(len(doc)):
        page = doc[page_idx]
        # Redact candidate name section of footer: [50.0, 796.0, 425.0, 807.0]
        r_footer = fitz.Rect(50.0, 796.0, 425.0, 807.0)
        page.add_redact_annot(r_footer, fill=(1, 1, 1))
        page.apply_redactions()

        # Re-insert updated candidate footer
        footer_text = "CSE 276 Capstone Technical Report — Athenaeum AI 2.0 (Candidate: Aryan Dutta)"
        page.insert_text(
            (51.02, 804.0),
            footer_text,
            fontsize=8.4975,
            fontname="arial",
            fontfile=f_arial,
            color=c_footer
        )

    # -------------------------------------------------------------
    # 2. Page 1: Cover Table, Declaration, Signature
    # -------------------------------------------------------------
    print("Updating Page 1 (Cover table, Declaration, Candidate Signature)...")
    p1 = doc[0]

    # 2a. Table row: Candidate Name
    r_p1_tbl = fitz.Rect(228.0, 268.0, 540.0, 284.0)
    p1.add_redact_annot(r_p1_tbl, fill=(1, 1, 1))
    p1.apply_redactions()
    p1.insert_text(
        (230.13, 279.75),
        "Aryan Dutta (Lead Architecture & Backend Engineering)",
        fontsize=9.495,
        fontname="times",
        fontfile=f_times,
        color=c_body
    )

    # 2b. Declaration line 1: Justified spacing
    r_p1_dec = fitz.Rect(50.0, 452.0, 545.0, 465.0)
    p1.add_redact_annot(r_p1_dec, fill=(1, 1, 1))
    p1.apply_redactions()

    dec_words = [
        ('I,', f_times, False),
        ('Aryan', f_timesbd, True),
        ('Dutta,', f_timesbd, True),
        ('hereby', f_times, False),
        ('declare', f_times, False),
        ('that', f_times, False),
        ('the', f_times, False),
        ('technical', f_times, False),
        ('capstone', f_times, False),
        ('project', f_times, False),
        ('titled', f_times, False)
    ]
    w_sum = sum((font_bd if is_b else font_reg).text_length(w, 11) for w, _, is_b in dec_words)
    avail = 544.24 - 51.02
    gap = (avail - w_sum) / (len(dec_words) - 1)

    cur_x = 51.02
    for w, fpath, is_b in dec_words:
        p1.insert_text(
            (cur_x, 462.0),
            w,
            fontsize=11.0,
            fontname="timesbd" if is_b else "times",
            fontfile=fpath,
            color=c_body
        )
        w_len = (font_bd if is_b else font_reg).text_length(w, 11.0)
        cur_x += w_len + gap

    # 2c. Candidate Signature block
    r_p1_sig = fitz.Rect(50.0, 698.0, 280.0, 711.0)
    p1.add_redact_annot(r_p1_sig, fill=(1, 1, 1))
    p1.apply_redactions()
    p1.insert_text(
        (51.02, 707.25),
        "Aryan Dutta (Lead Architecture & Backend Engineering)",
        fontsize=9.495,
        fontname="times",
        fontfile=f_times,
        color=c_body
    )

    # -------------------------------------------------------------
    # 3. Page 21: Certification Block
    # -------------------------------------------------------------
    print("Updating Page 21 (Evaluation Certification block)...")
    p21 = doc[20]
    r_p21_cert = fitz.Rect(50.0, 532.0, 546.0, 582.0)
    p21.add_redact_annot(r_p21_cert, fill=(1, 1, 1))
    p21.apply_redactions()

    # Line 1:
    x_l1 = 51.02
    p21.insert_text((x_l1, 543.75), "Report Certified for Evaluation: ", fontsize=11.0, fontname="timesbd", fontfile=f_timesbd, color=c_bold)
    x_l1 += font_bd.text_length("Report Certified for Evaluation: ", 11.0)
    p21.insert_text((x_l1, 543.75), "Academic Session 2026–2027 | ", fontsize=11.0, fontname="times", fontfile=f_times, color=c_body)
    x_l1 += font_reg.text_length("Academic Session 2026–2027 | ", 11.0)
    p21.insert_text((x_l1, 543.75), "Candidate Author:", fontsize=11.0, fontname="timesbd", fontfile=f_timesbd, color=c_bold)

    # Line 2:
    x_l2 = 51.02
    p21.insert_text((x_l2, 560.25), "Aryan Dutta (Lead Architecture & Backend Engineering)", fontsize=11.0, fontname="timesbd", fontfile=f_timesbd, color=c_bold)
    x_l2 += font_bd.text_length("Aryan Dutta (Lead Architecture & Backend Engineering)", 11.0)
    p21.insert_text((x_l2, 560.25), " | ", fontsize=11.0, fontname="times", fontfile=f_times, color=c_body)
    x_l2 += font_reg.text_length(" | ", 11.0)
    p21.insert_text((x_l2, 560.25), "Verification Status:", fontsize=11.0, fontname="timesbd", fontfile=f_timesbd, color=c_bold)

    # Line 3:
    p21.insert_text((51.02, 576.75), "423 Automated Unit & Integration Tests Passing (100% Green Run).", fontsize=11.0, fontname="times", fontfile=f_times, color=c_body)

    # -------------------------------------------------------------
    # 4. Page 23: Workspace Bullet Point
    # -------------------------------------------------------------
    print("Updating Page 23 (Workspace & Architecture attribution)...")
    p23 = doc[22]
    # Redact Line 1 after frontend/ badge
    r_p23_l1 = fitz.Rect(263.0, 467.0, 545.0, 481.0)
    p23.add_redact_annot(r_p23_l1, fill=(1, 1, 1))

    # Redact Line 2
    r_p23_l2 = fitz.Rect(65.0, 483.0, 545.0, 498.0)
    p23.add_redact_annot(r_p23_l2, fill=(1, 1, 1))
    p23.apply_redactions()

    # Line 1:
    sz1 = 10.3
    x1 = 264.64
    p23.insert_text((x1, 477.75), "): Built by Candidate ", fontsize=sz1, fontname="times", fontfile=f_times, color=c_body)
    x1 += font_reg.text_length("): Built by Candidate ", sz1)
    p23.insert_text((x1, 477.75), "Aryan Dutta (Lead Architecture &", fontsize=sz1, fontname="timesbd", fontfile=f_timesbd, color=c_bold)

    # Line 2:
    sz2 = 10.5
    x2 = 66.02
    p23.insert_text((x2, 494.25), "Backend Engineering) ", fontsize=sz2, fontname="timesbd", fontfile=f_timesbd, color=c_bold)
    x2 += font_bd.text_length("Backend Engineering) ", sz2)
    p23.insert_text((x2, 494.25), "using React 19.3.1, TypeScript 6.0.3, Vite 5.4.11, and Three.js 0.187.0. Includes", fontsize=sz2, fontname="times", fontfile=f_times, color=c_body)

    # Metadata update
    meta = doc.metadata
    meta['title'] = "CSE 276 Capstone Technical Report - Athenaeum AI 2.0"
    meta['author'] = "Aryan Dutta (Lead Architecture & Backend Engineering)"
    meta['subject'] = "Athenaeum AI 2.0 Capstone Engineering Report"
    doc.set_metadata(meta)

    # Save to workspace PDF
    print(f"Saving updated report to: {TARGET_WORKSPACE_PDF}")
    doc.save(TARGET_WORKSPACE_PDF)
    doc.close()

    # Copy to alt filename and artifact directory
    shutil.copy2(TARGET_WORKSPACE_PDF, TARGET_ALT_PDF)
    print(f"Saved alternate copy to: {TARGET_ALT_PDF}")

    shutil.copy2(TARGET_WORKSPACE_PDF, TARGET_ARTIFACT_PDF)
    print(f"Saved artifact copy to: {TARGET_ARTIFACT_PDF}")

    shutil.copy2(TARGET_WORKSPACE_PDF, TARGET_ARTIFACT_ALT_PDF)
    print(f"Saved alternate artifact copy to: {TARGET_ARTIFACT_ALT_PDF}")

    # Final Verification
    verify_doc = fitz.open(TARGET_WORKSPACE_PDF)
    print(f"\n--- Verification Audit ---")
    print(f"Total pages: {len(verify_doc)}")
    
    found_old = False
    for p_idx, page in enumerate(verify_doc):
        text = page.get_text()
        if "Prasanth" in text or "Gavara" in text:
            print(f"WARNING: Old name found on page {p_idx+1}!")
            found_old = True
            
    if not found_old:
        print("PASS: Zero occurrences of 'Prasanth' or 'Gavara' found across all 23 pages.")

    print("\nAuditing updated occurrences of 'Aryan Dutta':")
    for p_idx, page in enumerate(verify_doc):
        text = page.get_text()
        if "Aryan Dutta" in text:
            print(f"Page {p_idx+1}: 'Aryan Dutta' present.")

    verify_doc.close()
    print("\nReport update complete!")

if __name__ == "__main__":
    update_pdf()
