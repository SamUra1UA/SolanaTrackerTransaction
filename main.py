import requests
import telebot
import html
import time
from telebot.apihelper import ApiTelegramException

# Step 1: Configuration
TELEGRAM_BOT_TOKEN = ''
TELEGRAM_CHAT_ID = ''
SOLANA_API_URL = 'https://api.devnet.solana.com'
GECKOTERMINAL_URL = 'https://www.geckoterminal.com/solana/pools/'
COINGECKO_API_URL = 'https://api.coingecko.com/api/v3/simple/price'

# Initialize the bot
bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)

# Step 2: Fetch Recent Transactions from Solana
def get_latest_slot():
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "getSlot",
        "params": []
    }
    response = requests.post(SOLANA_API_URL, json=payload).json()
    return response['result']

def get_block_transactions(slot):
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "getBlock",
        "params": [
            slot,
            {
                "encoding": "json",
                "maxSupportedTransactionVersion": 0,
                "transactionDetails": "full",
                "rewards": False
            }
        ]
    }
    response = requests.post(SOLANA_API_URL, json=payload).json()
    if 'result' in response:
        return response['result']['transactions']
    else:
        print("Error in response:", response)
        return []

# Fetch the current SOL price from CoinGecko
def get_sol_price():
    params = {
        'ids': 'solana',
        'vs_currencies': 'usd'
    }
    response = requests.get(COINGECKO_API_URL, params=params).json()
    return response['solana']['usd']

# Step 3: Format the Message
def format_message(signature, wallet, sol_amount, is_new, sol_price):
    """Formats a message for sending to Telegram."""
    usd_spent = sol_amount * sol_price
    new_holder_text = "New Holder!" if is_new else "Existing Holder"
    geckoterminal_url = f"{GECKOTERMINAL_URL}{html.escape(wallet)}"
    solscan_tx_url = f"https://solscan.io/tx/{signature}"
    solana_wallet_url = f"https://solscan.io/account/{wallet}"

    short_signature = f"{signature[:10]}...{signature[-10:]}"

    return (
        f"🚨 USER <a href='{geckoterminal_url}'>New Buy</a> 🚨\n\n"
        f"💰Spent: ${usd_spent:.6f} ({sol_amount:.6f} SOL)\n"
        f"💼 Wallet: <a href='{solana_wallet_url}'>{wallet}</a>\n"
        f"💵 Price: ${sol_price:.4f}\n"
        f"👥 {new_holder_text}\n\n"
        f"TX <a href='{solscan_tx_url}'>{short_signature}</a> | "
        f"CHART <a href='{geckoterminal_url}'>Link</a>"
    )

# Step 4: Send Messages via Telegram Bot API
def send_telegram_message(message):
    while True:
        try:
            bot.send_message(TELEGRAM_CHAT_ID, message, parse_mode='HTML', disable_web_page_preview=True)
            break  # Exit the loop if the message was sent successfully
        except ApiTelegramException as e:
            if e.error_code == 429:
                retry_after = int(e.result_json['parameters']['retry_after'])
                print(f"Rate limit exceeded. Retrying after {retry_after} seconds.")
                time.sleep(retry_after)
            else:
                raise  # Re-raise the exception if it's not rate limiting

# Extract transaction details from the provided JSON structure
def parse_transaction(tx):
    signature = tx['transaction']['signatures'][0]
    wallet = tx['transaction']['message']['accountKeys'][0]

    # Find the account involved in the transaction and calculate the SOL amount spent
    pre_balance = tx['meta']['preBalances'][0]
    post_balance = tx['meta']['postBalances'][0]
    sol_amount = (pre_balance - post_balance) / 1e9  # Convert lamports to SOL

    is_new = True  # Placeholder for logic to check if the wallet is new
    return signature, wallet, sol_amount, is_new

# Main loop to periodically fetch new transactions and send messages
def main():
    latest_processed_slot = get_latest_slot()  # Initialize the latest processed slot
    processed_signatures = set()  # Set to track processed transactions

    while True:
        current_slot = get_latest_slot()

        if current_slot > latest_processed_slot:
            for slot in range(latest_processed_slot + 1, current_slot + 1):
                transactions = get_block_transactions(slot)
                sol_price = get_sol_price()

                for tx in transactions:
                    signature, wallet, sol_amount, is_new = parse_transaction(tx)

                    # Only process new transactions
                    if signature not in processed_signatures:
                        processed_signatures.add(signature)
                        message = format_message(signature, wallet, sol_amount, is_new, sol_price)
                        send_telegram_message(message)
                        print("Message sent")
                        time.sleep(7)  # Add delay to avoid hitting Telegram rate limits

            latest_processed_slot = current_slot  # Update the latest processed slot

        time.sleep(10)  # Add delay to check for new slots periodically

if __name__ == "__main__":
    main()
