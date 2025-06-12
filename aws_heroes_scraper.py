#!/usr/bin/env python3

import os
import os.path
import json
import re
import sys
from datetime import datetime
import time

# Parse command line arguments first (before imports that might fail)
if len(sys.argv) > 1 and sys.argv[1].lower() in ['--help', '-h']:
    print("AWS Heroes Scraper")
    print("Usage: python aws_heroes_scraper.py [OPTIONS]")
    print("")
    print("Options:")
    print("  -s, --single-page    Scrape only the first page")
    print("  -a, --all-pages      Scrape all pages (default)")
    print("  -h, --help           Show this help message")
    print("")
    print("State Management:")
    print("  The script maintains state in ./state/heroes.json")
    print("  It will skip already scraped heroes on restart")
    sys.exit(0)

# Import NovaAct after help check
from nova_act import NovaAct

# Configuration - Set to True to scrape all pages, False for just the first page
SCRAPE_ALL_PAGES = True

# Parse remaining command line arguments
if len(sys.argv) > 1:
    if sys.argv[1].lower() in ['--single-page', '-s']:
        SCRAPE_ALL_PAGES = False
        print("Running in single-page mode")
    elif sys.argv[1].lower() in ['--all-pages', '-a']:
        SCRAPE_ALL_PAGES = True
        print("Running in all-pages mode")

# Load API key from environment variable
api_key = os.environ.get("NOVA_ACT_API_KEY")
if not api_key:
    print("Error: NOVA_ACT_API_KEY environment variable is not set.")
    print("Please set it by running: export NOVA_ACT_API_KEY='your-api-key-here'")
    exit(1)

# Get the saved user_data_dir path
config_dir = os.path.dirname(os.path.abspath(__file__))
user_data_file = os.path.join(config_dir, ".user_data_dir")

if not os.path.exists(user_data_file):
    print("Error: No saved login session found.")
    print("Please run setup_envato_login.py first to create a persistent login session.")
    exit(1)

with open(user_data_file, "r") as f:
    user_data_dir = f.read().strip()

if not os.path.exists(user_data_dir):
    print(f"Error: User data directory '{user_data_dir}' not found.")
    print("Please run setup_envato_login.py to create a new session.")
    exit(1)

print(f"Using saved login session from: {user_data_dir}")

# Create output and state directories if they don't exist
output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output", "heroes")
state_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "state")
os.makedirs(output_dir, exist_ok=True)
os.makedirs(state_dir, exist_ok=True)

# State file to track scraped heroes
state_file = os.path.join(state_dir, "heroes.json")

# Generate timestamp for filename
timestamp = datetime.now().strftime("%H%M%S")
output_file = os.path.join(output_dir, f"hero-{timestamp}.jsonl")
debug_file = os.path.join(output_dir, f"hero-{timestamp}_debug.txt")

# AWS Heroes URL (starting with page 1)
aws_heroes_base_url = "https://aws.amazon.com/developer/community/heroes/?community-heroes-all.sort-by=item.additionalFields.sortPosition&community-heroes-all.sort-order=asc&awsf.filter-hero-category=*all&awsf.filter-location=location%23namer&awsf.filter-year=*all&awsf.filter-activity=*all"

# Initialize Nova Act with AWS Heroes page
nova = NovaAct(
    starting_page=aws_heroes_base_url + "&awsm.page-community-heroes-all=1",
    headless=False,
    user_data_dir=user_data_dir,
    clone_user_data_dir=False
)

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
    
    # Try to find JSON objects in the text
    lines = text.split('\n')
    for line in lines:
        line = line.strip()
        
        # Skip empty lines and non-JSON looking lines
        if not line or (not line.startswith('{') and '"name"' not in line):
            continue
            
        try:
            # Try to extract JSON from the line
            if not line.startswith('{'):
                # Find JSON within the line
                start = line.find('{')
                end = line.rfind('}') + 1
                if start >= 0 and end > start:
                    line = line[start:end]
            
            hero_data = json.loads(line)
            
            # Validate required fields
            if all(key in hero_data for key in ['name', 'profile_url', 'subject']):
                # Clean up the data
                hero_data['name'] = hero_data['name'].strip()
                hero_data['profile_url'] = hero_data['profile_url'].strip()
                hero_data['subject'] = hero_data['subject'].strip()
                
                # Skip if already scraped
                if is_hero_already_scraped(hero_data, scraped_heroes):
                    print(f"  Skipping already scraped hero: {hero_data['name']}")
                    continue
                
                # Skip duplicates in current batch
                if not any(h['name'] == hero_data['name'] and h['profile_url'] == hero_data['profile_url'] 
                          for h in valid_heroes):
                    valid_heroes.append(hero_data)
                    
        except (json.JSONDecodeError, KeyError, AttributeError):
            continue
    
    return valid_heroes

