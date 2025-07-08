import telegram
import asyncio
import pandas as pd
import numpy as np
import os
from datetime import datetime, timedelta
from telegram.ext import Application, CommandHandler
from telegram.error import TelegramError
from fastapi import FastAPI
from contextlib import asynccontextmanager
from typing import Dict
import ccxt.async_support as ccxt
import requests
import uvicorn
import pytz

try:
    from utils.logger import logger
    from utils.helpers import get_timestamp, format_timestamp, is_cooldown_active, scan_pause
    from model.predictor import SignalPredictor
    from telebot.sender import send_signal
    from data.collector import fetch_realtime_data
    from data.backtesting import backtest_signals
    from core.indicators import calculate_indicators
    from core.candle_patterns import identify_candle_patterns
    from core.multi_timeframe import multi_timeframe_boost
except ImportError as e:
    print(f"Import error: {e}. Ensure utils/, core/, data/, model/, telebot/ directories exist.")
    exit(1)

# Hard-coded environment variables
BOT_TOKEN = "7620836100:AAGY7xBjNJMKlzrDDMrQ5hblXzd_k_BvEtU"
CHAT_ID = "-4694205383"
API_KEY = "QdxVRt0QdSJYQNAp8f6V4T1NmJvmZjG9D2CUL3sySv6CNl6WisDQMBzFh2P807ag"
API_SECRET = "z0ucU4VCMlCSPA5ntIvqmKAy7yO5wLtweLyxL6hY8eMHFbG4C2nng6SZhT4gBAM5"
PORT = 5000
MIN_VOLUME = 500_000
MAX_SIGNALS_PER_MINUTE = 10
CYCLE_INTERVAL = 300
BATCH_SIZE = 30
COOLDOWN = 4 * 3600
RESET_INTERVAL = 24 * 3600
BLACKLIST = {'PNUT/USDT', 'SAHARA/USDT', 'SYRUP/USDT', 'VIRTUAL/USDT', 'WIF/USDT', 'NEIRO/USDT', 'FUN/USDT', 'NEWT/USDT'}

last_signal_time: Dict[str, datetime] = {}
last_reset_time = datetime.now(pytz.UTC)
application = None

app = FastAPI()

@asynccontextmanager
async def lifespan(app):
    await start_bot()
    yield
    if application:
        await application.updater.stop()
        await application.stop()
        logger.info("Application shutdown complete")

app = FastAPI(lifespan=lifespan)

@app.get("/")
async def root():
    return {"message": "Crypto Futures Scalping Bot is running"}

@app.get("/backtest/{symbol}")
async def run_backtest(symbol: str):
    try:
        results = await backtest_signals(symbol, timeframe="15m", limit=1000)
        if results is None:
            return {"error": f"No backtest results for {symbol}"}
        return results
    except Exception as e:
        logger.error(f"Backtest error for {symbol}: {str(e)}", exc_info=True)
        return {"error": str(e)}

def format_timestamp_to_pk(utc_timestamp_str):
    try:
        utc_time = datetime.fromisoformat(utc_timestamp_str.replace('Z', '+00:00').split('+00:00+')[0])
        utc_time = utc_time.replace(tzinfo=pytz.UTC)
        pk_time = utc_time.astimezone(pytz.timezone('Asia/Karachi'))
        return pk_time.strftime('%d %B %Y, %I:%M %p')
    except Exception as e:
        logger.error(f"Error converting timestamp: {str(e)}")
        return utc_timestamp_str

def determine_leverage(indicators):
    score = 0
    if isinstance(indicators, str):
        indicators = indicators.split(', ')
    if 'MACD' in indicators:
        score += 2
    if 'Strong Trend' in indicators:
        score += 2
    if 'VWAP' in indicators:
        score += 1
    if 'Stochastic' in indicators:
        score -= 1
    if 'Bollinger Breakout' in indicators:
        score += 2
    if 'RSI' in indicators:
        score += 1
    return '40x' if score >= 5 else '30x' if score >= 3 else '20x' if score >= 1 else '10x'

