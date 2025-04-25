import pdfplumber
import re
import csv
import os
from pathlib import Path

def process_pdf(directory: str, filename: str) -> None:
    pdf_path = Path(directory) / filename
    try:
        # Open the PDF
        pdf = pdfplumber.open(str(pdf_path))
        total_pages = len(pdf.pages)
        print(f"Processing PDF with {total_pages} pages")

        # Data structure to hold extracted rows: list of tuples (Observation Name, Observation Subdetail, Value)
        extracted_rows = []

        # Helper function to merge multi-line text in a value cell according to rules
        def merge_multiline_value(text):
            """Merge multi-line cell text into a single string following the specified rules."""
            lines = text.splitlines()
            merged_lines = [lines[0].strip()]
            for line in lines[1:]:
                line = line.strip()
                if not line:
                    continue  # skip blank lines in value
                prev = merged_lines[-1]
                # If previous line ends with a hyphen (word break), concatenate without space
                if prev.endswith("-"):
                    merged_lines[-1] = prev[:-1] + line
                # If previous line does not end in punctuation and current line starts with uppercase, treat as separate item
                elif prev and not prev.endswith(('.', ';', ':', ',')) and line[0].isupper():
                    merged_lines.append(line)
                else:
                    # Otherwise, treat as continuation of sentence (add a space between)
                    merged_lines[-1] = prev + (" " if not prev.endswith(" ") else "") + line
            # If multiple separate items were detected, join them with '; ', else return single string
            return "; ".join(merged_lines) if len(merged_lines) > 1 else merged_lines[0]

        # Dictionary to store content tables for each identified section
        section_content = {}

        # Keep track of the last section heading that continues to the next page (for multi-page tables)
        current_section = None

        # Iterate through each page to detect sections and extract tabular data
        for page_index in range(total_pages):
            page = pdf.pages[page_index]
            text = page.extract_text() or ""
            lines = text.splitlines()

            # Identify any section headings on this page
            page_headings = []
            for line_index, line in enumerate(lines):
                line_stripped = line.strip()
                if not line_stripped:
                    continue
                # Skip repetitive header/footer lines that are not content
                if (line_stripped.startswith("Date Submitted:") or 
                    line_stripped.startswith("Submitted By:") or 
                    line_stripped.startswith("Envelope Construction Progress Inspection") or 
                    line_stripped.startswith("Page ") or 
                    line_stripped.startswith("Exterior Inspections")):
                    continue
                # Project Information section heading
                if line_stripped == "Project Information":
                    page_headings.append((line_index, "Project Information"))
                # Observation section headings (e.g. "F_Something" or "S_Other")
                elif re.match(r'^[A-Z]_[\w\s\(\)&]+:?$', line_stripped):
                    # Keep the full header text including prefix and numbering
                    section_name = line_stripped.rstrip(":")
                    page_headings.append((line_index, section_name))
                # Review Status and Acknowledgment section heading
                elif line_stripped.startswith("Review Status and Acknowledgment"):
                    page_headings.append((line_index, "Review Status and Acknowledgment"))
            # Sort headings on this page by their order in text
            page_headings.sort(key=lambda x: x[0])

            # Extract all tables from the page using pdfplumber
            tables = page.extract_tables() or []

            # Determine the first actual content line index (skipping headers)
            first_content_line_idx = None
            for idx, line in enumerate(lines):
                ls = line.strip()
                if not ls:
                    continue
                if (ls.startswith("Date Submitted:") or ls.startswith("Submitted By:") or 
                    ls.startswith("Envelope Construction Progress Inspection") or 
                    ls.startswith("Page ") or ls.startswith("Exterior Inspections")):
                    continue
                first_content_line_idx = idx
                break

            # If there's a section continuing from the previous page and no new section starts immediately, 
            # treat the leading tables on this page as continuation of the current section.
            if current_section:
                # Check if this page has no new heading at the top (or the first heading appears later in the page)
                if not page_headings or (first_content_line_idx is not None and page_headings and first_content_line_idx < page_headings[0][0]):
                    # Assign tables to the continuing section until a new section heading is encountered
                    while tables:
                        if page_headings and first_content_line_idx is not None:
                            heading_line_idx = page_headings[0][0]
                        else:
                            heading_line_idx = float('inf')  # No heading on this page, treat all as continuation
                        # Use the first cell (or first few words of second cell) as a key to determine position in text
                        first_row = tables[0][0] if tables[0] else []
                        first_cell_text = str(first_row[0]).strip() if len(first_row) > 0 and first_row[0] is not None else ""
                        search_key = first_cell_text
                        if not search_key or search_key == '-' or len(search_key) < 3:
                            # If the first cell is empty or just a dash, use first 3 words of the value cell for positioning
                            if len(first_row) > 1 and first_row[1]:
                                search_key = " ".join(str(first_row[1]).split()[:3])
                        # Check if this search_key appears in the text before the next heading
                        found_position = False
                        for li, txt in enumerate(lines):
                            if li >= heading_line_idx:
                                break
                            if search_key and search_key in txt:
                                found_position = True
                                break
                        if found_position:
                            # Attach this table's rows to the current continuing section
                            section_content.setdefault(current_section, [])
                            for row in tables[0]:
                                section_content[current_section].append(row)
                            # Remove the table and update the first content line (in case multiple tables continue)
                            tables.pop(0)
                            # Update the first_content_line_idx to the next content after the assigned table
                            first_content_line_idx = None
                            for idx2, line in enumerate(lines):
                                ls2 = line.strip()
                                if not ls2:
                                    continue
                                if (ls2.startswith("Date Submitted:") or ls2.startswith("Submitted By:") or 
                                    ls2.startswith("Envelope Construction Progress Inspection") or 
                                    ls2.startswith("Page ") or ls2.startswith("Exterior Inspections")):
                                    continue
                                # Skip lines that belong to the table we just assigned
                                if search_key and search_key in ls2:
                                    continue
                                first_content_line_idx = idx2
                                break
                        else:
                            # Stop if the next table likely starts after a new heading
                            break

            # Process section headings on this page and assign remaining tables to sections
            if page_headings:
                # Iterate through each heading found on this page
                for idx, (heading_line_idx, section_name) in enumerate(page_headings):
                    if section_name == "Review Status and Acknowledgment":
                        # Do not assign tables for this special section here (handled separately later)
                        current_section = None
                        continue
                    section_content.setdefault(section_name, [])
                    if idx == len(page_headings) - 1:
                        # Last heading on this page: it gets all remaining tables (this accounts for multi-table sections)
                        for table in tables:
                            for row in table:
                                section_content[section_name].append(row)
                        tables = []  # all tables on this page assigned
                    else:
                        # Not the last heading: assign the next table to this section
                        if tables:
                            for row in tables[0]:
                                section_content[section_name].append(row)
                            tables.pop(0)
                    # Set this section as the current section (in case it continues to next page)
                    current_section = section_name if section_name != "Review Status and Acknowledgment" else None
            else:
                # No new heading on this page: if a section was continuing, keep it as current_section
                if current_section and tables:
                    section_content.setdefault(current_section, [])
                    for table in tables:
                        for row in table:
                            section_content[current_section].append(row)
                    tables = []

            # If "Review Status and Acknowledgment" heading is encountered, end any continuing section
            if page_headings and page_headings[-1][1] == "Review Status and Acknowledgment":
                current_section = None

        # After processing all pages, handle the "Review Status and Acknowledgment" section:
        review_status_value = None
        for page_index in range(total_pages):
            text = pdf.pages[page_index].extract_text() or ""
            if "Review Status and Acknowledgment" in text:
                # Extract the "Review Status" line from this section
                for line in text.splitlines():
                    if line.strip().startswith("Review Status") and "Acknowledgment" not in line:
                        # The line that contains the actual review status value (excluding the heading)
                        parts = line.split("Review Status", 1)
                        if len(parts) > 1:
                            review_status_value = parts[1].strip().lstrip(":").strip()
                        break
                break
        if review_status_value:
            section_content.setdefault("Review Status and Acknowledgment", [])
            section_content["Review Status and Acknowledgment"].append(["Review Status", review_status_value])

        # Close the PDF file
        pdf.close()

        # Normalize all outputs into rows with Observation Name, Observation Subdetail, and Value
        for section_name, rows in section_content.items():
            # Skip empty sections
            if not rows:
                continue
                
            # Special handling for photo sections
            if re.match(r'^[A-Z]_Site Photo \(\d+\)$', section_name):
                # For photo sections, ensure we have all four rows
                photo_rows = []
                for row in rows:
                    if not row:
                        continue
                    # Some rows might be single-column; ensure subdetail and value are defined
                    subdetail = str(row[0]).strip() if len(row) > 0 and row[0] is not None else ""
                    value = str(row[1]).strip() if len(row) > 1 and row[1] is not None else ""
                    # Rule 3 & 4: if subdetail is just a dash or blank, keep it as subdetail (indicates observation subdetail placeholder)
                    observation_subdetail = subdetail if subdetail != "" else "-" if subdetail == "-" else ""
                    # Merge multi-line values properly (Rule 2 and multi-line handling)
                    if "\n" in value:
                        value = merge_multiline_value(value)
                    photo_rows.append((section_name, observation_subdetail, value))
                
                # Ensure we have all four rows for photo sections
                required_fields = ["Photo Description", "Condition", "General Observation", "Action Item"]
                existing_fields = {row[1] for row in photo_rows}
                
                # Add missing fields with empty values
                for field in required_fields:
                    if field not in existing_fields:
                        photo_rows.append((section_name, field, ""))
                
                # Add all photo rows to the final output
                extracted_rows.extend(photo_rows)
            else:
                # Normal section processing
                for row in rows:
                    if not row:
                        continue
                    # Some rows might be single-column; ensure subdetail and value are defined
                    subdetail = str(row[0]).strip() if len(row) > 0 and row[0] is not None else ""
                    value = str(row[1]).strip() if len(row) > 1 and row[1] is not None else ""
                    # Rule 3 & 4: if subdetail is just a dash or blank, keep it as subdetail (indicates observation subdetail placeholder)
                    observation_subdetail = subdetail if subdetail != "" else "-" if subdetail == "-" else ""
                    # Merge multi-line values properly (Rule 2 and multi-line handling)
                    if "\n" in value:
                        value = merge_multiline_value(value)
                    # Ensure blank cells are handled (if value is empty string, it remains empty, which is fine - Rule 4)
                    extracted_rows.append((section_name, observation_subdetail, value))

        # Create output filename based on input filename
        output_csv_path = pdf_path.stem + "_extracted.csv"
        
        # Write the results to a CSV file
        with open(output_csv_path, mode="w", newline="", encoding="utf-8") as csvfile:
            writer = csv.writer(csvfile)
            # Write header
            writer.writerow(["Observation Name", "Observation Subdetail", "Value"])
            # Write each extracted row
            for obs_name, subdetail, val in extracted_rows:
                writer.writerow([obs_name, subdetail, val])
        
        print(f"\nData has been saved to: {output_csv_path}")
        print(f"Extracted {len(extracted_rows)} data points")
        
    except Exception as e:
        print(f"Error processing PDF: {str(e)}")
        raise

if __name__ == "__main__":
    # Process the specific file
    directory = r"C:\Users\DarrenGrover\EIPython"
    filename = "14915 Clover Meadow Ln Final 1st 04-17-2025_09516.pdf"
    
    try:
        process_pdf(directory, filename)
    except Exception as e:
        print(f"Error: {str(e)}")
        import sys
        sys.exit(1) 