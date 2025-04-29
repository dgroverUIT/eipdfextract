import json
import fitz
from ExtractObservations.extractor import extract_observations_from_text

# Test with a sample PDF
try:
    doc = fitz.open('test.pdf')  # Make sure to place a test PDF in the same directory
    text = '\n'.join(p.get_text() for p in doc)
    doc.close()
    
    results = extract_observations_from_text(text)
    print(json.dumps(results, indent=2))
except Exception as e:
    print(f"Error: {str(e)}") 