def calculate_profit_percentages(entry, direction, atr):
    try:
        if direction.upper() == 'LONG':
            tp1 = entry + (1 * atr)
            tp2 = entry + (1.5 * atr)
            tp3 = entry + (2 * atr)
            sl = entry - (1 * atr)
            tp1_percent = ((tp1 - entry) / entry) * 100
            tp2_percent = ((tp2 - entry) / entry) * 100
            tp3_percent = ((tp3 - entry) / entry) * 100
            sl_percent = ((entry - sl) / entry) * 100
        else:
            tp1 = entry - (1 * atr)
            tp2 = entry - (1.5 * atr)
            tp3 = entry - (2 * atr)
            sl = entry + (1 * atr)
            tp1_percent = ((entry - tp1) / entry) * 100
            tp2_percent = ((entry - tp2) / entry) * 100
            tp3_percent = ((entry - tp3) / entry) * 100
            sl_percent = ((sl - entry) / entry) * 100
        return {
            'tp1': round(tp1, 4), 'tp2': round(tp2, 4), 'tp3': round(tp3, 4), 'sl': round(sl, 4),
            'tp1_percent': round(tp1_percent, 2), 'tp2_percent': round(tp2_percent, 2),
            'tp3_percent': round(tp3_percent, 2), 'sl_percent': round(sl_percent, 2)
        }
    except Exception as e:
        logger.error(f"Error in calculate_profit_percentages: {str(e)}")
        return {
            'tp1': entry, 'tp2': entry, 'tp3': entry, 'sl': entry,
            'tp1_percent': 0, 'tp2_percent': 0, 'tp3_percent': 0, 'sl_percent': 0
        }

def get_24h_volume(symbol):
    try:
        symbol_clean = symbol.replace('/', '').upper()
        url = f"https://fapi.binance.com/fapi/v1/ticker/24hr?symbol={symbol_clean}"
        response = requests.get(url, timeout=5)
        data = response.json()
        quote_volume = float(data.get('quoteVolume', 0))
        logger.info(f"[{symbol}] Volume check: {quote_volume:,.2f}")
        return quote_volume, f"${quote_volume:,.2f}"
    except Exception as e:
        logger.error(f"Error fetching volume for {symbol}: {str(e)}")
        return 0, '$0.00'

async def test_api_keys(exchange):
    try:
        logger.info("Testing Binance Futures API keys")
        ticker = await exchange.fetch_ticker('BTC/USDT')
        logger.info(f"API key test successful: {ticker['symbol']} - {ticker['last']}")
        return True
    except Exception as e:
        logger.error(f"API key test failed: {str(e)}", exc_info=True)
        bot = telegram.Bot(token=BOT_TOKEN)
        await bot.send_message(chat_id=CHAT_ID, text=f"⚠ API key test failed: {str(e)}")
        return False

async def fetch_usdt_pairs(exchange):
    try:
        logger.info("Fetching USDT pairs from Binance Futures")
        markets = await exchange.load_markets()
        logger.info(f"Total markets fetched: {len(markets)}")
        symbols = [
            symbol for symbol in markets
            if symbol.endswith('/USDT') and markets[symbol]['active']
            and markets[symbol].get('info', {}).get('status') == 'TRADING'
            and markets[symbol].get('info', {}).get('contractType') == 'PERPETUAL'
            and symbol not in BLACKLIST
        ]
        logger.info(f"Total USDT pairs after initial filtering: {len(symbols)}")
        logger.debug(f"Filtered symbols: {symbols[:10]}")

        if not symbols:
            logger.warning("No valid USDT pairs found")
            return []

        # Limit to top 50 symbols to reduce API calls
        symbols = symbols[:50]
        logger.info(f"Limited to top {len(symbols)} USDT pairs for volume check")

        # Select top BATCH_SIZE symbols by volume
        volume_data = []
        for symbol in symbols:
            if symbol in last_signal_time and is_cooldown_active(symbol, last_signal_time, COOLDOWN):
                logger.debug(f"[{symbol}] In cooldown, skipping")
                continue
            volume, volume_str = get_24h_volume(symbol)
            if volume >= MIN_VOLUME:
                volume_data.append((symbol, volume))
            await asyncio.sleep(0.2)  # Increased delay to avoid rate limits
        if not volume_data:
            logger.warning("No symbols with sufficient volume")
            bot = telegram.Bot(token=BOT_TOKEN)
            await bot.send_message(chat_id=CHAT_ID, text="⚠ No symbols with volume > $500,000 found")
            return []

        volume_data.sort(key=lambda x: x[1], reverse=True)
        selected_symbols = [pair[0] for pair in volume_data[:BATCH_SIZE]]
        logger.info(f"Selected top {len(selected_symbols)} USDT pairs with volume > ${MIN_VOLUME:,}: {selected_symbols}")

        if not selected_symbols:
            logger.warning("No symbols selected after volume filtering")
            bot = telegram.Bot(token=BOT_TOKEN)
            await bot.send_message(chat_id=CHAT_ID, text="⚠ No symbols selected after volume filtering")
            return []

        return selected_symbols
    except Exception as e:
        logger.error(f"Error fetching USDT pairs: {str(e)}", exc_info=True)
        bot = telegram.Bot(token=BOT_TOKEN)
        await bot.send_message(chat_id=CHAT_ID, text=f"⚠ Binance Futures API error: {str(e)}")
        return []

