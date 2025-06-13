#!/usr/bin/env python3

import os
import os.path
import json
import re
import sys
from datetime import datetime
import time
import threading
from concurrent.futures import ThreadPoolExecutor
import queue

# Parse command line arguments first (before imports that might fail)
if len(sys.argv) > 1 and sys.argv[1].lower() in ['--help', '-h']:
    print("AWS Heroes Scraper - Parallel Version")
    print("Usage: python aws_heroes_scraper.py [OPTIONS]")
    print("")
    print("Options:")
    print("  -s, --single-page    Scrape only the first page")
    print("  -a, --all-pages      Scrape all 6 pages in parallel (default)")
    print("  -h, --help           Show this help message")
    print("")
    print("Output:")
    print("  Creates separate JSONL files for each page: hero-page-{N}-{timestamp}.jsonl")
    print("  State Management:")
    print("  The script maintains state in ./state/heroes.json")
    sys.exit(0)

# Import NovaAct after help check
from nova_act import NovaAct

# Configuration - Default to scraping all pages
scrape_all_pages = True

# Parse remaining command line arguments
if len(sys.argv) > 1:
    if sys.argv[1].lower() in ['--single-page', '-s']:
        scrape_all_pages = False
        print("Running in single-page mode")
    elif sys.argv[1].lower() in ['--all-pages', '-a']:
        scrape_all_pages = True
        print("Running in all-pages mode (6 pages in parallel)")

# Total number of pages (given by user)
TOTAL_PAGES = 6

# Load API key from environment variable
api_key = os.environ.get("NOVA_ACT_API_KEY")
if not api_key:
    print("Error: NOVA_ACT_API_KEY environment variable is not set.")
    print("Please set it by running: export NOVA_ACT_API_KEY='your-api-key-here'")
    exit(1)

# Create output and state directories if they don't exist
output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output", "heroes")
state_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "state")
os.makedirs(output_dir, exist_ok=True)
os.makedirs(state_dir, exist_ok=True)

# State file to track scraped heroes
state_file = os.path.join(state_dir, "heroes.json")

# Generate timestamp for filename
timestamp = datetime.now().strftime("%H%M%S")

# AWS Heroes URL (starting with page 1)
aws_heroes_base_url = "https://aws.amazon.com/developer/community/heroes/?community-heroes-all.sort-by=item.additionalFields.sortPosition&community-heroes-all.sort-order=asc&awsf.filter-hero-category=*all&awsf.filter-location=location%23namer&awsf.filter-year=*all&awsf.filter-activity=*all"

# Helper template for pagination via URL parameter
aws_heroes_url_template = aws_heroes_base_url + "&awsm.page-community-heroes-all={page_num}"

def load_state():
    """Load the current state of scraped heroes"""
    if os.path.exists(state_file):
        try:
            with open(state_file, 'r') as f:
                data = json.load(f)
                return data.get('scraped_heroes', [])
        except (json.JSONDecodeError, FileNotFoundError):
            return []
    return []

def save_state(scraped_heroes):
    """Save the current state of scraped heroes"""
    state_data = {
        'scraped_heroes': scraped_heroes,
        'last_updated': datetime.now().isoformat(),
        'total_count': len(scraped_heroes)
    }
    try:
        with open(state_file, 'w') as f:
            json.dump(state_data, f, indent=2)
    except Exception as e:
        print(f"Warning: Could not save state: {e}")

def is_hero_already_scraped(hero, scraped_heroes):
    """Check if a hero has already been scraped"""
    for scraped in scraped_heroes:
        if (scraped.get('name') == hero.get('name') and 
            scraped.get('profile_url') == hero.get('profile_url')):
            return True
    return False

