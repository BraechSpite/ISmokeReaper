from telethon import TelegramClient, events, Button
from quotexapi.stable_api import Quotex
from datetime import datetime, timedelta
import csv
import asyncio
import os

# Bot credentials
API_ID = '23844616'
API_HASH = '4aeca3680a20f9b8bc669f9897d5402f'
BOT_TOKEN = '7806851377:AAGV50o83eCWsjpsMtG10trMHyQ7ZuApng0'
OWNER_USERNAME = '@Advik_Ahooja'

# Quotex credentials
QUOTEX_EMAIL = "mashupcartoon@gmail.com"
QUOTEX_PASSWORD = "Cash@8055"

# Initialize bot and Quotex client
bot = TelegramClient('signal_bot', API_ID, API_HASH).start(bot_token=BOT_TOKEN)
quotex_client = Quotex(email=QUOTEX_EMAIL, password=QUOTEX_PASSWORD, lang="en")

# Store user IDs and signal messages
user_ids = set()
signal_messages = {}

async def connect_to_quotex():
    """Connect to Quotex API"""
    check, message = await quotex_client.connect()
    if check:
        print("Connected to Quotex")
    else:
        print("Failed to connect:", message)
    return check

def process_candle_data(history):
    """Process candle data from Quotex API"""
    candles = []
    current_minute = None
    candle_open = None
    candle_close = None

    for data in reversed(history):
        timestamp = datetime.fromtimestamp(data[0])
        price = data[1]
        
        if current_minute is None:
            current_minute = timestamp.replace(second=0, microsecond=0)
            candle_open = price
            candle_close = price
        elif timestamp.replace(second=0, microsecond=0) < current_minute:
            candles.append({
                'timestamp': current_minute,
                'open': candle_close,
                'close': candle_open,
                'color': '🟥 Red' if candle_close >= candle_open else '🟩 Green'
            })
            if len(candles) == 3:
                break
            current_minute = timestamp.replace(second=0, microsecond=0)
            candle_open = price
            candle_close = price
        else:
            candle_close = price

    return list(reversed(candles))

async def get_candle_data(asset, signal_time):
    """Get candle data from Quotex API"""
    try:
        check = await connect_to_quotex()
        if check:
            asset_name, asset_data = await quotex_client.get_available_asset(asset, force_open=True)
            if asset_data[2]:
                candle_v2 = await quotex_client.get_candle_v2(asset, 60)
                if candle_v2 and 'history' in candle_v2:
                    candles = process_candle_data(candle_v2['history'])
                    
                    # Log candle data
                    print(f"\n📊 Candle Data for {asset} (Signal Time: {signal_time}):")
                    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
                    for i, candle in enumerate(candles, 1):
                        print(f"Candle {i}:")
                        print(f"  Timestamp: {candle['timestamp']}")
                        print(f"  Open: {candle['open']}")
                        print(f"  Close: {candle['close']}")
                        print(f"  Color: {candle['color']}")
                        print("  ────────────────────────────────")
                    
                    return candles
            else:
                print(f"❌ Asset {asset_name} is closed.")
    except Exception as e:
        print(f"❌ Error getting candle data: {str(e)}")
    return None

def check_signal_result(candles, direction):
    """Check signal result based on candle data"""
    if not candles or len(candles) < 3:
        return None
    
    signal_candle = candles[0]['color']
    first_martingale = candles[1]['color']
    
    # Log result check
    print("\n🎯 Checking Result:")
    print(f"Signal Candle: {signal_candle}")
    print(f"First Martingale: {first_martingale}")
    print(f"Direction: {direction}")
    
    if direction == "UP":
        if signal_candle == "🟩 Green":
            result = "win"
        elif first_martingale == "🟩 Green":
            result = "mtg"
        else:
            result = "loss"
    elif direction == "DOWN":
        if signal_candle == "🟥 Red":
            result = "win"
        elif first_martingale == "🟥 Red":
            result = "mtg"
        else:
            result = "loss"
    
    print(f"Result: {result.upper()}")
    return result

@bot.on(events.NewMessage(pattern='/start'))
async def start(event):
    """Handle /start command"""
    user_id = event.chat_id
    user_ids.add(user_id)
    
    sender = await event.get_sender()
    if sender.username == OWNER_USERNAME.replace('@', ''):
        await event.respond(
            "**Welcome, Owner! 👑**\n\n"
            "**To send signals, please upload a CSV file with the following format:**\n"
            "Asset_otc,Time,Direction\n"
            "USDARS_otc,21:45:00,UP\n"
            "USDTRY_otc,21:56:00,DOWN\n\n"
            "**The signals will be automatically sent to all users 1 minute before the specified time.**\n"
            "**Results will be automatically checked exactly 2 minutes after each trade time.**"
        )
    else:
        await event.respond(
            "**Welcome to the Signal Bot! 📊**\n\n"
            "**You will receive signals automatically one minute before each trade.**\n"
            "**Results will be sent automatically after each trade.**\n"
            "**Stay tuned for profitable opportunities! 💹**"
        )

