import csv
import requests
import json
import time
import os
import sys
import argparse
import random
from pathlib import Path

def load_processed_state(state_file_path: str) -> set[str]:
    """
    Load the set of already processed heroes from state file
    
    Args:
        state_file_path: Path to the state JSON file
        
    Returns:
        set: Set of processed hero identifiers (first_name|last_name)
    """
    try:
        if os.path.exists(state_file_path):
            with open(state_file_path, 'r', encoding='utf-8') as file:
                data = json.load(file)
                return set(data.get('processed_heroes', []))
        return set()
    except Exception as e:
        print(f"⚠️  Warning: Could not load state file: {str(e)}")
        return set()

def save_processed_state(state_file_path: str, processed_heroes: set[str]) -> None:
    """
    Save the set of processed heroes to state file with forced disk flush
    
    Args:
        state_file_path: Path to the state JSON file
        processed_heroes: Set of processed hero identifiers
    """
    try:
        # Ensure state directory exists
        state_dir = os.path.dirname(state_file_path)
        if state_dir:
            os.makedirs(state_dir, exist_ok=True)
        
        data = {
            'processed_heroes': sorted(list(processed_heroes)),
            'last_updated': time.strftime('%Y-%m-%d %H:%M:%S')
        }
        
        with open(state_file_path, 'w', encoding='utf-8') as file:
            json.dump(data, file, indent=2, ensure_ascii=False)
            file.flush()  # Force write to disk
            os.fsync(file.fileno())  # Force OS to write to physical disk
    except Exception as e:
        print(f"⚠️  Warning: Could not save state file: {str(e)}")

def countdown_sleep(seconds: int) -> None:
    """
    Sleep for specified seconds while displaying countdown
    
    Args:
        seconds: Number of seconds to sleep
    """
    print(f"⏰ Waiting {seconds} seconds before next request...")
    for remaining in range(seconds, 0, -1):
        minutes, secs = divmod(remaining, 60)
        timer = f"{minutes:02d}:{secs:02d}"
        print(f"\r⏳ Time remaining: {timer}", end="", flush=True)
        time.sleep(1)
    print("\r✅ Wait complete!                    ")  # Clear the countdown line

def get_hero_id(first_name: str, last_name: str) -> str:
    """
    Generate a unique identifier for a hero
    
    Args:
        first_name: Hero's first name
        last_name: Hero's last name
        
    Returns:
        str: Unique hero identifier
    """
    return f"{first_name}|{last_name}"

def make_hero_request(first_name: str, last_name: str, endpoint_url: str) -> bool:
    """
    Make HTTP POST request for a single hero
    
    Args:
        first_name: Hero's first name
        last_name: Hero's last name  
        endpoint_url: API endpoint URL
        
    Returns:
        bool: True if request successful, False otherwise
    """
    payload = {
        "first_name": first_name,
        "last_name": last_name,
        "company_name": "AWS Hero"
    }
    
    try:
        response = requests.post(
            endpoint_url,
            json=payload,
            headers={'Content-Type': 'application/json'},
            timeout=30
        )
        
        if response.status_code == 200:
            print(f"✅ Successfully processed: {first_name} {last_name}")
            return True
        else:
            print(f"❌ Failed to process {first_name} {last_name}: HTTP {response.status_code}")
            print(f"   Response: {response.text}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Error processing {first_name} {last_name}: {str(e)}")
        return False

