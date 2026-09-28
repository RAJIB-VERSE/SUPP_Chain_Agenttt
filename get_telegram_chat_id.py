import urllib.request
import json
import time

print("="*60)
print("TELEGRAM BOT SETUP UTILITY")
print("="*60)
print("1. Open Telegram on your phone or computer.")
print("2. Search for '@BotFather' and send him the message: /newbot")
print("3. Follow the steps to name your bot and get the HTTP API TOKEN.")
print("4. Paste your token below:")

token = input("Enter your token: ")

if not token:
    print("Invalid token. Exiting.")
    exit(1)

print("\nAwesome! Now do this:")
print("5. Search for your newly created bot in Telegram and click 'Start' (or send it a message like 'hello').")
print("6. If you just sent the message, wait a few seconds and run this script again.")

import ssl

url = f"https://api.telegram.org/bot{token}/getUpdates"
try:
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, context=ctx) as response:
        data = json.loads(response.read().decode())
        
    results = data.get("result", [])
    if not results:
        print("\n❌ No messages found. Please make sure you sent a message to your bot and try running this script again.")
    else:
        # Get the chat ID from the latest message
        chat_id = results[-1]["message"]["chat"]["id"]
        print("\n✅ SUCCESS!")
        print(f"Your TELEGRAM_BOT_TOKEN: {token}")
        print(f"Your TELEGRAM_CHAT_ID: {chat_id}")
        
        print("\n--- NEXT STEP ---")
        print("Open D:\\AWS\\backend\\lambda_function.py and paste these values around line 443 where it says:")
        print('TELEGRAM_BOT_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN_HERE"')
        print('TELEGRAM_CHAT_ID = "YOUR_TELEGRAM_CHAT_ID_HERE"')

except Exception as e:
    print(f"\n❌ Error connecting to Telegram API: {e}")
    print("Check your token and internet connection.")
