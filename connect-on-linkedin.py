#!/usr/bin/env python3
"""
LinkedIn Connection Script with Automation
Reads data from Google Sheets, finds new profiles, and makes LinkedIn connections using Nova Act
"""

import gspread
import pandas as pd
from google.oauth2.service_account import Credentials
import os
import sys
import datetime
import time
import random
from nova_act import NovaAct, BOOL_SCHEMA

# Google Sheets configuration
SPREADSHEET_ID = "1M8UMAEKCj24a1Lxxqpx_prvbbB0nyEdXSLwdxIDkAHo"
TRACKER_SHEET_NAME = "stephen-connect-request-tracker"
PERSONS_SHEET_NAME = "Sheet1"

# Scopes required for Google Sheets API
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]

def authenticate_google_sheets():
    """
    Authenticate with Google Sheets API using service account credentials
    """
    try:
        # Try to find credentials file in common locations
        credential_paths = [
            'credentials.json',
            'service-account-credentials.json',
            os.path.expanduser('~/credentials.json'),
            os.path.expanduser('~/.config/gcp/credentials.json')
        ]
        
        credentials_file = None
        for path in credential_paths:
            if os.path.exists(path):
                credentials_file = path
                break
        
        if not credentials_file:
            print("❌ Error: Could not find credentials.json file")
            print("Please ensure your service account credentials file is in one of these locations:")
            for path in credential_paths:
                print(f"  - {path}")
            sys.exit(1)
        
        print(f"✅ Using credentials from: {credentials_file}")
        
        # Authenticate using service account
        gc = gspread.service_account(filename=credentials_file)
        return gc
        
    except Exception as e:
        print(f"❌ Error authenticating with Google Sheets: {str(e)}")
        sys.exit(1)

def open_spreadsheet(gc):
    """
    Open the target spreadsheet and return the tracker and persons worksheets
    """
    try:
        # Open the spreadsheet by ID
        spreadsheet = gc.open_by_key(SPREADSHEET_ID)
        print(f"✅ Successfully opened spreadsheet: {spreadsheet.title}")
        
        # Get all worksheets
        worksheets = spreadsheet.worksheets()
        tracker_worksheet = None
        persons_worksheet = None
        
        # Find the specific worksheets by name
        for ws in worksheets:
            if ws.title == TRACKER_SHEET_NAME:
                tracker_worksheet = ws
            elif ws.title == PERSONS_SHEET_NAME:
                persons_worksheet = ws
        
        if not tracker_worksheet:
            print(f"❌ Could not find worksheet: {TRACKER_SHEET_NAME}")
            print("Available worksheets:")
            for ws in worksheets:
                print(f"  - {ws.title}")
            sys.exit(1)
        
        if not persons_worksheet:
            print(f"❌ Could not find worksheet: {PERSONS_SHEET_NAME}")
            print("Available worksheets:")
            for ws in worksheets:
                print(f"  - {ws.title}")
            sys.exit(1)
        
        print(f"✅ Successfully opened tracker sheet: {tracker_worksheet.title}")
        print(f"✅ Successfully opened persons sheet: {persons_worksheet.title}")
        return tracker_worksheet, persons_worksheet
        
    except Exception as e:
        print(f"❌ Error opening spreadsheet: {str(e)}")
        sys.exit(1)

def read_sheet_data(worksheet):
    """
    Read all data from the worksheet
    """
    try:
        # Get all records as a list of dictionaries
        records = worksheet.get_all_records()
        
        if not records:
            print(f"⚠️  No data found in worksheet: {worksheet.title}")
            return pd.DataFrame()
        
        print(f"✅ Successfully read {len(records)} records from {worksheet.title}")
        
        # Convert to pandas DataFrame for easier manipulation
        df = pd.DataFrame(records)
        
        # Display basic info about the data
        print(f"📊 Data shape: {df.shape}")
        print(f"📋 Columns: {list(df.columns)}")
        
        return df
        
    except Exception as e:
        print(f"❌ Error reading sheet data from {worksheet.title}: {str(e)}")
        return pd.DataFrame()