def process_heroes_csv(csv_file_path: str, endpoint_url: str, state_file_path: str, 
                      process_all: bool = False, delay_seconds: float = 0.5) -> None:
    """
    Read CSV file and process heroes with state tracking
    
    Args:
        csv_file_path: Path to the CSV file
        endpoint_url: API endpoint URL
        state_file_path: Path to the state JSON file
        process_all: If True, process all heroes; if False, process only one
        delay_seconds: Base delay between requests (only used for single hero mode)
    """
    successful_requests = 0
    failed_requests = 0
    skipped_requests = 0
    
    # Load existing state
    processed_heroes = load_processed_state(state_file_path)
    
    try:
        # First, read all heroes to know the total count and which ones need processing
        all_heroes = []
        unprocessed_heroes = []
        
        with open(csv_file_path, 'r', encoding='utf-8') as file:
            csv_reader = csv.DictReader(file)
            
            for row_num, row in enumerate(csv_reader, start=1):
                first_name = row.get('first_name', '').strip()
                last_name = row.get('last_name', '').strip()
                
                if not first_name or not last_name:
                    continue  # Skip invalid rows
                
                hero_data = {
                    'row_num': row_num,
                    'first_name': first_name,
                    'last_name': last_name,
                    'hero_id': get_hero_id(first_name, last_name)
                }
                
                all_heroes.append(hero_data)
                
                # Check if already processed
                if hero_data['hero_id'] not in processed_heroes:
                    unprocessed_heroes.append(hero_data)
        
        mode_text = "all AWS Heroes" if process_all else "one AWS Hero"
        print(f"🚀 Processing {mode_text}...")
        print(f"📡 Endpoint: {endpoint_url}")
        print(f"💾 State file: {state_file_path}")
        if process_all:
            print(f"⏱️  Random delay: 90-120 seconds between requests")
        else:
            print(f"⏱️  Delay between requests: {delay_seconds}s")
        if processed_heroes:
            print(f"🔄 Found {len(processed_heroes)} already processed heroes")
        print(f"📋 Total heroes in CSV: {len(all_heroes)}")
        print(f"🎯 Heroes remaining to process: {len(unprocessed_heroes)}")
        print("-" * 60)
        
        if not unprocessed_heroes:
            print(f"🎯 All heroes have already been processed!")
            return
        
        # Process heroes
        for i, hero in enumerate(unprocessed_heroes):
            # Check if already processed (in case state changed during run)
            if hero['hero_id'] in processed_heroes:
                print(f"[{hero['row_num']}] ⏭️  Skipping {hero['first_name']} {hero['last_name']} (already processed)")
                skipped_requests += 1
                continue
            
            print(f"[{hero['row_num']}] Processing: {hero['first_name']} {hero['last_name']} ({i+1}/{len(unprocessed_heroes)})")
            
            if make_hero_request(hero['first_name'], hero['last_name'], endpoint_url):
                successful_requests += 1
                # Add to processed set and save state only on success
                processed_heroes.add(hero['hero_id'])
                save_processed_state(state_file_path, processed_heroes)
                print(f"💾 State saved and flushed to disk")
                
                if not process_all:
                    print(f"✨ Successfully processed one hero. Exiting.")
                    break  # Exit after processing one hero successfully
                
                # For --all mode, sleep with countdown before next hero (except for last hero)
                if process_all and i < len(unprocessed_heroes) - 1:  # Not the last hero
                    sleep_time = random.randint(90, 120)
                    countdown_sleep(sleep_time)
                    
            else:
                failed_requests += 1
                if not process_all:
                    print(f"❌ Failed to process hero. Exiting.")
                    break  # Exit even on failure (don't continue to next hero)
                else:
                    print(f"❌ Failed to process hero. Continuing with next hero...")
                    # Still sleep even on failure to avoid hammering the API
                    if i < len(unprocessed_heroes) - 1:  # Not the last hero
                        sleep_time = random.randint(90, 120)
                        countdown_sleep(sleep_time)
        
        if process_all and successful_requests > 0:
            print(f"🎯 Processed {successful_requests} heroes in this run!")
            
    except FileNotFoundError:
        print(f"❌ Error: CSV file not found at {csv_file_path}")
        return
    except KeyboardInterrupt:
        print(f"\n\n⚠️  Process interrupted by user")
        print(f"💾 Current state has been saved. You can resume later.")
        return
    except Exception as e:
        print(f"❌ Error reading CSV file: {str(e)}")
        return
    
    print("-" * 60)
    mode_text = "All Heroes" if process_all else "Single Hero"
    print(f"📊 {mode_text} Run Summary:")
    print(f"   ✅ Successful requests: {successful_requests}")
    print(f"   ❌ Failed requests: {failed_requests}")
    print(f"   ⏭️  Skipped (already processed): {skipped_requests}")
    if successful_requests > 0:
        if process_all:
            print(f"   🎯 Status: {successful_requests} heroes successfully processed")
        else:
            print(f"   🎯 Status: One hero successfully processed")
    elif failed_requests > 0:
        print(f"   🎯 Status: Processing failed")
    else:
        print(f"   🎯 Status: All heroes already processed")

def main():
    """Main function to run the script"""
    parser = argparse.ArgumentParser(
        description="Process AWS Heroes through API endpoint",
        epilog="Examples:\n"
               "  python process_heroes.py           # Process one hero\n"
               "  python process_heroes.py --all     # Process all heroes\n",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        '--all',
        action='store_true',
        help='Process all heroes instead of just one. Includes random 90-120 second delays between requests.'
    )
    
    args = parser.parse_args()
    
    # Configuration
    CSV_FILE_PATH = "data/all_heroes_export.csv"
    ENDPOINT_URL = "https://hook.relay.app/api/v1/playbook/cmbtx3qgs08q10pm28a1018yi/trigger/gomNnsQkbyl4Lu7pBLyN7g"
    STATE_FILE_PATH = "state/process_heroes.json"
    DELAY_SECONDS = 0.5  # Delay between requests for single hero mode
    
    mode_text = "All Heroes Mode" if args.all else "Single Hero Mode"
    print(f"🦸‍♂️ AWS Heroes Processor ({mode_text})")
    print("=" * 60)
    
    if args.all:
        print("⚠️  WARNING: --all flag is set. This will process ALL heroes!")
        print("⚠️  This may take a very long time (90-120 seconds between each hero).")
        print("⚠️  Press Ctrl+C to interrupt at any time. Progress will be saved.")
        print("-" * 60)
    
    # Process the heroes
    process_heroes_csv(
        CSV_FILE_PATH, 
        ENDPOINT_URL, 
        STATE_FILE_PATH, 
        process_all=args.all,
        delay_seconds=DELAY_SECONDS
    )
    
    completion_text = "processing complete!" if args.all else "single hero processing complete!"
    print(f"\n🎉 {completion_text}")

if __name__ == "__main__":
    main() 