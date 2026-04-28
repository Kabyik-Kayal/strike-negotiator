import pypdf, pathlib
for src, dst in [
    ('seed/filings/raw/swiggy-drhp-2024.pdf', 'seed/filings/text/swiggy-drhp-2024.txt'),
    ('seed/filings/raw/zomato-annual_report-2024.pdf', 'seed/filings/text/zomato-annual_report-2024.txt'),
    ('seed/filings/raw/zomato-investor_call-2024.pdf', 'seed/filings/text/zomato-investor_call-2024.txt'),
]:
    reader = pypdf.PdfReader(src)
    text = '\n\n'.join(page.extract_text() or '' for page in reader.pages)
    pathlib.Path(dst).write_text(text, encoding='utf-8')
    print(f'Done: {dst}  ({len(reader.pages)} pages)')