"""
EDGAR Filings EPS Parser
========================

Purpose:
--------
This script is designed to automatically parse a directory of EDGAR financial filings
in HTML format. Its primary goal is to extract the quarterly Earnings Per Share (EPS)
value for each filing and save the results into a structured CSV file.

It is built to be "versatile," meaning it can handle variations in how different
companies format their financial data.

How to Run:
-------------
The script is executed from the command line and requires two arguments: an input
directory and an output file path. An optional argument can be provided to specify
a log file path.

1.  Save this script as `parser.py`.
2.  Make sure you have a directory containing your HTML filing files.
3.  Open your terminal or command prompt and run the script using the following format:

    python parser.py [INPUT_DIRECTORY] [OUTPUT_CSV_FILE] --log_file [LOG_FILE_PATH]

Example Command:
    python parser.py /path/to/your/filings /path/to/your/output.csv --log_file /path/to/logs/parser.log

- `[INPUT_DIRECTORY]`: The folder containing the .html files you want to parse.
- `[OUTPUT_CSV_FILE]`: The full path where the final CSV results should be saved.
- `[LOG_FILE_PATH]` (Optional): The path for the log file. If not provided, it defaults
  to creating `parser.log` in the current directory.

Required Libraries:
-------------------
- beautifulsoup4
- pandas
- lxml

You can install these using pip:
    pip install beautifulsoup4 pandas lxml

How It Works:
-------------
The parser uses a multi-layered strategy to find the most accurate EPS value:
1.  **Table Analysis:** It first searches all tables within the HTML document, as this is
    the most reliable source. It uses a prioritized list of regular expression
    patterns to find "Basic" EPS before "Diluted" EPS.
2.  **Dynamic Column Detection:** It intelligently analyzes table headers to detect whether
    the most recent quarter's data is on the left or right side of the table, and
    adjusts its search direction accordingly.
3.  **Regex Fallback:** If no EPS value is found in any tables, the script falls back to
    running the same prioritized regex patterns on the full text of the document.
4.  **Logging & Analytics:** The script generates a detailed log file of its operations and
    provides a summary report on which keywords were most successful, which helps
    in refining the parser over time.

Disclaimer:
-----------
This script was created by Mohammed Zakriah Ibrahim for a coding test as part of the
interview process with Trexquant Investment. During the preparation of this
application, assistance from LLMs such as Gemini and ChatGPT was used.
"""

import argparse
import os
import re
import time
import logging
from collections import defaultdict
import pandas as pd
from bs4 import BeautifulSoup

# --- Global Keyword Frequency Counter ---
# This dictionary will store the count of successful matches for each keyword pattern.
# It uses defaultdict(int) so that if a key doesn't exist, it's automatically initialized to 0.
KEYWORD_FREQUENCY = defaultdict(int)

# --- Pre-compiled Regular Expressions for Performance ---
# Compiling regex patterns once at the module level is more efficient than re-compiling
# them every time they are used inside a loop.
YEAR_PATTERN = re.compile(r'\b(20\d{2})\b')
EPS_VALUE_PATTERN = re.compile(r'^\(?\s*\$?\s*(\d+\.\d+)\s*\)?$')

# --- Keyword Configuration ---
# This dictionary organizes keyword patterns by priority. The script searches for "basic"
# patterns first, then "diluted", and finally "generic". This ensures that the most
# specific and desirable EPS value (e.g., Basic, Unadjusted) is found first.
EPS_KEYWORD_PATTERNS = {
    "basic": [
        re.compile(r"basic earnings per (common )?share", re.IGNORECASE),
        re.compile(r"net (income|earnings)( \(loss\))? per (common )?share\s*[-—]\s*basic", re.IGNORECASE),
        re.compile(r"(income|loss) \(loss\)? per share\s*[-—]\s*basic", re.IGNORECASE),
        re.compile(r"\bbasic eps\b", re.IGNORECASE),
        re.compile(r"\bbasic\b", re.IGNORECASE),
    ],
    "diluted": [
        re.compile(r"diluted earnings per (common )?share", re.IGNORECASE),
        re.compile(r"net (income|earnings)( \(loss\))? per (common )?share\s*[-—]\s*diluted", re.IGNORECASE),
        re.compile(r"(income|loss) \(loss\)? per share\s*[-—]\s*diluted", re.IGNORECASE),
        re.compile(r"\bdiluted eps\b", re.IGNORECASE),
        re.compile(r"per diluted (common )?share", re.IGNORECASE),
    ],
    "generic": [
        re.compile(r"\beps\b", re.IGNORECASE),
        re.compile(r"(net )?(income|loss|earnings)( \(loss\))? per (common )?share", re.IGNORECASE),
        re.compile(r"per (common )?share", re.IGNORECASE),
    ]
}


