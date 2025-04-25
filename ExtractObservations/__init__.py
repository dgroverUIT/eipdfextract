import logging
import azure.functions as func
import fitz  # PyMuPDF
import re
import json
from typing import List, Dict

def extract_observations_from_text(text: str) -> List[Dict[str, str]]:
    entries: List[Dict[str, str]] = []

    # 1) Extract Project Information
    proj_match = re.search(r'Project Information\s*(.*?)\n\n', text, re.DOTALL)
    if proj_match:
        for ln in proj_match.group(1).splitlines():
            if ':' in ln:
                key, val = ln.split(':', 1)
                entries.append({
                    "Observation Name": "Project Information",
                    "Observation Subdetail": key.strip(),
                    "Value": val.strip()
                })

    # 2) Identify all section headers (keep prefixes & numbering)
    header_regex = re.compile(r'^([A-Z]_[^\n:]+?(?: \(\d+\))?):?$', re.MULTILINE)
    headers = [(m.start(), m.group(1).strip()) for m in header_regex.finditer(text)]
    headers.append((len(text), "__END__"))  # sentinel

    # 3) Process each header block
    for i in range(len(headers) - 1):
        start_pos, obs_name = headers[i]
        end_pos = headers[i + 1][0]
        block_lines = text[start_pos:end_pos].splitlines()

        # Strip out the header line itself
        lines = [
            ln.strip()
            for ln in block_lines
            if ln.strip() and ln.strip().rstrip(':') != obs_name
        ]
        if not lines:
            continue

        # 3a) Site Photo handling
        if "Site Photo" in obs_name:
            entries.append({
                "Observation Name": obs_name,
                "Observation Subdetail": "Site Photo",
                "Value": "image"
            })
            idx = 0
            while idx < len(lines):
                label = lines[idx]
                if label in ("Photo Description", "Condition", "General Observation", "Action Item"):
                    if idx + 1 < len(lines):
                        entries.append({
                            "Observation Name": obs_name,
                            "Observation Subdetail": label,
                            "Value": lines[idx + 1]
                        })
                        idx += 2
                        continue
                idx += 1
            continue

        # 3b) Dash-prefixed rows
        dash_rows = []
        buffer_cont = []
        for ln in lines:
            if ln.startswith("-"):
                # flush any buffer into last row
                if buffer_cont and dash_rows:
                    dash_rows[-1]["Value"] += " " + " ".join(buffer_cont)
                    buffer_cont = []
                dash_rows.append({
                    "Observation Name": obs_name,
                    "Observation Subdetail": "-",
                    "Value": ln.lstrip("- ").strip()
                })
            else:
                if dash_rows:
                    buffer_cont.append(ln)
        if dash_rows:
            entries.extend(dash_rows)
            continue

        # 3c) Generic key:value parsing
        curr_label = None
        curr_vals: List[str] = []
        for ln in lines:
            if ":" in ln:
                if curr_label:
                    entries.append({
                        "Observation Name": obs_name,
                        "Observation Subdetail": curr_label,
                        "Value": ", ".join(curr_vals)
                    })
                key, val = ln.split(":", 1)
                curr_label = key.strip()
                curr_vals = [val.strip()]
            elif curr_label:
                curr_vals.append(ln)
            else:
                entries.append({
                    "Observation Name": obs_name,
                    "Observation Subdetail": "",
                    "Value": ln
                })
        if curr_label:
            entries.append({
                "Observation Name": obs_name,
                "Observation Subdetail": curr_label,
                "Value": ", ".join(curr_vals)
            })

    # 4) Extract Review Status and Acknowledgment
    review_match = re.search(
        r'Review Status and Acknowledgment\s*(.*?)(?:Date Submitted:|$)',
        text,
        re.DOTALL
    )
    if review_match:
        lines = [
            ln.strip()
            for ln in review_match.group(1).splitlines()
            if ln.strip()
        ]
        fields = ["Review Status", "Acknowledgment", "Inspector", "Inspector Phone Number"]
        label = None
        for ln in lines:
            if ln in fields:
                label = ln
            elif label:
                entries.append({
                    "Observation Name": "Review Status and Acknowledgment",
                    "Observation Subdetail": label,
                    "Value": ln
                })
                label = None

    return entries

def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Received PDF for extraction.')

    try:
        # 1. Read PDF bytes from POST body
        pdf_bytes = req.get_body()
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")

        # 2. Concatenate all page texts
        full_text = "\n".join(page.get_text() for page in doc)
        doc.close()

        # 3. Extract structured observations
        records = extract_observations_from_text(full_text)

        # 4. Return JSON array
        return func.HttpResponse(
            json.dumps(records, ensure_ascii=False),
            status_code=200,
            mimetype="application/json"
        )

    except Exception as e:
        logging.error(f"PDF extraction error: {e}")
        return func.HttpResponse(
            json.dumps({"error": str(e)}),
            status_code=500,
            mimetype="application/json"
        ) 