def extract_json_from_text(text, scraped_heroes):
    """Extract JSON objects from text response, filtering out already scraped heroes"""
    if not text:
        return []

    valid_heroes = []

    # 1) Try loading the entire text as JSON first (handles JSON arrays directly returned)
    try:
        loaded = json.loads(text)
        if isinstance(loaded, list):
            iterable = loaded
        elif isinstance(loaded, dict):
            iterable = [loaded]
        else:
            iterable = []
        for hero_data in iterable:
            if not isinstance(hero_data, dict):
                continue
            # Validate required fields
            if all(key in hero_data for key in ['name', 'profile_url', 'subject']):
                hero_data['name'] = hero_data['name'].strip()
                hero_data['profile_url'] = hero_data['profile_url'].strip()
                hero_data['subject'] = hero_data['subject'].strip()

                if is_hero_already_scraped(hero_data, scraped_heroes):
                    print(f"  Skipping already scraped hero: {hero_data['name']}")
                    continue

                if not any(h['name'] == hero_data['name'] and h['profile_url'] == hero_data['profile_url'] for h in valid_heroes):
                    valid_heroes.append(hero_data)
        # If we successfully parsed an array or object, return early
        if valid_heroes:
            return valid_heroes
    except (json.JSONDecodeError, TypeError):
        # Fall back to line-by-line extraction below
        pass

    # 2) Fallback: scan line-by-line for embedded JSON objects
    lines = text.split('\n')
    for line in lines:
        line = line.strip()

        if not line:
            continue

        # If the whole line is an array like [ {...}, {...} ] process it
        if line.startswith('['):
            try:
                arr = json.loads(line)
                if isinstance(arr, list):
                    lines.extend([json.dumps(obj) for obj in arr])
                continue
            except json.JSONDecodeError:
                pass

        # Identify potential JSON object substrings
        if '{' not in line:
            continue
        try:
            # Extract substring representing JSON object
            start = line.find('{')
            end = line.rfind('}') + 1
            if start < 0 or end <= start:
                continue
            obj_str = line[start:end]
            hero_data = json.loads(obj_str)

            if all(key in hero_data for key in ['name', 'profile_url', 'subject']):
                hero_data['name'] = hero_data['name'].strip()
                hero_data['profile_url'] = hero_data['profile_url'].strip()
                hero_data['subject'] = hero_data['subject'].strip()

                if is_hero_already_scraped(hero_data, scraped_heroes):
                    print(f"  Skipping already scraped hero: {hero_data['name']}")
                    continue

                if not any(h['name'] == hero_data['name'] and h['profile_url'] == hero_data['profile_url'] for h in valid_heroes):
                    valid_heroes.append(hero_data)
        except (json.JSONDecodeError, KeyError, AttributeError):
            continue

    return valid_heroes

