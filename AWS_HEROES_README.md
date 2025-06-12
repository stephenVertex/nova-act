# AWS Heroes Scraper

This script scrapes AWS Community Heroes data from the AWS Developer Community Heroes page and saves it to a JSONL file.

## Prerequisites

1. Set up your Nova Act API key:
   ```bash
   export NOVA_ACT_API_KEY='your-api-key-here'
   ```

2. Make sure you have a browser session saved (using the existing `.user_data_dir` from other scripts in this project).

## Usage

### Run with all pages (default behavior):
```bash
python aws_heroes_scraper.py
```

or explicitly:
```bash
python aws_heroes_scraper.py --all-pages
```

### Run with single page only:
```bash
python aws_heroes_scraper.py --single-page
```

### Show help:
```bash
python aws_heroes_scraper.py --help
```

## Output

The script will create:
- `./output/heroes/hero-{HHMMSS}.jsonl` - Main output file with hero data (all heroes in state)
- `./output/heroes/hero-{HHMMSS}_debug.txt` - Debug information and summary
- `./state/heroes.json` - Persistent state file tracking all scraped heroes

Each line in the JSONL file contains a JSON object with:
- `name`: The hero's full name
- `profile_url`: URL to their AWS Heroes profile page
- `subject`: Their hero category (e.g., "AWS Serverless Hero", "AWS Machine Learning Hero")

## State Management

The script maintains a persistent state file at `./state/heroes.json` that contains:
- All successfully scraped heroes
- Last updated timestamp
- Total count of heroes

This allows the script to:
- Skip heroes that have already been scraped
- Resume from where it left off after interruption
- Avoid duplicate work when rerunning

The state is saved after each page is processed, so even if the script crashes, minimal progress is lost.

## Example Output

```json
{"name": "John Doe", "profile_url": "https://aws.amazon.com/developer/community/heroes/john-doe/", "subject": "AWS Serverless Hero"}
{"name": "Jane Smith", "profile_url": "https://aws.amazon.com/developer/community/heroes/jane-smith/", "subject": "AWS Machine Learning Hero"}
```

## Features

- **State Management**: Maintains a persistent state file (`./state/heroes.json`) to track successfully scraped heroes
- **Resume Capability**: Can restart or recover from crashes without re-scraping existing heroes
- **Pagination Support**: Can scrape all pages or just the first page
- **Real-time State Saving**: Saves state after each page to prevent data loss
- **Debug Information**: Saves detailed debug info including page-by-page statistics
- **Error Handling**: Robust JSON parsing with fallback error handling
- **Summary Statistics**: Shows breakdown of hero categories found, both total and new this session

## Notes

- The script uses a non-headless browser so you can see the scraping process
- It includes safety limits to prevent infinite loops (max 20 pages)
- The script waits between page loads to avoid rate limiting
- All output is saved with timestamps to avoid overwriting previous runs 