def _format_eps_value(raw_string):
    """
    Formats a raw string containing a number into a standardized EPS value string.
    This function correctly handles negative numbers, which are often denoted by parentheses
    in financial statements.
    
    Example: "(0.41)" is converted to "-0.41".
    
    Args:
        raw_string (str): The raw text extracted from an HTML cell.

    Returns:
        str: The formatted EPS value as a string, or None if no number is found.
    """
    if not raw_string:
        return None
    
    # A value is considered negative if it's enclosed in parentheses.
    is_negative = '(' in raw_string
    
    # Extract the numeric part of the string (e.g., "0.41" from "($0.41)").
    numeric_match = re.search(r'(\d+\.\d+)', raw_string)
    
    if numeric_match:
        numeric_part = numeric_match.group(1)
        # Prepend a hyphen if the value was determined to be negative.
        return f"-{numeric_part}" if is_negative else numeric_part
        
    return None


def _get_search_direction(table):
    """
    Analyzes a table's header to determine the chronological order of its columns.
    Many financial tables list the most recent quarter first (left), but some do the opposite.
    This function returns a 'direction' to guide the search for the EPS value.

    Args:
        table (bs4.element.Tag): The BeautifulSoup object for a single HTML table.

    Returns:
        str: 'left-to-right' or 'right-to-left', indicating the search direction.
    """
    header_rows = table.find_all('tr', limit=5) # Limit search to the first 5 rows for efficiency.
    year_positions = []

    # Find all year numbers (e.g., "2020") in the header and record their column index.
    for row in header_rows:
        for i, cell in enumerate(row.find_all(['th', 'td'])):
            matches = YEAR_PATTERN.findall(cell.get_text(strip=True))
            if matches:
                year_positions.append({'year': int(matches[0]), 'index': i})

    # If no years are found in the header, default to a standard left-to-right search.
    if not year_positions:
        return 'left-to-right'

    # Determine which year is the most recent (highest number).
    most_recent = max(year_positions, key=lambda x: x['year'])
    # Determine which year is the oldest (lowest number).
    oldest = min(year_positions, key=lambda x: x['year'])

    # If the most recent year's column index is greater than the oldest, it's on the right.
    if most_recent['index'] > oldest['index']:
        return 'right-to-left'
    else:
        return 'left-to-right'


def _find_value_in_row(cells, search_direction):
    """
    Iterates through a list of table cells in a specified direction (left-to-right or
    right-to-left) and returns the first valid EPS value found.

    Args:
        cells (list): A list of BeautifulSoup cell elements (<td> or <th>).
        search_direction (str): The direction to search ('left-to-right' or 'right-to-left').

    Returns:
        str: The extracted EPS value, or None if not found.
    """
    # Set the iteration order based on the determined search direction.
    cell_iterator = reversed(cells) if search_direction == 'right-to-left' else cells
    for cell in cell_iterator:
        cell_text = cell.get_text(strip=True)
        # Check if the cell's content matches the pattern for an EPS value.
        if EPS_VALUE_PATTERN.match(cell_text):
            eps_value = _format_eps_value(cell_text)
            if eps_value:
                return eps_value
    return None