async def process_symbol(exchange, symbol):
    try:
        logger.info(f"[{symbol}] Scanning for signal")
        current_time = datetime.now(pytz.UTC)
        if is_cooldown_active(symbol, last_signal_time, COOLDOWN):
            logger.info(f"[{symbol}] In cooldown")
            return None

        volume, volume_str = get_24h_volume(symbol)
        if volume < MIN_VOLUME:
            logger.info(f"[{symbol}] Low volume: {volume_str}")
            return None

        ticker = await exchange.fetch_ticker(symbol)
        if ticker['quoteVolume'] < MIN_VOLUME:
            logger.info(f"[{symbol}] Low ticker volume: ${ticker['quoteVolume']:.2f}")
            return None

        timeframes = ['5m', '15m', '1h', '4h']
        ohlcv_data = []
        for tf in timeframes:
            for attempt in range(3):
                try:
                    ohlcv = await fetch_realtime_data(symbol, tf, limit=50)
                    if ohlcv is None or len(ohlcv) < 30:
                        logger.warning(f"[{symbol}] Insufficient data for {tf} on attempt {attempt + 1}")
                        if attempt < 2:
                            await asyncio.sleep(2)
                            continue
                        return None
                    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']).astype(np.float32)
                    if df.isnull().any().any():
                        logger.warning(f"[{symbol}] NaN values in {tf} data")
                        return None
                    df = calculate_indicators(df)
                    df = identify_candle_patterns(df)
                    required_indicators = ['ma20', 'macd', 'rsi', 'adx', 'vwap', 'atr', 'bollinger_upper', 'bollinger_lower', 'stoch_k', 'stoch_d']
                    if not all(ind in df.columns for ind in required_indicators):
                        logger.warning(f"[{symbol}] Missing required indicators for {tf}: {list(df.columns)}")
                        return None
                    logger.info(f"[{symbol}] Calculated indicators for {tf}: {list(df.columns)}")
                    ohlcv_data.append(df)
                    break
                except Exception as e:
                    logger.error(f"[{symbol}] Retry {attempt + 1}/3 for {tf}: {str(e)}")
                    if attempt < 2:
                        await asyncio.sleep(2)
                        continue
                    logger.error(f"[{symbol}] Failed to fetch data for {tf} after 3 attempts")
                    return None

        if len(ohlcv_data) < len(timeframes):
            logger.warning(f"[{symbol}] Incomplete data for all timeframes")
            return None

        predictor = SignalPredictor()
        signal = await predictor.predict_signal(symbol, ohlcv_data[0], '15m')
        if not signal or signal['confidence'] < 50.0:  # Lowered threshold
            logger.info(f"[{symbol}] No signal or low confidence: {signal.get('confidence', 0) if signal else 'None'}")
            return None

        if signal['tp1'] == signal['tp2'] == signal['tp3'] == signal['entry']:
            logger.info(f"[{symbol}] Identical TP/entry values")
            return None

        atr = ohlcv_data[0]['atr'].iloc[-1]
        profit_levels = calculate_profit_percentages(signal['entry'], signal['direction'], atr)
        signal.update(profit_levels)

        boost = await multi_timeframe_boost(symbol, exchange, signal['direction'], timeframes)
        logger.info(f"[{symbol}] Multi-timeframe boost: {boost:.2f} ({int(boost * len(timeframes))}/{len(timeframes)})")
        if boost < 0.5:  # Lowered threshold for 2/4 agreement
            logger.info(f"[{symbol}] No multi-timeframe agreement: boost={boost:.2f}")
            return None

        signal['quote_volume_24h'] = volume_str
        signal['leverage'] = determine_leverage(signal['conditions'])
        signal['timestamp'] = format_timestamp(get_timestamp())
        signal['trade_duration'] = '4h'
        logger.info(f"[{symbol}] Signal generated: {signal['direction']}, Confidence: {signal['confidence']:.2f}%, Indicators: {signal['conditions']}, Boost: {boost:.2f}")
        await send_signal(signal, BOT_TOKEN, CHAT_ID)
        last_signal_time[symbol] = current_time
        return signal
    except Exception as e:
        logger.error(f"[{symbol}] Error processing: {str(e)}")
        return None

