from dotenv import load_dotenv
import os
import time
import logging
import pandas as pd
from binance.client import Client
from binance.exceptions import BinanceAPIException


class BinanceTestnetBot:
    def __init__(self, api_key: str, api_secret: str,
                 symbol: str = 'BTCUSDT'):
        """Initialize the trading bot with Binance testnet credentials"""
        self.client = Client(
            api_key,
            api_secret,
            testnet=True  # This enables testnet
        )
        self.symbol = symbol
        self.setup_logging()

    def setup_logging(self):
        """Set up logging configuration"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('trading_bot.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)

    def get_account_balance(self) -> dict:
        """Get current account balance"""
        try:
            account = self.client.get_account()
            balances = {}
            for balance in account['balances']:
                if float(balance['free']) > 0 or float(balance['locked']) > 0:
                    balances[balance['asset']] = {
                        'free': float(balance['free']),
                        'locked': float(balance['locked'])
                    }
            return balances
        except BinanceAPIException as e:
            self.logger.error(f"Error getting account balance: {e}")
            return {}

    def get_symbol_price(self) -> float:
        """Get current price of trading pair"""
        try:
            ticker = self.client.get_symbol_ticker(symbol=self.symbol)
            return float(ticker['price'])
        except BinanceAPIException as e:
            self.logger.error(f"Error getting symbol price: {e}")
            return None

    def calculate_indicators(self, interval: str = '1h', limit: int = 100) -> pd.DataFrame:
        """Calculate trading indicators"""
        try:
            # Get historical klines/candlestick data
            klines = self.client.get_historical_klines(
                self.symbol,
                interval,
                f"{limit} hours ago UTC"
            )

            # Create DataFrame
            df = pd.DataFrame(klines, columns=[
                'timestamp', 'open', 'high', 'low', 'close', 'volume',
                'close_time', 'quote_volume', 'trades', 'taker_buy_base',
                'taker_buy_quote', 'ignored'
            ])

            # Convert price columns to float
            df[['open', 'high', 'low', 'close', 'volume']] = df[['open', 'high', 'low', 'close', 'volume']].astype(
                float)

            # Calculate indicators
            # Short-term SMA (20 periods)
            df['SMA20'] = df['close'].rolling(window=20).mean()

            # Long-term SMA (50 periods)
            df['SMA50'] = df['close'].rolling(window=50).mean()

            return df

        except BinanceAPIException as e:
            self.logger.error(f"Error calculating indicators: {e}")
            return None

    def generate_signal(self, df: pd.DataFrame) -> int:
        """Generate trading signal based on SMA crossover
        Returns: 1 (buy), -1 (sell), or 0 (hold)
        """
        if df is None or len(df) < 50:
            return 0

        # Get last two rows to check for crossover
        prev_row = df.iloc[-2]
        curr_row = df.iloc[-1]

        # Check for SMA crossover
        if prev_row['SMA20'] < prev_row['SMA50'] and curr_row['SMA20'] > curr_row['SMA50']:
            return 1  # Golden Cross (buy signal)
        elif prev_row['SMA20'] > prev_row['SMA50'] and curr_row['SMA20'] < curr_row['SMA50']:
            return -1  # Death Cross (sell signal)

        return 0  # No signal

    def place_order(self, side: str, quantity: float) -> dict:
        """Place a market order"""
        try:
            order = self.client.create_order(
                symbol=self.symbol,
                side=side,
                type='MARKET',
                quantity=quantity
            )
            self.logger.info(f"Placed {side} order: {order}")
            return order
        except BinanceAPIException as e:
            self.logger.error(f"Error placing order: {e}")
            return None

    def calculate_position_size(self, usdt_amount: float) -> float:
        """Calculate position size based on current price and USDT amount"""
        price = self.get_symbol_price()
        if price:
            # Get symbol info for quantity precision
            symbol_info = self.client.get_symbol_info(self.symbol)
            step_size = 0.00001  # default

            for filter in symbol_info['filters']:
                if filter['filterType'] == 'LOT_SIZE':
                    step_size = float(filter['stepSize'])
                    break

            quantity = usdt_amount / price
            # Round down to the nearest step size
            quantity = float(int(quantity / step_size) * step_size)
            return quantity
        return 0

# Press the green button in the gutter to run the script.
    def run_bot(self, check_interval: int = 60, trade_amount: float = 100):
        """Main bot loop"""
        self.logger.info(f"Starting Binance Testnet trading bot for {self.symbol}")
        self.logger.info(f"Trading amount per position: {trade_amount} USDT")

        while True:
            try:
                # Get current state
                balances = self.get_account_balance()
                current_price = self.get_symbol_price()

                self.logger.info(f"\nCurrent price: ${current_price:.2f}")
                self.logger.info(f"Current balances: {balances}")

                # Calculate indicators and generate signal
                df = self.calculate_indicators()
                if df is not None:
                    signal = self.generate_signal(df)

                    if signal == 1:  # Buy signal
                        usdt_balance = balances.get('USDT', {}).get('free', 0)
                        if usdt_balance >= trade_amount:
                            quantity = self.calculate_position_size(trade_amount)
                            if quantity > 0:
                                self.logger.info(f"Buy signal! Placing order for {quantity} {self.symbol}")
                                self.place_order('BUY', quantity)
                        else:
                            self.logger.info("Insufficient USDT balance for buy order")

                    elif signal == -1:  # Sell signal
                        base_currency = self.symbol.replace('USDT', '')
                        base_balance = balances.get(base_currency, {}).get('free', 0)
                        if base_balance > 0:
                            self.logger.info(f"Sell signal! Placing order for {base_balance} {self.symbol}")
                            self.place_order('SELL', base_balance)
                        else:
                            self.logger.info(f"No {base_currency} balance to sell")

                    else:
                        self.logger.info("No trading signal")

                time.sleep(check_interval)

            except Exception as e:
                self.logger.error(f"Error in main loop: {e}")
                self.logger.error(f"\n Signal was {signal}")
                time.sleep(check_interval)


if __name__ == "__main__":
    load_dotenv()
    # Your Binance testnet API credentials
    API_KEY = os.getenv("API_KEY")
    API_SECRET = os.getenv("SECRET_KEY")

    # Trading parameters
    SYMBOL = "BTCUSDT"
    TRADE_AMOUNT = 100  # Amount in USDT to trade with

    # Initialize and run the bot
    bot = BinanceTestnetBot(API_KEY, API_SECRET, SYMBOL)
    bot.run_bot(trade_amount=TRADE_AMOUNT)