def scrape_current_page(scraped_heroes):
    """Scrape heroes from the current page"""
    print("Extracting hero information from current page...")
    
    # Wait for page to load completely
    result = nova.act("Wait for the page to fully load. Look for AWS hero cards with names, categories, and profile links.")
    
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
    """)
    
    heroes_data = result.response or ""
    print(f"Extracted data from current page. Response length: {len(heroes_data)}")
    
    return extract_json_from_text(heroes_data, scraped_heroes)

try:
    # Load existing state
    print("Loading existing state...")
    scraped_heroes = load_state()
    print(f"Found {len(scraped_heroes)} already scraped heroes in state")
    
    # Start the browser
    print("Starting browser...")
    nova.start()
    
    print("Loading AWS Heroes page...")
    time.sleep(3)  # Give page time to load
    
    new_heroes = []  # Only newly discovered heroes this session
    current_page = 1
    debug_info = []
    
    while True:
        print(f"\n--- Processing Page {current_page} ---")
        print(f"Total heroes in state: {len(scraped_heroes)}")
        
        # Scrape current page
        page_heroes = scrape_current_page(scraped_heroes)
        
        if page_heroes:
            print(f"Found {len(page_heroes)} new heroes on page {current_page}")
            new_heroes.extend(page_heroes)
            scraped_heroes.extend(page_heroes)
            
            # Save state after each page
            save_state(scraped_heroes)
            print(f"State saved with {len(scraped_heroes)} total heroes")
            
            # Show sample of heroes found
            for i, hero in enumerate(page_heroes[:3]):
                print(f"  New {i+1}: {hero['name']} - {hero['subject']}")
        else:
            print(f"No new heroes found on page {current_page}")
            # Still save state to record we processed this page
            save_state(scraped_heroes)
        
        # If single-page mode, stop after first page
        if not SCRAPE_ALL_PAGES:
            print("Single-page mode: stopping after first page.")
            break
        
        # Check for next page
        print("Checking for pagination...")
        pagination_result = nova.act("""
        Look for pagination controls at the bottom of the page. 
        Is there a "Next" button or page number for the next page that can be clicked?
        If yes, tell me "YES" and click on it to go to the next page.
        If no, tell me "NO" - we've reached the end.
        """)
        
        debug_info.append(f"Page {current_page}: {len(page_heroes)} new heroes, Total: {len(scraped_heroes)}, Pagination: {pagination_result.response}")
        
        if not pagination_result.response or "NO" in pagination_result.response.upper():
            print("No more pages found. Scraping complete.")
            break
        elif "YES" in pagination_result.response.upper():
            print("Moving to next page...")
            current_page += 1
            time.sleep(2)  # Wait for page to load
            
            # Safety check to avoid infinite loops
            if current_page > 20:  # Reasonable limit
                print("Reached maximum page limit (20). Stopping.")
                break
        else:
            print("Unclear pagination response. Stopping to be safe.")
            break
    
    print(f"\n=== Scraping Complete ===")
    print(f"New heroes found this session: {len(new_heroes)}")
    print(f"Total heroes in state: {len(scraped_heroes)}")
    print(f"Pages processed: {current_page}")
    
    # Save all heroes (from state) to JSONL file for this session's output
    with open(output_file, 'w') as f:
        for hero in scraped_heroes:
            f.write(json.dumps(hero) + '\n')
    
    # Save debug information
    with open(debug_file, 'w') as f:
        f.write(f"AWS Heroes Scraping Debug Info\n")
        f.write(f"Timestamp: {datetime.now()}\n")
        f.write(f"Mode: {'All pages' if SCRAPE_ALL_PAGES else 'Single page'}\n")
        f.write(f"New heroes found this session: {len(new_heroes)}\n")
        f.write(f"Total heroes in state: {len(scraped_heroes)}\n")
        f.write(f"Pages processed: {current_page}\n\n")
        
        for info in debug_info:
            f.write(f"{info}\n")
        
        f.write(f"\nNew heroes found this session:\n")
        for i, hero in enumerate(new_heroes):
            f.write(f"{i+1}. {hero['name']} - {hero['subject']} - {hero['profile_url']}\n")
        
        f.write(f"\nSample of all heroes in state:\n")
        for i, hero in enumerate(scraped_heroes[:10]):
            f.write(f"{i+1}. {hero['name']} - {hero['subject']} - {hero['profile_url']}\n")
    
    print(f"\nResults saved to: {output_file}")
    print(f"State saved to: {state_file}")
    print(f"Debug info saved to: {debug_file}")
    
    # Show summary
    if scraped_heroes:
        subjects = {}
        for hero in scraped_heroes:
            subject = hero['subject']
            subjects[subject] = subjects.get(subject, 0) + 1
        
        print(f"\nTotal hero categories in state:")
        for subject, count in sorted(subjects.items()):
            print(f"  {subject}: {count}")
    
    if new_heroes:
        new_subjects = {}
        for hero in new_heroes:
            subject = hero['subject']
            new_subjects[subject] = new_subjects.get(subject, 0) + 1
        
        print(f"\nNew hero categories found this session:")
        for subject, count in sorted(new_subjects.items()):
            print(f"  {subject}: {count}")
    
    # Wait for user input before closing
    input("\nPress Enter to close the browser...")
    
finally:
    # Always ensure we stop the browser properly
    print("Stopping browser...")
    nova.stop() 