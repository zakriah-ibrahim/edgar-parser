# EDGAR Filings EPS Parser

A versatile Python script designed to automatically extract quarterly Earnings Per Share (EPS) values from EDGAR financial filings in HTML format. The parser uses intelligent table analysis and regex fallback strategies to handle variations in financial data formatting across different companies.

## Features

- **Multi-Strategy Parsing**: Combines table analysis with regex fallback for maximum accuracy
- **Intelligent Column Detection**: Automatically detects chronological order of financial data
- **Priority-Based Search**: Searches for "Basic" EPS before "Diluted" EPS before generic values
- **Comprehensive Logging**: Detailed operation logs with performance metrics
- **Analytics Reporting**: Tracks successful keyword patterns for continuous improvement
- **Error Handling**: Robust error handling for malformed HTML files

## Installation

### Prerequisites

- Python 3.6 or higher
- Required Python packages:

```bash
pip install beautifulsoup4 pandas lxml
```

### Setup

1. Clone or download the script
2. Save as `parser.py`
3. Ensure you have the required dependencies installed

## Usage

### Command Line Interface

```bash
python parser.py [INPUT_DIRECTORY] [OUTPUT_CSV_FILE] --log_file [LOG_FILE_PATH]
```

### Parameters

- `INPUT_DIRECTORY`: Path to the folder containing HTML filing files
- `OUTPUT_CSV_FILE`: Path where the results CSV file will be saved
- `--log_file` (Optional): Path for the log file (defaults to `parser.log`)

### Examples

```bash
# Basic usage
python parser.py /path/to/filings /path/to/output.csv

# With custom log file
python parser.py /path/to/filings /path/to/output.csv --log_file /path/to/logs/parser.log

# Windows example
python parser.py "C:\filings" "C:\results\output.csv" --log_file "C:\logs\parser.log"
```

## How It Works

### Parsing Strategy

The parser employs a two-tier approach:

1. **Table Analysis (Primary)**:
   - Searches all HTML tables for EPS-related keywords
   - Uses dynamic column detection to determine data chronology
   - Prioritizes "Basic" over "Diluted" over generic EPS values
   - Searches both current and next rows for values

2. **Regex Fallback (Secondary)**:
   - If table analysis fails, searches the entire document text
   - Uses the same priority-based keyword matching
   - Looks for patterns like "EPS: $1.23" or "earnings per share (0.45)"

### Keyword Priorities

1. **Basic EPS Keywords**:
   - "basic earnings per share"
   - "basic eps"
   - "net income per share - basic"

2. **Diluted EPS Keywords**:
   - "diluted earnings per share"
   - "diluted eps"
   - "net income per share - diluted"

3. **Generic Keywords**:
   - "eps"
   - "income per share"
   - "per share"

### Data Handling

- **Negative Values**: Automatically converts parentheses notation `(0.41)` to `-0.41`
- **Currency Symbols**: Strips dollar signs and other formatting
- **Direction Detection**: Analyzes table headers to determine if recent data is left or right

## Output

### CSV File Format

The script generates a CSV file with the following columns:

| filename | EPS |
|----------|-----|
| filing1.html | 1.23 |
| filing2.html | -0.45 |
| filing3.html | Not Found |

### Log File

The log file contains:
- Processing status for each file
- Performance metrics (processing time per file)
- Method used to extract each EPS value
- Keyword frequency analysis
- Error messages and warnings

## Error Handling

The parser handles various edge cases:
- Malformed HTML files
- Missing or corrupted data
- Files with no EPS information
- Different table structures and formats
- Various number formatting styles

## Performance

- **Average Processing Time**: ~0.1-0.5 seconds per file
- **Memory Usage**: Minimal (processes files sequentially)
- **Scalability**: Can handle hundreds of files efficiently

## Troubleshooting

### Common Issues

1. **No EPS Found**:
   - Check if the HTML files contain financial data
   - Verify files are quarterly earnings reports (10-Q, 8-K)
   - Check log file for specific error messages

2. **Permission Errors**:
   - Ensure write permissions for output directory
   - Check that input directory exists and is readable

3. **Installation Issues**:
   - Verify all required packages are installed
   - Check Python version compatibility

### Log Analysis

Use the keyword frequency report in logs to understand:
- Which patterns are most successful
- Whether files contain expected financial data
- Performance bottlenecks

## Example Log Output

```
2024-03-15 10:30:15 - INFO - Starting analysis for AAPL_Q3_2023.html
2024-03-15 10:30:15 - INFO - [SUCCESS] Found EPS: 1.26 | Method: Table (L-R Search) | Keyword: 'basic earnings per share' | Time: 0.12s
2024-03-15 10:30:15 - INFO - Starting analysis for MSFT_Q2_2023.html
2024-03-15 10:30:16 - INFO - [SUCCESS] Found EPS: 2.45 | Method: Regex | Keyword: 'diluted eps' | Time: 0.15s

--- Keyword Frequency Report ---
5 match(es) for: "basic earnings per share"
3 match(es) for: "diluted eps"
2 match(es) for: "eps"
```

## Contributing

This script was created as part of a technical assessment. For improvements or bug reports, consider:
- Adding new keyword patterns for edge cases
- Implementing support for additional file formats
- Enhancing table structure recognition

## License

Created by Mohammed Zakriah Ibrahim for Trexquant Investment interview process.

## Acknowledgments

Development assistance provided by LLMs including Gemini and ChatGPT during the preparation phase.