def _parse_eps_from_tables(soup):
    """
    Strategy 1: Finds the EPS value by searching all financial tables in the document.
    This function respects the keyword priority and dynamically determines the search
    direction for each table.

    Args:
        soup (bs4.BeautifulSoup): The BeautifulSoup object for the entire HTML document.

    Returns:
        tuple: A tuple containing (eps_value, method, keyword_pattern) if successful,
               otherwise (None, None, None).
    """
    try:
        # Loop through the keyword priorities ('basic', then 'diluted', then 'generic').
        for priority in ["basic", "diluted", "generic"]:
            # Loop through each pre-compiled regex pattern within that priority group.
            for pattern in EPS_KEYWORD_PATTERNS[priority]:
                # Search every table for the current high-priority pattern.
                for table in soup.find_all('table'):
                    search_direction = _get_search_direction(table)
                    rows = table.find_all('tr')

                    for i, row in enumerate(rows):
                        row_text = ' '.join(row.get_text(strip=True).split())
                        # If the pattern is found in the row's text...
                        if pattern.search(row_text):
                            # ...first, try to find the value in the current row.
                            cells = row.find_all(['td', 'th'])
                            eps_value = _find_value_in_row(cells, search_direction)
                            if eps_value:
                                method = f"Table ({'R-L' if search_direction == 'right-to-left' else 'L-R'} Search)"
                                return eps_value, method, pattern.pattern

                            # If not found, check the next row, as some formats place the value there.
                            if i + 1 < len(rows):
                                next_row_cells = rows[i + 1].find_all(['td', 'th'])
                                eps_value = _find_value_in_row(next_row_cells, search_direction)
                                if eps_value:
                                    method = f"Table (Next Row, {'R-L' if search_direction == 'right-to-left' else 'L-R'} Search)"
                                    return eps_value, method, pattern.pattern
        return None, None, None
    except Exception as e:
        logging.error(f"  > An unexpected error occurred during table parsing: {e}")
        return None, None, None


def _parse_eps_with_regex(soup):
    """
    Strategy 2 (Fallback): Finds the EPS value by running regex patterns against the
    entire raw text of the document. This is less reliable than table parsing but
    is a good fallback.

    Args:
        soup (bs4.BeautifulSoup): The BeautifulSoup object for the entire HTML document.
        
    Returns:
        tuple: A tuple containing (eps_value, method, keyword_pattern) if successful,
               otherwise (None, None, None).
    """
    full_text = ' '.join(soup.get_text(strip=True).split())

    for priority in ["basic", "diluted", "generic"]:
        for pattern in EPS_KEYWORD_PATTERNS[priority]:
            # Dynamically build a search pattern to find the keyword followed by a number.
            # The ".{0,50}?" part creates a non-greedy search window of up to 50 characters.
            regex = re.compile(pattern.pattern + r".{0,50}?(\(?\$\s?\d+\.\d+\)?)", re.IGNORECASE)
            match = regex.search(full_text)
            if match:
                eps_value = _format_eps_value(match.group(1))
                if eps_value:
                    return eps_value, "Regex", pattern.pattern
    return None, None, None


def parse_html_filing(file_path):
    """
    Orchestrates the parsing of a single HTML file by applying strategies in order.

    Args:
        file_path (str): The full path to the HTML filing.

    Returns:
        tuple: A tuple containing (filename, eps_value).
    """
    start_time = time.time()
    filename = os.path.basename(file_path)
    logging.info(f"--- Starting analysis for {filename} ---")
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            soup = BeautifulSoup(f, 'lxml')

        # Attempt to find EPS using the most reliable method first (tables).
        eps_value, method, keyword_pattern = _parse_eps_from_tables(soup)

        # If the table search fails, fall back to the regex search on the full text.
        if eps_value is None:
            logging.info(f"  [i] No EPS found in tables for {filename}. Attempting regex search.")
            eps_value, method, keyword_pattern = _parse_eps_with_regex(soup)
        
        duration = time.time() - start_time
        
        if keyword_pattern:
            # If a match was found, record which keyword pattern was successful.
            KEYWORD_FREQUENCY[keyword_pattern] += 1
            logging.info(f"  [SUCCESS] Found EPS: {eps_value} | Method: {method} | Keyword: '{keyword_pattern}' | Time: {duration:.2f}s")
        else:
            logging.warning(f"  [FAILURE] Could not find EPS for {filename}. | Time: {duration:.2f}s")

        return filename, eps_value

    except Exception as e:
        duration = time.time() - start_time
        logging.error(f"  [CRITICAL] An unexpected error occurred while parsing {filename}: {e} | Time: {duration:.2f}s")
        return filename, None