async def start(update, context):
    try:
        await update.message.reply_text('Crypto Futures Scalping Bot is running! Use /help for commands.')
        logger.info('Start command executed')
    except Exception as e:
        logger.error(f"Error in start command: {str(e)}")

async def help(update, context):
    try:
        help_text = (
            '📋 Crypto Futures Scalping Bot Commands\n'
            '/start - Start bot\n'
            '/status - Bot status\n'
            '/signal - Latest signal\n'
            '/test - Test connectivity\n'
            '/help - Show this message'
        )
        await update.message.reply_text(help_text, parse_mode='Markdown')
        logger.info('Help command executed')
    except Exception as e:
        logger.error(f"Error in help command: {str(e)}")

async def test(update, context):
    try:
        await update.message.reply_text('Test message from Crypto Futures Scalping Bot!')
        logger.info('Test message sent')
    except Exception as e:
        logger.error(f"Error in test command: {str(e)}")

async def status(update, context):
    try:
        bot = telegram.Bot(token=BOT_TOKEN)
        bot_info = await bot.get_me()
        active_signals = len([s for s, t in last_signal_time.items() if (datetime.now(pytz.UTC) - t).total_seconds() < COOLDOWN])
        status_text = (
            f"🟢 Bot running\n"
            f"🤖 @{bot_info.username}\n"
            f"📈 Active signals: {active_signals}"
        )
        await update.message.reply_text(status_text, parse_mode='Markdown')
        logger.info('Status command executed')
    except Exception as e:
        logger.error(f"Error in status: {str(e)}")

async def signal(update, context):
    try:
        file_path = 'logs/signals_log_new.csv'
        if not os.path.exists(file_path):
            await update.message.reply_text('No signals available.')
            return
        df = pd.read_csv(file_path)
        if df.empty:
            await update.message.reply_text('No signals available.')
            return
        latest_signal = df.iloc[-1]
        conditions_str = ', '.join(latest_signal['conditions'].split(', ')) if 'conditions' in latest_signal else 'None'
        volume, volume_str = get_24h_volume(latest_signal['symbol'])
        if volume < MIN_VOLUME:
            logger.warning(f"[{latest_signal['symbol']}] Low volume: {volume_str}")
            await update.message.reply_text('Insufficient signal volume.')
            return

        latest_signal['leverage'] = determine_leverage(latest_signal['conditions'])
        latest_signal['quote_volume_24h'] = volume_str
        latest_signal['timestamp'] = format_timestamp_to_pk(latest_signal['timestamp'])

        message = (
            f"📈 Futures Scalping Signal\n"
            f"💱 Symbol: {latest_signal['symbol']}\n"
            f"📊 Direction: {latest_signal['direction']}\n"
            f"⏰ Timeframe: {latest_signal['timeframe']}\n"
            f"⏳ Duration: {latest_signal['trade_duration']}\n"
            f"💰 Entry: ${latest_signal['entry']:.4f}\n"
            f"🎯 TP1: ${latest_signal['tp1']:.4f} ({latest_signal['tp1_percent']:.2f}%)\n"
            f"🎯 TP2: ${latest_signal['tp2']:.4f} ({latest_signal['tp2_percent']:.2f}%)\n"
            f"🎯 TP3: ${latest_signal['tp3']:.4f} ({latest_signal['tp3_percent']:.2f}%)\n"
            f"🛑 SL: ${latest_signal['sl']:.4f} ({latest_signal['sl_percent']:.2f}%)\n"
            f"🔍 Confidence: {latest_signal['confidence']:.2f}%\n"
            f"⚡ Type: {latest_signal['trade_type']}\n"
            f"⚖ Leverage: {latest_signal.get('leverage', 'N/A')}\n"
            f"📈 Volume: ${latest_signal['volume']:,.2f}\n"
            f"📈 24h Volume: {latest_signal['quote_volume_24h']}\n"
            f"🔎 Indicators: {conditions_str}\n"
            f"🕒 Timestamp: {latest_signal['timestamp']}"
        )
        await update.message.reply_text(message, parse_mode='Markdown')
        logger.info('Signal command executed')
    except Exception as e:
        logger.error(f"Error handling signal: {str(e)}")

