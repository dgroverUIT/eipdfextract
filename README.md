# PDF Inspection Data Extractor

An Azure Function that extracts structured data from PDF inspection reports.

## Features

- Extracts project information, observations, and review status from PDF inspection reports
- Returns data in a structured JSON format
- Handles various data formats including key-value pairs, dash-prefixed rows, and site photos

## Project Structure

```
eipdfextract/
├── ExtractObservations/
│   ├── __init__.py            # Main function code
│   └── function.json          # HTTP trigger configuration
├── host.json                  # Functions runtime configuration
└── requirements.txt           # Python dependencies
```

## Prerequisites

- Python 3.8 or higher
- Azure Functions Core Tools
- Azure subscription (for deployment)

## Local Development

1. Create a virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Run the function locally:
   ```bash
   func start
   ```

## Deployment

### Deploy to Azure

1. Install Azure Functions Core Tools:
   ```bash
   npm install -g azure-functions-core-tools@4
   ```

2. Login to Azure:
   ```bash
   az login
   ```

3. Deploy the function:
   ```bash
   func azure functionapp publish EIPDFExtractV1
   ```

### Using GitHub Actions

The repository includes a GitHub Actions workflow for automated deployment. Simply push to the main branch to trigger deployment.

## API Usage

Send a POST request to the function endpoint with a PDF file in the request body:

```bash
curl -X POST -H "Content-Type: application/pdf" --data-binary @your-file.pdf https://eipdfextractv1.azurewebsites.net/api/ExtractObservations
```

## Response Format

The function returns a JSON array of observations, each containing:
- Observation Name
- Observation Subdetail
- Value

Example response:
```json
[
  {
    "Observation Name": "Project Information",
    "Observation Subdetail": "Project Name",
    "Value": "Sample Project"
  },
  {
    "Observation Name": "A_General Observations",
    "Observation Subdetail": "Condition",
    "Value": "Good"
  }
]
```

## License

MIT 