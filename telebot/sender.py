import telegram
from utils.logger import logger

async def send_signal(signal, bot_token, chat_id):
    try:
        bot = telegram.Bot(token=bot_token)
        entry = signal['entry']
        tp1 = signal['tp1']
        tp2 = signal['tp2']
        tp3 = signal['tp3']
        sl = signal['sl']

        message = (
            f"📈 Futures Scalping Signal for {signal['symbol']}\n"
            f"📊 Direction: {signal['direction']}\n"
            f"⏰ Timeframe: {signal['timeframe']}\n"
            f"⏳ Trade Duration: {signal['trade_duration']}\n"
            f"💰 Entry: {entry:.4f}\n"
            f"🎯 TP1: {tp1:.4f} ({signal['tp1_percent']:.2f}% / {signal['tp1_possibility']:.2f}%)\n"
            f"🎯 TP2: {tp2:.4f} ({signal['tp2_percent']:.2f}% / {signal['tp2_possibility']:.2f}%)\n"
            f"🎯 TP3: {tp3:.4f} ({signal['tp3_percent']:.2f}% / {signal['tp3_possibility']:.2f}%)\n"
            f"🛑 SL: {sl:.4f} ({signal['sl_percent']:.2f}% / {signal['sl_possibility']:.2f}%)\n"
            f"⚖ Leverage: {signal['leverage']}\n"
            f"🔍 Confidence: {signal['confidence']:.2f}%"
        )
        await bot.send_message(chat_id=chat_id, text=message)
        logger.info(f"Signal sent to Telegram: {signal['symbol']} - {signal['direction']}")
    except Exception as e:
        logger.error(f"Error sending signal to Telegram: {str(e)}")