async def start_bot():
    global application, last_signal_time, last_reset_time
    try:
        logger.info("Starting bot initialization")
        if not API_KEY or not API_SECRET:
            logger.error("Binance API key/secret missing")
            bot = telegram.Bot(token=BOT_TOKEN)
            await bot.send_message(chat_id=CHAT_ID, text="⚠️ API key/secret missing")
            return

        logger.info("Initializing Binance Futures exchange")
        exchange = ccxt.binance({
            'apiKey': API_KEY,
            'secret': API_SECRET,
            'enableRateLimit': True,
            'options': {'defaultType': 'future', 'adjustForTimeDifference': True}
        })

        if not await test_api_keys(exchange):
            logger.error("Stopping bot due to invalid API keys")
            return

        last_signal_time = {}
        signal_count = 0
        last_signal_minute = get_timestamp() // 60

        logger.info("Setting up Telegram bot")
        application = Application.builder().token(BOT_TOKEN).build()
        application.add_handler(CommandHandler('start', start))
        application.add_handler(CommandHandler('help', help))
        application.add_handler(CommandHandler('test', test))
        application.add_handler(CommandHandler('status', status))
        application.add_handler(CommandHandler('signal', signal))
        await application.initialize()
        await application.start()
        await application.updater.start_polling(allowed_updates=["message"])
        logger.info("Telegram bot polling started")

        while True:
            try:
                current_time = datetime.now(pytz.UTC)
                if (current_time - last_reset_time).total_seconds() >= RESET_INTERVAL:
                    last_signal_time.clear()
                    last_reset_time = current_time
                    logger.info("Cooldowns reset after 24 hours")

                logger.info("Starting new scan cycle")
                selected_symbols = await fetch_usdt_pairs(exchange)
                if not selected_symbols:
                    logger.warning("No USDT pairs found, retrying in 60s")
                    await asyncio.sleep(60)
                    continue

                if len(selected_symbols) > BATCH_SIZE:
                    logger.warning(f"Selected {len(selected_symbols)} symbols, expected {BATCH_SIZE}. Truncating to {BATCH_SIZE}")
                    selected_symbols = selected_symbols[:BATCH_SIZE]

                logger.info(f"Processing batch of {len(selected_symbols)} symbols: {selected_symbols}")
                tasks = [process_symbol(exchange, symbol) for symbol in selected_symbols]
                results = await asyncio.gather(*tasks, return_exceptions=True)

                valid_signals = [r for r in results if r and not isinstance(r, Exception)]
                if valid_signals:
                    current_time = get_timestamp()
                    current_minute = current_time // 60
                    if current_minute > last_signal_minute:
                        signal_count = 0
                        last_signal_minute = current_minute

                    if signal_count >= MAX_SIGNALS_PER_MINUTE:
                        logger.info("Max signals limit reached for this minute")
                        await asyncio.sleep(60)
                        continue

                    signal_count += len(valid_signals)
                    logger.info(f"Generated {len(valid_signals)} valid signals in batch")

                await asyncio.sleep(5)
                logger.info("Scan cycle completed")
                await scan_pause(CYCLE_INTERVAL)

            except Exception as e:
                logger.error(f"Main loop error: {str(e)}", exc_info=True)
                await asyncio.sleep(60)

        await exchange.close()

    except Exception as e:
        logger.error(f"Bot startup error: {str(e)}", exc_info=True)
        await asyncio.sleep(60)
        raise

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT, workers=1)