async def send_result(signal_id, result_type, owner_id):
    """Send result to all users"""
    signal_info = signal_messages.get(signal_id)
    if signal_info:
        # Determine result text
        if result_type == 'win':
            result_text = "WIN ✅"
        elif result_type == 'mtg':
            result_text = "MTG WIN ✅"
        elif result_type == 'loss':
            result_text = "LOSS ⚔️"
        else:
            return

        # Clean signal info and create result message
        clean_signal_info = signal_info.replace('**', '')
        result_message = (
            f"**🏁 RESULT OF TRADE = {result_text}**\n\n"
            f"**{clean_signal_info}**"
        )

        # Send result to all users
        for user_id in user_ids:
            try:
                await bot.send_message(user_id, result_message)
                await bot.send_message(user_id, "➖➖➖➖➖➖➖➖➖➖")
            except Exception as e:
                print(f"Error sending result to {user_id}: {str(e)}")

async def send_signal(asset, time_str, direction, scheduled_time, signal_id):
    """Send signal and handle result checking"""
    direction_emoji = "🟩" if direction.upper() == "UP" else "🟥"
    formatted_asset = asset.replace('_otc', '-OTC')
    
    message = (
        f"**📊 PAIR - {formatted_asset}\n"
        f"⏰ TIME - {time_str}\n"
        f"↕️ DIRECTION - {direction.upper()} {direction_emoji}\n"
        f"✅¹ 1 Step-Martingale\n"
        f"🧔🏻 OWNER - {OWNER_USERNAME}**"
    )
    
    signal_messages[signal_id] = message
    button = [Button.url("🧔🏻 CONTACT OWNER 🧔🏻", "https://t.me/+905010726177")]
    
    try:
        # Calculate times
        signal_time = datetime.strptime(time_str, '%H:%M').time()
        current_date = datetime.now().date()
        signal_datetime = datetime.combine(current_date, signal_time)
        check_time = signal_datetime + timedelta(minutes=2)
        
        # Wait until signal send time
        now = datetime.now()
        wait_seconds = (scheduled_time - now).total_seconds()
        
        if wait_seconds > 0:
            print(f"\n⏳ Waiting {wait_seconds:.2f} seconds to send signal for {asset}")
            await asyncio.sleep(wait_seconds)
            
            # Send signal to all users
            print(f"📣 Sending signal for {asset}")
            for user_id in user_ids:
                try:
                    await bot.send_message(user_id, message, buttons=button)
                except Exception as e:
                    print(f"Error sending signal to {user_id}: {str(e)}")
            
            # Wait until exact check time
            wait_for_check = (check_time - datetime.now()).total_seconds()
            print(f"\n⏳ Waiting {wait_for_check:.2f} seconds to check result for {asset}")
            await asyncio.sleep(wait_for_check)
            
            # Check results using Quotex API
            print(f"\n🔍 Checking result for {asset} at {check_time}")
            candles = await get_candle_data(asset, time_str)
            if candles:
                result_type = check_signal_result(candles, direction.upper())
                if result_type:
                    await send_result(signal_id, result_type, None)
                
    except Exception as e:
        print(f"❌ Error in send_signal: {str(e)}")

@bot.on(events.NewMessage(from_users=OWNER_USERNAME))
async def handle_csv(event):
    """Handle CSV file uploads from the owner"""
    if event.file and event.file.name.endswith('.csv'):
        file_path = await event.download_media()
        
        try:
            with open(file_path, 'r') as file:
                csv_reader = csv.reader(file)
                next(csv_reader)
                
                tasks = []
                for idx, row in enumerate(csv_reader):
                    if len(row) == 3:
                        asset, time_str, direction = row
                        signal_time = datetime.strptime(time_str, '%H:%M:%S').time()
                        current_date = datetime.now().date()
                        signal_datetime = datetime.combine(current_date, signal_time)
                        send_time = signal_datetime - timedelta(minutes=1)
                        signal_id = f"signal_{int(datetime.now().timestamp())}_{idx}"
                        
                        if send_time > datetime.now():
                            display_time = signal_time.strftime('%H:%M')
                            task = asyncio.create_task(
                                send_signal(asset, display_time, direction, send_time, signal_id)
                            )
                            tasks.append(task)
                
                if tasks:
                    await event.respond(
                        f"**✅ Successfully scheduled {len(tasks)} signals!**\n"
                        "**Signals will be sent automatically 1 minute before each trade time.**\n"
                        "**Results will be checked automatically exactly 2 minutes after each trade time.**"
                    )
                else:
                    await event.respond("**⚠️ No valid future signals found in the CSV file.**")
                
                for task in tasks:
                    asyncio.create_task(task)
                
        except Exception as e:
            await event.respond(f"**❌ Error processing CSV file: {str(e)}**")
        finally:
            if os.path.exists(file_path):
                os.remove(file_path)

def main():
    """Start the bot"""
    print("🤖 Bot started...")
    bot.run_until_disconnected()

if __name__ == '__main__':
    main()