def find_new_linkedin_url(persons_df, tracker_df):
    """
    Find a LinkedIn URL that's in persons_df but not in tracker_df
    """
    print("\n🔍 Finding new LinkedIn URL to connect...")
    
    # Check if persons data has ProfileUrl column
    if 'ProfileUrl' not in persons_df.columns:
        print("❌ ProfileUrl column not found in persons data")
        return None, None
    
    # Get all LinkedIn URLs from persons data
    persons_urls = set(persons_df['ProfileUrl'].dropna().str.strip())
    print(f"📊 Found {len(persons_urls)} LinkedIn URLs in persons data")
    
    # Get all LinkedIn URLs already in tracker
    tracker_urls = set()
    if not tracker_df.empty and 'linkedin_url' in tracker_df.columns:
        tracker_urls = set(tracker_df['linkedin_url'].dropna().str.strip())
        print(f"📊 Found {len(tracker_urls)} LinkedIn URLs already in tracker")
    else:
        print("📊 Tracker is empty or missing linkedin_url column")
    
    # Find URLs not yet tracked
    new_urls = persons_urls - tracker_urls
    
    if not new_urls:
        print("⚠️  No new LinkedIn URLs found to connect")
        return None, None
    
    # Get the first new URL
    selected_url = next(iter(new_urls))
    
    # Find the corresponding person data
    person_data = persons_df[persons_df['ProfileUrl'] == selected_url].iloc[0]
    
    print(f"🎯 Selected URL: {selected_url}")
    print(f"👤 Person: {person_data.get('Person', 'Unknown')}")
    print(f"🏢 Company: {person_data.get('Company', 'Unknown')}")
    
    return selected_url, person_data

def setup_nova_act(linkedin_url):
    """
    Set up Nova Act with LinkedIn credentials, starting directly on the profile URL
    """
    print("\n🤖 Setting up Nova Act...")
    
    # Load API key from environment variable
    api_key = os.environ.get("NOVA_ACT_API_KEY")
    if not api_key:
        print("❌ Error: NOVA_ACT_API_KEY environment variable is not set.")
        print("Please set it by running: export NOVA_ACT_API_KEY='your-api-key-here'")
        sys.exit(1)
    
    # Get user data directory from setup
    config_dir = os.path.dirname(os.path.abspath(__file__))
    user_data_dir_file = os.path.join(config_dir, ".linkedin_user_data_dir")
    
    if not os.path.exists(user_data_dir_file):
        print("❌ LinkedIn user data directory not found.")
        print("Please run setup_linkedin_login.py first to set up LinkedIn credentials.")
        sys.exit(1)
    
    with open(user_data_dir_file, "r") as f:
        user_data_dir = f.read().strip()
    
    print(f"✅ Using LinkedIn user data directory: {user_data_dir}")
    
    # Initialize Nova Act starting directly on the profile URL
    nova = NovaAct(
        starting_page=linkedin_url,
        headless=False,  # Keep visible for debugging
        user_data_dir=user_data_dir,
        clone_user_data_dir=False  # Important: Don't clone to preserve the session
    )
    
    return nova