def setup_logging(log_file):
    """
    Configures the logging system to output messages to both a specified file and the console.
    
    Args:
        log_file (str): The path to the log file.
    """
    # Ensure the directory for the log file exists.
    log_dir = os.path.dirname(log_file)
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir)

    # Configure the root logger.
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        # 'w' mode overwrites the log file on each run, creating a fresh log.
        # Use 'a' to append to the log file instead.
        handlers=[
            logging.FileHandler(log_file, mode='w'),
            logging.StreamHandler() # This handler sends logs to the console.
        ]
    )


def main(input_dir, output_file, log_file):
    """
    The main execution function of the script. It handles file discovery,
    orchestrates the parsing loop, and generates the final CSV and reports.
    """
    setup_logging(log_file)
    total_start_time = time.time()
    
    logging.info("="*25 + " Starting EDGAR EPS Parser " + "="*25)
    
    if not os.path.isdir(input_dir):
        logging.error(f"Error: Input directory not found at '{input_dir}'")
        return

    # Discover all HTML files in the input directory.
    files_to_process = [f for f in os.listdir(input_dir) if f.lower().endswith((".html", ".htm"))]
    if not files_to_process:
        logging.warning("No HTML files found in the input directory.")
        return
        
    logging.info(f"Found {len(files_to_process)} HTML file(s) to process in '{input_dir}'")
    
    # Process each file and store the results.
    results = []
    for filename in files_to_process:
        file_path = os.path.join(input_dir, filename)
        fname, eps = parse_html_filing(file_path)
        results.append({
            "filename": fname,
            "EPS": eps if eps is not None else "Not Found"
        })

    # Write the collected results to a CSV file.
    logging.info(f"Consolidating {len(results)} results and writing to '{output_file}'...")
    df = pd.DataFrame(results)
    try:
        df.to_csv(output_file, index=False)
        logging.info("CSV file written successfully.")
    except Exception as e:
        logging.error(f"Error writing to output file '{output_file}': {e}")
        
    # --- Final Performance and Analytics Summary ---
    total_duration = time.time() - total_start_time
    average_time = total_duration / len(files_to_process) if files_to_process else 0
    
    logging.info("\n" + "="*27 + " Parsing Complete " + "="*28)
    logging.info(f"Total files processed: {len(files_to_process)}")
    logging.info(f"Total time taken: {total_duration:.2f} seconds")
    logging.info(f"Average time per file: {average_time:.2f} seconds")
    
    if KEYWORD_FREQUENCY:
        logging.info("\n--- Keyword Frequency Report ---")
        sorted_keywords = sorted(KEYWORD_FREQUENCY.items(), key=lambda item: item[1], reverse=True)
        for keyword, count in sorted_keywords:
            logging.info(f'{count} match(es) for: "{keyword}"')
    else:
        logging.warning("\nNo keywords resulted in a successful match.")


# This block ensures that the script runs only when executed directly,
# not when imported as a module into another script.
if __name__ == "__main__":
    # Set up the command-line argument parser.
    parser = argparse.ArgumentParser(
        description="Parse quarterly EPS from EDGAR 8-K filings.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        'input_dir',
        help="Path to the input directory containing HTML filings.\nExample: /home/user/Training_Filings/"
    )
    parser.add_argument(
        'output_file',
        help="Path for the output CSV file.\nExample: /home/user/output.csv"
    )
    parser.add_argument(
        '--log_file',
        default='parser.log',
        help="Path for the output log file. Defaults to 'parser.log'."
    )

    args = parser.parse_args()
    main(args.input_dir, args.output_file, args.log_file)