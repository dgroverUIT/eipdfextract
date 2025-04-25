# PDF Inspection Data Extractor

An Azure Function that extracts structured data from PDF inspection reports.

## Features

- Extracts project information from PDF inspection reports
- Processes section headers and their content
- Handles special cases like Site Photos
- Extracts Review Status and Acknowledgment information
- Returns data in a structured JSON format

## Requirements

- Python 3.8 or higher
- Azure Functions Core Tools
- Dependencies listed in requirements.txt

## Installation

1. Clone this repository
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

The function accepts a POST request with a PDF file in the request body. It returns a JSON array containing the extracted data.

### Example Request

```bash
curl -X POST -H "Content-Type: application/pdf" --data-binary @inspection.pdf http://your-function-url/api/function-name
```

### Example Response

```json
[
  {
    "Observation Name": "Project Information",
    "Observation Subdetail": "Date/Time",
    "Value": "04-17-2025"
  },
  {
    "Observation Name": "Project Information",
    "Observation Subdetail": "Street Address",
    "Value": "14915 Clover Meadow Ln"
  }
]
```

## Development

To run the function locally:

1. Install Azure Functions Core Tools
2. Run the function:
   ```bash
   func start
   ```

## License

MIT 