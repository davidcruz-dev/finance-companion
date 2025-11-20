#!/usr/bin/env python3
import os
import json
import asyncio
import logging
import requests
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Bot configuration
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_USER_ID = int(os.getenv('TELEGRAM_USER_ID'))

class SimpleBitcoinBot:
    def __init__(self):
        self.app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
        self.last_analysis = None
        self.monitoring = False
        
    def get_fear_greed_index(self):
        """Get Fear & Greed Index from API"""
        try:
            response = requests.get("https://api.alternative.me/fng/", timeout=10)
            if response.status_code == 200:
                data = response.json()
                return {
                    'value': int(data['data'][0]['value']),
                    'classification': data['data'][0]['value_classification']
                }
        except Exception as e:
            logger.error(f"Error fetching Fear & Greed: {str(e)}")
        return {'value': 50, 'classification': 'Neutral'}
    
    def get_bitcoin_price(self):
        """Get current Bitcoin price"""
        try:
            response = requests.get("https://api.coinbase.com/v2/exchange-rates?currency=BTC", timeout=10)
            if response.status_code == 200:
                data = response.json()
                return float(data['data']['rates']['USD'])
        except Exception as e:
            logger.error(f"Error fetching BTC price: {str(e)}")
        return None
    
    def analyze_bitcoin(self):
        """Simple Bitcoin analysis based on Fear & Greed"""
        fg = self.get_fear_greed_index()
        price = self.get_bitcoin_price()
        
        # Simple contrarian logic
        if fg['value'] <= 25:  # Extreme Fear
            recommendation = "Strong BUY"
            reasoning = f"Extreme Fear ({fg['value']}) - Contrarian opportunity"
            emoji = "🚀"
        elif fg['value'] <= 45:  # Fear
            recommendation = "BUY"
            reasoning = f"Fear ({fg['value']}) - Good buying opportunity"
            emoji = "📈"
        elif fg['value'] >= 75:  # Greed
            recommendation = "SELL"
            reasoning = f"Greed ({fg['value']}) - Consider taking profits"
            emoji = "📉"
        elif fg['value'] >= 55:  # Some greed
            recommendation = "HOLD/SELL"
            reasoning = f"Greed building ({fg['value']}) - Be cautious"
            emoji = "⚠️"
        else:  # Neutral
            recommendation = "HOLD"
            reasoning = f"Neutral sentiment ({fg['value']}) - Wait for better setup"
            emoji = "⏸️"
        
        return {
            'price': price,
            'fear_greed': fg,
            'recommendation': recommendation,
            'reasoning': reasoning,
            'emoji': emoji,
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")
        }
    
    def format_analysis_message(self, analysis):
        """Format analysis into Telegram message"""
        msg = f"{analysis['emoji']} **Bitcoin Analysis**\n"
        msg += f"⏰ {analysis['timestamp']}\n\n"
        
        if analysis['price']:
            msg += f"💰 **Price:** ${analysis['price']:,.2f}\n"
        
        msg += f"😱 **Fear & Greed:** {analysis['fear_greed']['value']} ({analysis['fear_greed']['classification']})\n\n"
        msg += f"🎯 **Signal:** {analysis['recommendation']}\n"
        msg += f"💭 **Reason:** {analysis['reasoning']}\n"
        
        # Add basic trading levels
        if analysis['price']:
            if 'BUY' in analysis['recommendation']:
                msg += f"\n📊 **Suggested Entry:** ${analysis['price']:,.0f}\n"
                msg += f"🛑 **Stop Loss:** ${analysis['price'] * 0.95:,.0f} (-5%)\n"
                msg += f"🎁 **Target:** ${analysis['price'] * 1.15:,.0f} (+15%)\n"
        
        return msg

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        if update.effective_user.id != TELEGRAM_USER_ID:
            await update.message.reply_text("❌ Unauthorized access")
            return
            
        await update.message.reply_text(
            "🤖 **Simple Bitcoin Trading Bot**\n\n"
            "Uses Fear & Greed Index for contrarian signals\n\n"
            "Commands:\n"
            "/analyze - Get current analysis\n"
            "/monitor - Start auto monitoring (every 5 min)\n"
            "/stop - Stop monitoring\n"
            "/status - Bot status"
        )

    async def analyze_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /analyze command"""
        if update.effective_user.id != TELEGRAM_USER_ID:
            await update.message.reply_text("❌ Unauthorized access")
            return
            
        await update.message.reply_text("🔍 Analyzing Bitcoin...")
        
        analysis = self.analyze_bitcoin()
        message = self.format_analysis_message(analysis)
        await update.message.reply_text(message, parse_mode='Markdown')

    async def monitor_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /monitor command"""
        if update.effective_user.id != TELEGRAM_USER_ID:
            await update.message.reply_text("❌ Unauthorized access")
            return
            
        self.monitoring = True
        await update.message.reply_text("📡 Monitoring started! Checking every 5 minutes for signal changes.")
        asyncio.create_task(self.monitoring_loop())

    async def stop_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /stop command"""
        if update.effective_user.id != TELEGRAM_USER_ID:
            await update.message.reply_text("❌ Unauthorized access")
            return
            
        self.monitoring = False
        await update.message.reply_text("🛑 Monitoring stopped")

    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /status command"""
        if update.effective_user.id != TELEGRAM_USER_ID:
            await update.message.reply_text("❌ Unauthorized access")
            return
            
        status = "🟢 Active" if self.monitoring else "🔴 Inactive"
        await update.message.reply_text(f"🤖 **Bot Status**\nMonitoring: {status}")

    async def monitoring_loop(self):
        """Monitor for signal changes"""
        logger.info("Starting monitoring loop")
        
        while self.monitoring:
            try:
                analysis = self.analyze_bitcoin()
                
                # Check if recommendation changed
                if self.last_analysis is None or analysis['recommendation'] != self.last_analysis.get('recommendation'):
                    message = f"🚨 **SIGNAL CHANGE** 🚨\n\n{self.format_analysis_message(analysis)}"
                    await self.app.bot.send_message(chat_id=TELEGRAM_USER_ID, text=message, parse_mode='Markdown')
                    
                self.last_analysis = analysis
                await asyncio.sleep(300)  # 5 minutes
                
            except Exception as e:
                logger.error(f"Error in monitoring: {str(e)}")
                await asyncio.sleep(300)

    def setup_handlers(self):
        """Setup command handlers"""
        self.app.add_handler(CommandHandler("start", self.start_command))
        self.app.add_handler(CommandHandler("analyze", self.analyze_command))
        self.app.add_handler(CommandHandler("monitor", self.monitor_command))
        self.app.add_handler(CommandHandler("stop", self.stop_command))
        self.app.add_handler(CommandHandler("status", self.status_command))

    async def run(self):
        """Run the bot"""
        logger.info("Starting Simple Bitcoin Bot...")
        self.setup_handlers()
        
        await self.app.bot.send_message(
            chat_id=TELEGRAM_USER_ID,
            text="🤖 Simple Bitcoin Bot online!\nUse /start to begin."
        )
        
        await self.app.initialize()
        await self.app.start()
        await self.app.updater.start_polling()
        
        logger.info("Bot running...")
        
        try:
            await asyncio.Future()
        except KeyboardInterrupt:
            logger.info("Shutting down...")
        finally:
            await self.app.updater.stop()
            await self.app.stop()
            await self.app.shutdown()

if __name__ == "__main__":
    bot = SimpleBitcoinBot()
    asyncio.run(bot.run())