def scrape_page(page_num, scraped_heroes_list, result_queue):
    """Scrape heroes from a specific page number"""
    page_output_file = os.path.join(output_dir, f"hero-page-{page_num}-{timestamp}.jsonl")
    page_debug_file = os.path.join(output_dir, f"hero-page-{page_num}-{timestamp}_debug.txt")
    
    nova = None
    try:
        print(f"[Page {page_num}] Starting scraper...")
        
        # Add a small delay to stagger browser starts
        time.sleep(page_num * 2)  # 2 second delay per page to avoid conflicts
        
        # Initialize Nova Act for this page - use headless mode for stability
        page_url = aws_heroes_url_template.format(page_num=page_num)
        nova = NovaAct(
            starting_page=page_url,
            headless=True  # Use headless mode for better stability in parallel
        )
        
        print(f"[Page {page_num}] Starting browser and navigating to {page_url}")
        nova.start()
        time.sleep(8)  # Give more time for page to load
        
        print(f"[Page {page_num}] Verifying page loaded correctly...")
        
        # First verify the page loaded correctly
        verification_result = nova.act(f"""
        Check if the AWS Heroes page loaded correctly:
        1. Can you see AWS Hero cards on this page?
        2. What is the current URL in the browser?
        3. Are there any error messages visible?
        
        Respond with exactly one of:
        - "SUCCESS" if you see hero cards and no errors
        - "ERROR: [description]" if there are problems
        """)
        
        verification_response = (verification_result.response or "").strip()
        print(f"[Page {page_num}] Page verification: {verification_response}")
        
        if not verification_response.startswith("SUCCESS"):
            raise Exception(f"Page verification failed: {verification_response}")
        
        print(f"[Page {page_num}] Extracting hero information...")
        
        # Extract hero data with detailed instructions
        result = nova.act("""
        Please extract ALL AWS Heroes information from this page. For each hero card visible, provide:
        1. Name: The person's full name
        2. Profile URL: The complete URL that clicking on the hero card/name would take you to (look for href attributes)
        3. Subject: The AWS hero category shown on their badge (like "AWS Container Hero", "AWS Serverless Hero", "AWS Machine Learning Hero", etc.)
        
        IMPORTANT: Provide the output as valid JSON objects, one per line, in exactly this format:
        {"name": "John Doe", "profile_url": "https://aws.amazon.com/developer/community/heroes/john-doe/", "subject": "AWS Serverless Hero"}
        
        Make sure to:
        - Get the complete profile URLs (they typically start with https://aws.amazon.com/developer/community/heroes/)
        - Get the exact hero category text from their badge
        - Include ALL heroes visible on the current page
        - Only output valid JSON, no other text
        - If you see no heroes, respond with "NO_HEROES_FOUND"
        """)
        
        heroes_data = result.response or ""
        print(f"[Page {page_num}] Extracted data. Response length: {len(heroes_data)}")
        
        if heroes_data.strip() == "NO_HEROES_FOUND":
            print(f"[Page {page_num}] No heroes found on this page")
            page_heroes = []
        else:
            # Extract heroes from response
            page_heroes = extract_json_from_text(heroes_data, scraped_heroes_list)
        
        # Add page number to each hero for tracking
        for hero in page_heroes:
            hero['page_scraped'] = page_num
            hero['scraped_timestamp'] = datetime.now().isoformat()
        
        print(f"[Page {page_num}] Found {len(page_heroes)} heroes")
        
        # Write page results to individual JSONL file
        with open(page_output_file, 'w') as f:
            for hero in page_heroes:
                f.write(json.dumps(hero) + '\n')
        
        # Write debug info for this page
        with open(page_debug_file, 'w') as f:
            f.write(f"AWS Heroes Scraping Debug Info - Page {page_num}\n")
            f.write(f"Timestamp: {datetime.now()}\n")
            f.write(f"Page URL: {page_url}\n")
            f.write(f"Verification Response: {verification_response}\n")
            f.write(f"Heroes found: {len(page_heroes)}\n")
            f.write(f"Raw response length: {len(heroes_data)}\n\n")
            
            f.write(f"Raw response data:\n")
            f.write("-" * 50 + "\n")
            f.write(heroes_data[:2000] + ("..." if len(heroes_data) > 2000 else "") + "\n")
            f.write("-" * 50 + "\n\n")
            
            f.write(f"Heroes found on page {page_num}:\n")
            for i, hero in enumerate(page_heroes):
                f.write(f"{i+1}. {hero['name']} - {hero['subject']} - {hero['profile_url']}\n")
        
        # Show sample of heroes found
        for i, hero in enumerate(page_heroes[:3]):
            print(f"[Page {page_num}] Hero {i+1}: {hero['name']} - {hero['subject']}")
        
        result_info = {
            'page_num': page_num,
            'heroes_count': len(page_heroes),
            'heroes': page_heroes,
            'output_file': page_output_file,
            'debug_file': page_debug_file,
            'success': True,
            'error': None
        }
        
        print(f"[Page {page_num}] Completed successfully!")
        
    except Exception as e:
        error_msg = str(e)
        print(f"[Page {page_num}] Error: {error_msg}")
        
        # Import traceback for detailed error info
        import traceback
        detailed_error = traceback.format_exc()
        
        result_info = {
            'page_num': page_num,
            'heroes_count': 0,
            'heroes': [],
            'output_file': page_output_file,
            'debug_file': page_debug_file,
            'success': False,
            'error': error_msg
        }
        
        # Write error info to debug file
        try:
            with open(page_debug_file, 'w') as f:
                f.write(f"AWS Heroes Scraping Error - Page {page_num}\n")
                f.write(f"Timestamp: {datetime.now()}\n")
                f.write(f"Page URL: {aws_heroes_url_template.format(page_num=page_num)}\n")
                f.write(f"Error: {error_msg}\n\n")
                f.write(f"Detailed traceback:\n")
                f.write(detailed_error)
        except Exception as debug_error:
            print(f"[Page {page_num}] Could not write debug file: {debug_error}")
    
    finally:
        # Always try to stop the browser
        if nova:
            try:
                nova.stop()
            except Exception as stop_error:
                print(f"[Page {page_num}] Error stopping browser: {stop_error}")
    
    # Put result in queue for main thread
    result_queue.put(result_info)