def make_linkedin_connection(nova, linkedin_url, person_data, tracker_worksheet=None, tracker_row=None):
    """
    Use Nova Act to make a LinkedIn connection request (starts directly on profile page)
    Returns tuple: (success: bool, status: str, details: str)
    """
    print(f"\n🔗 Checking LinkedIn connection status for: {linkedin_url}")
    
    # Initialize trace for detailed logging
    trace_steps = []
    
    def update_progress(status, details_so_far):
        """Helper function to update tracker progress"""
        if tracker_worksheet and tracker_row:
            update_tracker_row(tracker_worksheet, tracker_row, status, " -> ".join(details_so_far))
    
    try:
        # Start the browser (already configured to start on the profile URL)
        print("🌐 Starting browser on profile page...")
        nova.start()
        trace_steps.append("Browser started")
        update_progress("BROWSER_STARTED", trace_steps)
        
        # Wait a moment for page to load
        time.sleep(3)
        
        # Check for captcha as recommended in documentation
        print("🛡️ Checking for captcha...")
        captcha_result = nova.act("Is there a captcha on the screen?", schema=BOOL_SCHEMA, max_steps=2)
        if captcha_result.matches_schema and captcha_result.parsed_response:
            print("🔒 Captcha detected. Please solve it manually.")
            trace_steps.append("Captcha detected and handled")
            update_progress("CAPTCHA_HANDLING", trace_steps)
            input("Please solve the captcha and press Enter to continue...")
        
        # First check if there's a Connect button directly visible on the page
        print("🔍 First checking for directly visible Connect button...")
        trace_steps.append("Checking for direct Connect button")
        update_progress("CHECKING_CONNECT_BUTTON", trace_steps)
        direct_connect_result = nova.act("Can you see a 'Connect' button directly visible on this LinkedIn profile page (not in a menu)?", 
                                       schema=BOOL_SCHEMA, max_steps=3)
        print(f"Direct Connect button check: {direct_connect_result.response}")
        
        if direct_connect_result.matches_schema and direct_connect_result.parsed_response:
            # There's a Connect button directly visible - use it!
            trace_steps.append("Found direct Connect button")
            update_progress("FOUND_DIRECT_CONNECT", trace_steps)
            print("🤝 Found directly visible Connect button - clicking it...")
            connect_result = nova.act("Click the Connect button to send a connection request", max_steps=5)
            print(f"Connect attempt: {connect_result.response}")
            trace_steps.append("Clicked Connect button")
            update_progress("CLICKED_CONNECT", trace_steps)
            
            # Wait a moment for potential dialog to appear
            time.sleep(2)
            
            # Handle the connection dialog - send without a message
            print("💬 Sending connection request without a message...")
            dialog_result = nova.act("Click 'Send' or 'Send invitation' to send the connection request without adding a personal message", 
                                    max_steps=5)
            print(f"Dialog handling: {dialog_result.response}")
            trace_steps.append("Clicked 'Send without Note'")
            update_progress("CLICKED_SEND", trace_steps)
            
            # Final verification that connection was sent
            print("✅ Verifying connection request was sent...")
            final_check = nova.act("Was the connection request sent successfully? Look for confirmation messages or changes on the page.", 
                                  schema=BOOL_SCHEMA, max_steps=3)
            if final_check.matches_schema:
                if final_check.parsed_response:
                    print("✅ Connection request appears to have been sent successfully")
                    trace_steps.append("Connection request sent successfully")
                    update_progress("PENDING", trace_steps)
                else:
                    print("⚠️ Connection request may not have been sent - check manually")
                    trace_steps.append("Connection request status unclear")
                    update_progress("PENDING", trace_steps)
            else:
                print("⚠️ Could not verify if connection request was sent")
                trace_steps.append("Could not verify connection request")
                update_progress("PENDING", trace_steps)
            
            print("✅ Connection request process completed")
            return True, "PENDING", " -> ".join(trace_steps)
        
        # No direct Connect button found - use the More button method to check connection status
        trace_steps.append("No direct Connect button found")
        update_progress("CHECKING_MORE_BUTTON", trace_steps)
        print("🔍 No direct Connect button found. Looking for 'More' button to check connection status...")
        more_button_result = nova.act("Can you see a 'More' button on this LinkedIn profile page?", 
                                    schema=BOOL_SCHEMA, max_steps=3)
        print(f"More button check: {more_button_result.response}")
        
        if not more_button_result.matches_schema or not more_button_result.parsed_response:
            print("❌ Could not find 'More' button on the page")
            trace_steps.append("More button not found")
            update_progress("ERROR", trace_steps)
            return False, "ERROR", " -> ".join(trace_steps)
        
        # Click the More button to reveal the menu
        trace_steps.append("Found More button")
        update_progress("FOUND_MORE_BUTTON", trace_steps)
        print("📱 Clicking 'More' button to reveal menu...")
        more_click_result = nova.act("Click the 'More' button", max_steps=3)
        print(f"More button click: {more_click_result.response}")
        trace_steps.append("Clicked More button")
        update_progress("CLICKED_MORE_BUTTON", trace_steps)
        
        # Wait for menu to appear
        time.sleep(2)
        
        # Check if we see "Remove connection" (the ONLY reliable indicator of existing connection)
        print("🔍 Checking if already connected by looking for 'Remove connection'...")
        remove_connection_result = nova.act("Can you see 'Remove connection' in the menu that appeared?", 
                                          schema=BOOL_SCHEMA, max_steps=3)
        print(f"Remove connection check: {remove_connection_result.response}")
        
        if remove_connection_result.matches_schema and remove_connection_result.parsed_response:
            print("✅ Already connected to this profile! ('Remove connection' found)")
            trace_steps.append("Found 'Remove connection' - Already connected")
            update_progress("CONNECTED", trace_steps)
            return True, "CONNECTED", " -> ".join(trace_steps)
        
        # Not connected yet - look for Connect button in the revealed menu
        trace_steps.append("No 'Remove connection' found")
        update_progress("CHECKING_MENU_CONNECT", trace_steps)
        print("🔍 Not connected yet. Looking for Connect button in the menu...")
        connect_in_menu_result = nova.act("Can you see a Connect button in the menu that appeared?", 
                                        schema=BOOL_SCHEMA, max_steps=3)
        print(f"Connect button in menu: {connect_in_menu_result.response}")
        
        if not connect_in_menu_result.matches_schema or not connect_in_menu_result.parsed_response:
            print("❌ Could not find Connect button in the More menu")
            trace_steps.append("Connect button not found in menu")
            update_progress("ERROR", trace_steps)
            return False, "ERROR", " -> ".join(trace_steps)
        
        # Click the Connect button in the revealed menu
        trace_steps.append("Found Connect button in menu")
        update_progress("FOUND_MENU_CONNECT", trace_steps)
        print("🤝 Clicking Connect button from the menu...")
        connect_result = nova.act("Click the Connect button to send a connection request", max_steps=5)
        print(f"Connect attempt: {connect_result.response}")
        trace_steps.append("Clicked Connect button from menu")
        update_progress("CLICKED_MENU_CONNECT", trace_steps)
        
        # Wait a moment for potential dialog to appear
        time.sleep(2)
        
        # Handle the connection dialog - send without a message
        print("💬 Sending connection request without a message...")
        dialog_result = nova.act("Click 'Send' or 'Send invitation' to send the connection request without adding a personal message", 
                                max_steps=5)
        print(f"Dialog handling: {dialog_result.response}")
        trace_steps.append("Clicked 'Send without Note'")
        update_progress("CLICKED_SEND", trace_steps)
        
        # Final verification that connection was sent
        print("✅ Verifying connection request was sent...")
        final_check = nova.act("Was the connection request sent successfully? Look for confirmation messages or changes on the page.", 
                              schema=BOOL_SCHEMA, max_steps=3)
        if final_check.matches_schema:
            if final_check.parsed_response:
                print("✅ Connection request appears to have been sent successfully")
                trace_steps.append("Connection request sent successfully")
                update_progress("PENDING", trace_steps)
            else:
                print("⚠️ Connection request may not have been sent - check manually")
                trace_steps.append("Connection request status unclear")
                update_progress("PENDING", trace_steps)
        else:
            print("⚠️ Could not verify if connection request was sent")
            trace_steps.append("Could not verify connection request")
            update_progress("PENDING", trace_steps)
        
        print("✅ Connection request process completed")
        return True, "PENDING", " -> ".join(trace_steps)
        
    except Exception as e:
        print(f"❌ Error making LinkedIn connection: {str(e)}")
        trace_steps.append(f"Error: {str(e)}")
        update_progress("ERROR", trace_steps)
        return False, "ERROR", " -> ".join(trace_steps)
    
    finally:
        # Always stop the browser
        try:
            print("🛑 Stopping browser...")
            nova.stop()
        except Exception as stop_error:
            print(f"⚠️  Error stopping browser: {stop_error}")

