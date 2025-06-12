#!/usr/bin/env python3

import os
import tempfile
from pathlib import Path
from nova_act import NovaAct

# Create a persistent directory for the Chrome user data
user_data_dir = os.path.join(os.path.expanduser("~"), ".linkedin-browser-data")
os.makedirs(user_data_dir, exist_ok=True)

# Store the user_data_dir path in a config file for the main script to use
config_dir = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(config_dir, ".linkedin_user_data_dir"), "w") as f:
    f.write(user_data_dir)

print(f"Setting up persistent login session in: {user_data_dir}")

# Load API key from environment variable
api_key = os.environ.get("NOVA_ACT_API_KEY")
if not api_key:
    print("Error: NOVA_ACT_API_KEY environment variable is not set.")
    print("Please set it by running: export NOVA_ACT_API_KEY='your-api-key-here'")
    exit(1)

# Initialize Nova Act with LinkedIn as the starting page
# Using clone_user_data_dir=False to preserve the session
nova = NovaAct(
    starting_page="https://www.linkedin.com/",
    headless=False,
    user_data_dir=user_data_dir,
    clone_user_data_dir=False  # Important: Don't clone to preserve the session
)

try:
    # Start the browser
    print("Starting browser...")
    nova.start()
    
    # Navigate to sign in page
    print("Navigating to sign in page...")
    result = nova.act("Click on the Sign In button")
    
    print("\n" + "="*50)
    print("PLEASE SIGN IN MANUALLY TO YOUR LINKEDIN ACCOUNT")
    print("The browser window should now show the login page.")
    print("Complete the authentication process manually.")
    print("This may include entering your email/password and")
    print("completing any 2FA verification if required.")
    print("="*50 + "\n")
    
    input("Press Enter once you have successfully signed in...")
    
    # Verify we're logged in
    result = nova.act("Am I logged in to LinkedIn?")
    print(f"Authentication status: {result.response}")
    
    print("\nLinkedIn login session has been saved for future use.")
    print(f"User data directory: {user_data_dir}")
    
finally:
    # Always ensure we stop the browser properly
    print("Stopping browser...")
    nova.stop() 