def main():
    try:
        # Load existing state
        print("Loading existing state...")
        scraped_heroes = load_state()
        print(f"Found {len(scraped_heroes)} already scraped heroes in state")
        
        # Determine which pages to scrape
        if scrape_all_pages:
            pages_to_scrape = list(range(1, TOTAL_PAGES + 1))
            print(f"Will scrape all {TOTAL_PAGES} pages in parallel")
        else:
            pages_to_scrape = [1]
            print("Will scrape only page 1")
        
        # Create a queue to collect results
        result_queue = queue.Queue()
        
        # Use ThreadPoolExecutor with limited workers to avoid resource conflicts
        max_parallel = min(3, len(pages_to_scrape))  # Limit to 3 parallel browsers
        print(f"\nStarting parallel scraping of {len(pages_to_scrape)} pages (max {max_parallel} parallel)...")
        
        with ThreadPoolExecutor(max_workers=max_parallel) as executor:
            # Submit all page scraping tasks
            futures = []
            for page_num in pages_to_scrape:
                future = executor.submit(scrape_page, page_num, scraped_heroes, result_queue)
                futures.append(future)
            
            # Wait for all tasks to complete
            for future in futures:
                try:
                    future.result()  # This will raise any exceptions that occurred
                except Exception as e:
                    print(f"Task failed with exception: {e}")
        
        # Collect all results
        page_results = []
        while not result_queue.empty():
            page_results.append(result_queue.get())
        
        # Sort results by page number
        page_results.sort(key=lambda x: x['page_num'])
        
        # Combine all new heroes and update state
        all_new_heroes = []
        successful_pages = 0
        
        print(f"\n=== Results Summary ===")
        for result in page_results:
            if result['success']:
                successful_pages += 1
                all_new_heroes.extend(result['heroes'])
                print(f"Page {result['page_num']}: {result['heroes_count']} heroes -> {result['output_file']}")
            else:
                print(f"Page {result['page_num']}: ERROR - {result['error']}")
        
        # Update state with all new heroes
        scraped_heroes.extend(all_new_heroes)
        save_state(scraped_heroes)
        
        print(f"\n=== Final Summary ===")
        print(f"Successfully scraped: {successful_pages}/{len(pages_to_scrape)} pages")
        print(f"New heroes found: {len(all_new_heroes)}")
        print(f"Total heroes in state: {len(scraped_heroes)}")
        
        # Create a combined summary file
        summary_file = os.path.join(output_dir, f"hero-summary-{timestamp}.json")
        summary_data = {
            'timestamp': datetime.now().isoformat(),
            'pages_scraped': len(pages_to_scrape),
            'successful_pages': successful_pages,
            'new_heroes_count': len(all_new_heroes),
            'total_heroes_count': len(scraped_heroes),
            'page_results': page_results
        }
        
        with open(summary_file, 'w') as f:
            json.dump(summary_data, f, indent=2)
        
        print(f"Summary saved to: {summary_file}")
        
        # Show category breakdown
        if all_new_heroes:
            new_subjects = {}
            for hero in all_new_heroes:
                subject = hero['subject']
                new_subjects[subject] = new_subjects.get(subject, 0) + 1
            
            print(f"\nNew hero categories found:")
            for subject, count in sorted(new_subjects.items()):
                print(f"  {subject}: {count}")
        
        print(f"\nIndividual page files created:")
        for result in page_results:
            if result['success']:
                print(f"  {result['output_file']}")
        
        print(f"\nCheck debug files for detailed information:")
        for result in page_results:
            print(f"  {result['debug_file']}")
        
        # Wait for user input before finishing
        input("\nPress Enter to finish...")
        
    except KeyboardInterrupt:
        print("\nScraping interrupted by user")
    except Exception as e:
        print(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main() 