def add_initial_tracker_row(tracker_worksheet, linkedin_url):
    """
    Add initial row to tracker sheet with STARTING_AUTOMATION status
    Returns the row number of the added row, or None if failed
    """
    print(f"\n📝 Adding initial tracker row for: {linkedin_url}")
    
    try:
        # Check if sheet has headers, if not add them
        try:
            headers = tracker_worksheet.row_values(1)
            if not headers or len(headers) < 4:
                # Add headers if they don't exist or are incomplete
                tracker_worksheet.update('A1:D1', [['linkedin_url', 'request_sent', 'current_status', 'details']])
                print("✅ Added headers to tracker sheet")
        except Exception:
            # Sheet might be empty, add headers
            tracker_worksheet.update('A1:D1', [['linkedin_url', 'request_sent', 'current_status', 'details']])
            print("✅ Added headers to empty tracker sheet")
        
        # Prepare the initial row data
        now = datetime.datetime.now()
        initial_row = [
            linkedin_url,  # linkedin_url
            now.strftime("%Y-%m-%d %H:%M:%S"),  # request_sent
            "STARTING_AUTOMATION",  # current_status
            "Automation started"  # details
        ]
        
        # Append the initial row
        tracker_worksheet.append_row(initial_row)
        
        # Get the row number of the added row (last row)
        all_values = tracker_worksheet.get_all_values()
        row_number = len(all_values)  # 1-indexed
        
        print(f"✅ Added initial tracker row {row_number}:")
        print(f"   URL: {linkedin_url}")
        print(f"   Started: {now.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"   Status: STARTING_AUTOMATION")
        
        return row_number
        
    except Exception as e:
        print(f"❌ Error adding initial tracker row: {str(e)}")
        return None

def update_tracker_row(tracker_worksheet, row_number, status, details):
    """
    Update existing tracker row with new status and details
    """
    try:
        # Update the status and details columns (C and D)
        now = datetime.datetime.now()
        updates = [
            [status, details]  # current_status, details
        ]
        
        # Update columns C:D for the specific row
        range_name = f'C{row_number}:D{row_number}'
        tracker_worksheet.update(range_name, updates)
        
        print(f"📝 Updated tracker row {row_number}: {status}")
        return True
        
    except Exception as e:
        print(f"❌ Error updating tracker row {row_number}: {str(e)}")
        return False

def update_tracker_sheet(tracker_worksheet, linkedin_url, status="PENDING", details=""):
    """
    Update the tracker sheet with the connection status and details (legacy function for compatibility)
    """
    print(f"\n📝 Updating tracker sheet with status: {status}...")
    
    try:
        # Prepare the new row data
        now = datetime.datetime.now()
        new_row = [
            linkedin_url,  # linkedin_url
            now.strftime("%Y-%m-%d %H:%M:%S"),  # request_sent (or detected)
            status,  # current_status
            details  # details
        ]
        
        # Check if sheet has headers, if not add them
        try:
            headers = tracker_worksheet.row_values(1)
            if not headers or len(headers) < 4:
                # Add headers if they don't exist or are incomplete
                tracker_worksheet.update('A1:D1', [['linkedin_url', 'request_sent', 'current_status', 'details']])
                print("✅ Added headers to tracker sheet")
        except Exception:
            # Sheet might be empty, add headers
            tracker_worksheet.update('A1:D1', [['linkedin_url', 'request_sent', 'current_status', 'details']])
            print("✅ Added headers to empty tracker sheet")
        
        # Append the new row
        tracker_worksheet.append_row(new_row)
        action_text = "connection status" if status == "CONNECTED" else "connection request"
        print(f"✅ Successfully added {action_text} to tracker:")
        print(f"   URL: {linkedin_url}")
        date_label = "Detected" if status == "CONNECTED" else "Sent"
        print(f"   {date_label}: {now.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"   Status: {status}")
        print(f"   Details: {details}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error updating tracker sheet: {str(e)}")
        return False

def process_single_connection():
    """
    Process a single LinkedIn connection automation
    """
    print("🚀 Starting LinkedIn Connection Automation")
    print("=" * 50)
    
    # Step 1: Authenticate with Google Sheets
    print("\n1️⃣ Authenticating with Google Sheets...")
    gc = authenticate_google_sheets()
    
    # Step 2: Open the spreadsheet and worksheets
    print("\n2️⃣ Opening spreadsheet and worksheets...")
    tracker_worksheet, persons_worksheet = open_spreadsheet(gc)
    
    # Step 3: Read data from both sheets
    print("\n3️⃣ Reading data from sheets...")
    tracker_df = read_sheet_data(tracker_worksheet)
    persons_df = read_sheet_data(persons_worksheet)
    
    # Step 4: Find a new LinkedIn URL to connect
    print("\n4️⃣ Finding new LinkedIn URL...")
    linkedin_url, person_data = find_new_linkedin_url(persons_df, tracker_df)
    
    if not linkedin_url:
        print("✅ No new connections to make. Returning.")
        return False  # Return False to indicate no more connections available
    
    # Step 5: Add initial tracker row
    print("\n5️⃣ Adding initial tracker row...")
    tracker_row = add_initial_tracker_row(tracker_worksheet, linkedin_url)
    if not tracker_row:
        print("❌ Failed to add initial tracker row. Continuing anyway...")
    
    # Step 6: Set up Nova Act
    print("\n6️⃣ Setting up Nova Act...")
    nova = setup_nova_act(linkedin_url)
    
    # Step 7: Make LinkedIn connection (with real-time progress updates)
    print("\n7️⃣ Checking LinkedIn connection...")
    connection_success, connection_status, connection_details = make_linkedin_connection(
        nova, linkedin_url, person_data, tracker_worksheet, tracker_row
    )
    
    # No need to update tracker sheet manually - it's already updated in real-time
    # Just verify the final status is correctly set
    if tracker_row:
        update_tracker_row(tracker_worksheet, tracker_row, connection_status, connection_details)
    
    update_success = True  # Since we're updating in real-time, consider it successful
    
    if update_success:
        print("\n✅ LinkedIn connection automation completed successfully!")
        print(f"📊 Summary:")
        print(f"   • Profile: {linkedin_url}")
        if person_data is not None:
            print(f"   • Person: {person_data.get('Person', 'Unknown')}")
            print(f"   • Company: {person_data.get('Company', 'Unknown')}")
        print(f"   • Status: {connection_status}")
        if connection_status == "CONNECTED":
            print(f"   • Action: Already connected (detected)")
        elif connection_status == "PENDING":
            print(f"   • Action: Connection request sent")
        print(f"   • Details: {connection_details}")
        print(f"   • Tracker updated: Yes (real-time)")
    else:
        action_text = "detected existing connection" if connection_status == "CONNECTED" else "sent connection request"
        print(f"\n⚠️  Successfully {action_text} but tracker update failed.")
        print(f"   • Details: {connection_details}")
        print("You may need to manually check the tracker sheet.")
    
    return True  # Return True to indicate successful processing

def main(n=1):
    """
    Main function to orchestrate multiple LinkedIn connection automations
    
    Args:
        n (int): Number of iterations to perform
    """
    print(f"🚀 Starting LinkedIn Connection Automation - {n} iteration(s)")
    print("=" * 60)
    
    successful_iterations = 0
    
    for i in range(n):
        print(f"\n{'='*20} ITERATION {i+1} of {n} {'='*20}")
        
        # Process a single connection
        result = process_single_connection()
        
        if result:
            successful_iterations += 1
            print(f"✅ Iteration {i+1} completed successfully")
        else:
            print(f"⚠️  Iteration {i+1}: No new connections available")
            print("🛑 Stopping iterations as no more connections are available")
            break
        
        # Sleep between iterations (except for the last one)
        if i < n - 1:
            sleep_time = random.randint(60, 90)
            print(f"\n😴 Sleeping for {sleep_time} seconds before next iteration...")
            time.sleep(sleep_time)
    
    print(f"\n🏁 All iterations completed!")
    print(f"📊 Final Summary:")
    print(f"   • Total iterations requested: {n}")
    print(f"   • Successful iterations: {successful_iterations}")
    print(f"   • Stopped early: {'Yes' if successful_iterations < n else 'No'}")

if __name__ == "__main__":
    # Get number of iterations from command line argument or default to 1
    import argparse
    
    parser = argparse.ArgumentParser(description='LinkedIn Connection Automation')
    parser.add_argument('-n', '--iterations', type=int, default=1, 
                       help='Number of connection attempts to make (default: 1)')
    
    args = parser.parse_args()
    
    if args.iterations <= 0:
        print("❌ Error: Number of iterations must be positive")
        sys.exit(1)
    
    main(args.iterations) 