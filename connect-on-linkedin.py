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

def make_linkedin_connection(nova, linkedin_url, person_data):
    """
    Use Nova Act to make a LinkedIn connection request (starts directly on profile page)
    """
    print(f"\n🔗 Making LinkedIn connection to: {linkedin_url}")
    
    try:
        # Start the browser (already configured to start on the profile URL)
        print("🌐 Starting browser on profile page...")
        nova.start()
        
        # Wait a moment for page to load
        time.sleep(3)
        
        # Check for captcha as recommended in documentation
        print("🛡️ Checking for captcha...")
        captcha_result = nova.act("Is there a captcha on the screen?", schema=BOOL_SCHEMA, max_steps=2)
        if captcha_result.matches_schema and captcha_result.parsed_response:
            print("🔒 Captcha detected. Please solve it manually.")
            input("Please solve the captcha and press Enter to continue...")
        
        # Check if we're on the correct profile page and can see a Connect button
        print("🔍 Verifying we're on the correct profile page...")
        verification_result = nova.act("Can you see a Connect button on this LinkedIn profile page?", 
                                     schema=BOOL_SCHEMA, max_steps=3)
        print(f"Verification: {verification_result.response}")
        
        # If no Connect button visible, try clicking "More" to reveal it
        if not verification_result.matches_schema or not verification_result.parsed_response:
            print("🔍 Connect button not visible, looking for 'More' button...")
            more_button_result = nova.act("Can you see a 'More' button on this LinkedIn profile page?", 
                                        schema=BOOL_SCHEMA, max_steps=3)
            print(f"More button check: {more_button_result.response}")
            
            if more_button_result.matches_schema and more_button_result.parsed_response:
                print("📱 Clicking 'More' button to reveal menu...")
                more_click_result = nova.act("Click the 'More' button", max_steps=3)
                print(f"More button click: {more_click_result.response}")
                
                # Wait for menu to appear
                time.sleep(2)
                
                # Check again for Connect button in the revealed menu
                print("🔍 Looking for Connect button in the revealed menu...")
                connect_in_menu_result = nova.act("Can you see a Connect button in the menu that appeared?", 
                                                schema=BOOL_SCHEMA, max_steps=3)
                print(f"Connect button in menu: {connect_in_menu_result.response}")
                
                if not connect_in_menu_result.matches_schema or not connect_in_menu_result.parsed_response:
                    print("❌ Could not find Connect button even after clicking More")
                    return False
            else:
                print("❌ Could not find Connect button or More button on the page")
                return False
        
        # Click the Connect button (either directly visible or in the revealed menu)
        print("🤝 Clicking Connect button...")
        connect_result = nova.act("Click the Connect button to send a connection request", max_steps=5)
        print(f"Connect attempt: {connect_result.response}")
        
        # Wait a moment for potential dialog to appear
        time.sleep(2)
        
        # Handle the connection dialog - send without a message
        print("💬 Sending connection request without a message...")
        dialog_result = nova.act("Click 'Send' or 'Send invitation' to send the connection request without adding a personal message", 
                                max_steps=5)
        print(f"Dialog handling: {dialog_result.response}")
        
        # Final verification that connection was sent
        print("✅ Verifying connection request was sent...")
        final_check = nova.act("Was the connection request sent successfully? Look for confirmation messages or changes on the page.", 
                              schema=BOOL_SCHEMA, max_steps=3)
        if final_check.matches_schema:
            if final_check.parsed_response:
                print("✅ Connection request appears to have been sent successfully")
            else:
                print("⚠️ Connection request may not have been sent - check manually")
        else:
            print("⚠️ Could not verify if connection request was sent")
        
        print("✅ Connection request process completed")
        return True
        
    except Exception as e:
        print(f"❌ Error making LinkedIn connection: {str(e)}")
        return False
    
    finally:
        # Always stop the browser
        try:
            print("🛑 Stopping browser...")
            nova.stop()
        except Exception as stop_error:
            print(f"⚠️  Error stopping browser: {stop_error}")

def update_tracker_sheet(tracker_worksheet, linkedin_url):
    """
    Update the tracker sheet with the new connection request
    """
    print(f"\n📝 Updating tracker sheet with new connection...")
    
    try:
        # Prepare the new row data
        now = datetime.datetime.now()
        new_row = [
            linkedin_url,  # linkedin_url
            now.strftime("%Y-%m-%d %H:%M:%S"),  # request_sent
            "PENDING"  # current_status
        ]
        
        # Check if sheet has headers, if not add them
        try:
            headers = tracker_worksheet.row_values(1)
            if not headers or len(headers) < 3:
                # Add headers if they don't exist
                tracker_worksheet.update('A1:C1', [['linkedin_url', 'request_sent', 'current_status']])
                print("✅ Added headers to tracker sheet")
        except Exception:
            # Sheet might be empty, add headers
            tracker_worksheet.update('A1:C1', [['linkedin_url', 'request_sent', 'current_status']])
            print("✅ Added headers to empty tracker sheet")
        
        # Append the new row
        tracker_worksheet.append_row(new_row)
        print(f"✅ Successfully added connection request to tracker:")
        print(f"   URL: {linkedin_url}")
        print(f"   Sent: {now.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"   Status: PENDING")
        
        return True
        
    except Exception as e:
        print(f"❌ Error updating tracker sheet: {str(e)}")
        return False

def main():
    """
    Main function to orchestrate the LinkedIn connection automation
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
        print("✅ No new connections to make. Exiting.")
        return
    
    # Step 5: Set up Nova Act
    print("\n5️⃣ Setting up Nova Act...")
    nova = setup_nova_act(linkedin_url)
    
    # Step 6: Make LinkedIn connection
    print("\n6️⃣ Making LinkedIn connection...")
    connection_success = make_linkedin_connection(nova, linkedin_url, person_data)
    
    if not connection_success:
        print("❌ Failed to make LinkedIn connection. Exiting without updating tracker.")
        return
    
    # Step 7: Update tracker sheet
    print("\n7️⃣ Updating tracker sheet...")
    update_success = update_tracker_sheet(tracker_worksheet, linkedin_url)
    
    if update_success:
        print("\n✅ LinkedIn connection automation completed successfully!")
        print(f"📊 Summary:")
        print(f"   • Connected to: {linkedin_url}")
        if person_data is not None:
            print(f"   • Person: {person_data.get('Person', 'Unknown')}")
            print(f"   • Company: {person_data.get('Company', 'Unknown')}")
        print(f"   • Tracker updated: Yes")
    else:
        print("\n⚠️  Connection was made but tracker update failed.")
        print("You may need to manually add this connection to the tracker sheet.")

if __name__ == "__main__":
    main() 