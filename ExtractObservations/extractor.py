import re
import logging
from typing import List, Dict

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def extract_observations_from_text(text: str) -> List[Dict[str, str]]:
    entries: List[Dict[str, str]] = []
    logger.debug("Starting text extraction")

    try:
        # Project Information
        proj = re.search(r"Project Information\s*(.*?)\n\n", text, re.DOTALL)
        if proj:
            logger.debug("Found Project Information section")
            for ln in proj.group(1).splitlines():
                if ":" in ln:
                    k, v = ln.split(":", 1)
                    entry = {
                        "Observation Name": "Project Information",
                        "Observation Subdetail": k.strip(),
                        "Value": v.strip()
                    }
                    logger.debug(f"Adding project info entry: {entry}")
                    entries.append(entry)

        # Section headers (keep prefixes + numbering)
        hdr_re = re.compile(r"^([A-Z]_[^\n:]+?(?: \(\d+\))?):?$", re.MULTILINE)
        headers = [(m.start(), m.group(1).strip()) for m in hdr_re.finditer(text)]
        headers.append((len(text), "__END__"))
        logger.debug(f"Found {len(headers)} section headers")

        for i in range(len(headers) - 1):
            start, name = headers[i]
            end = headers[i + 1][0]
            lines = [ln.strip()
                    for ln in text[start:end].splitlines()
                    if ln.strip() and ln.strip().rstrip(":") != name]

            if not lines:
                continue

            logger.debug(f"Processing section: {name}")

            # --- Site Photo blocks ------------------------------------------------
            if "Site Photo" in name:
                logger.debug("Processing Site Photo block")
                entries.append({
                    "Observation Name": name,
                    "Observation Subdetail": "Site Photo",
                    "Value": "image"
                })
                idx = 0
                while idx < len(lines):
                    label = lines[idx]
                    if label in ("Photo Description", "Condition",
                                "General Observation", "Action Item"):
                        if idx + 1 < len(lines):
                            entry = {
                                "Observation Name": name,
                                "Observation Subdetail": label,
                                "Value": lines[idx + 1]
                            }
                            logger.debug(f"Adding photo entry: {entry}")
                            entries.append(entry)
                            idx += 2
                            continue
                    idx += 1
                continue

            # --- dash-style rows --------------------------------------------------
            dash_rows, buffer = [], []
            for ln in lines:
                if ln.startswith("-"):
                    if buffer and dash_rows:
                        dash_rows[-1]["Value"] += " " + " ".join(buffer)
                        buffer = []
                    entry = {
                        "Observation Name": name,
                        "Observation Subdetail": "-",
                        "Value": ln.lstrip("- ").strip()
                    }
                    logger.debug(f"Adding dash entry: {entry}")
                    dash_rows.append(entry)
                else:
                    if dash_rows:
                        buffer.append(ln)
            if dash_rows:
                logger.debug(f"Adding {len(dash_rows)} dash entries")
                entries.extend(dash_rows)
                continue

            # --- generic key: value parsing --------------------------------------
            label, vals = None, []
            for ln in lines:
                if ":" in ln:
                    if label and isinstance(vals, list):
                        entry = {
                            "Observation Name": name,
                            "Observation Subdetail": label,
                            "Value": ", ".join(vals)
                        }
                        logger.debug(f"Adding key-value entry: {entry}")
                        entries.append(entry)
                    label, vals = map(str.strip, ln.split(":", 1))
                    vals = [vals]  # Ensure vals is a list
                elif label:
                    if isinstance(vals, list):
                        vals.append(ln)
                    else:
                        logger.warning(f"vals is not a list: {vals}")
                        vals = [str(vals), ln]
                else:
                    entry = {
                        "Observation Name": name,
                        "Observation Subdetail": "",
                        "Value": ln
                    }
                    logger.debug(f"Adding standalone entry: {entry}")
                    entries.append(entry)
            if label and isinstance(vals, list):
                entry = {
                    "Observation Name": name,
                    "Observation Subdetail": label,
                    "Value": ", ".join(vals)
                }
                logger.debug(f"Adding final key-value entry: {entry}")
                entries.append(entry)

        # Review Status & Acknowledgment
        rev = re.search(r"Review Status and Acknowledgment\s*(.*?)(?:Date Submitted:|$)",
                        text, re.DOTALL)
        if rev:
            logger.debug("Processing Review Status section")
            fields = ["Review Status", "Acknowledgment",
                    "Inspector", "Inspector Phone Number"]
            lab = None
            for ln in (l.strip() for l in rev.group(1).splitlines() if l.strip()):
                if ln in fields:
                    lab = ln
                elif lab:
                    entry = {
                        "Observation Name": "Review Status and Acknowledgment",
                        "Observation Subdetail": lab,
                        "Value": ln
                    }
                    logger.debug(f"Adding review entry: {entry}")
                    entries.append(entry)
                    lab = None

        logger.debug(f"Extraction complete. Found {len(entries)} entries")
        return entries

    except Exception as e:
        logger.error(f"Error during extraction: {str(e)}")
        logger.error(f"Current entries: {entries}")
        raise 