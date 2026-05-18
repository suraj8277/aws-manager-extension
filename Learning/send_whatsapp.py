#import pywhatkit as kit
# Send a WhatsApp message
#kit.sendwhatmsg("+918210237547", "Hello! This is an automated message from Python 😎", 9, 4)
#kit.sendwhatmsg_instantly("+918210237547", "Instant message",wait_time=10, tab_close=True)

###########################################

import pywhatkit as kit
import re
import datetime

def send_scheduled_whatsapp():
    """
    Asks the user for input and schedules a WhatsApp message using pywhatkit.
    """
    print("--- WhatsApp Message Scheduler ---")
    
    # --- Get Phone Number ---
    while True:
        phone_number = input("Enter the recipient's phone number (e.g., +919876543210): ").strip()
        # Basic validation for international format
        if re.match(r'^\+\d{1,3}\d{6,14}$', phone_number):
            break
        else:
            print("Invalid format. Please include the country code (e.g., +91) and the number.")
            
    # --- Get Message ---
    message = input("Enter the message to send: ").strip()
    
    # --- Get Time ---
    while True:
        try:
            # Get the scheduled hour (in 24-hour format)
            hour_str = input("Enter the HOUR to send (0-23): ").strip()
            hour = int(hour_str)
            if not 0 <= hour <= 23:
                raise ValueError
            
            # Get the scheduled minute
            minute_str = input("Enter the MINUTE to send (0-59): ").strip()
            minute = int(minute_str)
            if not 0 <= minute <= 59:
                raise ValueError
            
            # Use the input hour and minute without leading zeros
            break
        except ValueError:
            print("Invalid input. Hour must be between 0 and 23, and Minute between 0 and 59.")
            
    # --- Confirmation and Scheduling ---
    
    try:
        # Check if the scheduled time is in the past
        now = datetime.datetime.now()
        schedule_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        
        if schedule_time < now:
            # Schedule for the next day
            print(f"\nTime {hour:02d}:{minute:02d} is in the past. Scheduling for the next day.")
        
        # Schedule the message
        kit.sendwhatmsg(phone_number, message, hour, minute)
        
        print("\n✅ Message successfully scheduled!")
        print(f"It will be sent to {phone_number} at {hour:02d}:{minute:02d}.")
        print("Make sure WhatsApp Web is logged in on your Chrome browser[cite: 211, 212].")

    except Exception as e:
        print(f"\n❌ An error occurred during scheduling: {e}")

if __name__ == "__main__":
    send_scheduled_whatsapp()
