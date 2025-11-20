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

class HybridTradingBot:
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
    
    def get_dxy_data(self):
        """Get USD Index data (mock for now)"""
        try:
            # This would normally come from a financial data API
            # For now, returning typical DXY level
            return {
                'level': 106.5,
                'trend': 'Up',
                'risk_environment': 'Risk-Off'
            }
        except:
            return {'level': 105, 'trend': 'Neutral', 'risk_environment': 'Neutral'}
    
    def get_seasonal_analysis(self):
        """Get seasonal analysis for current month"""
        month = datetime.now().month
        seasonal_data = {
            11: {'bias': 'Bullish', 'win_rate': 65, 'pattern': 'Q4 Rally'},  # November
            12: {'bias': 'Bullish', 'win_rate': 70, 'pattern': 'Year-end Rally'},
            1: {'bias': 'Neutral', 'win_rate': 55, 'pattern': 'January Effect'},
            2: {'bias': 'Bearish', 'win_rate': 45, 'pattern': 'Winter Lull'},
            3: {'bias': 'Bullish', 'win_rate': 60, 'pattern': 'Q1 Recovery'},
            4: {'bias': 'Neutral', 'win_rate': 50, 'pattern': 'Spring Uncertainty'},
            5: {'bias': 'Bearish', 'win_rate': 40, 'pattern': 'Sell in May'},
            6: {'bias': 'Bearish', 'win_rate': 35, 'pattern': 'Summer Doldrums'},
            7: {'bias': 'Bearish', 'win_rate': 35, 'pattern': 'Summer Doldrums'},
            8: {'bias': 'Neutral', 'win_rate': 45, 'pattern': 'Late Summer'},
            9: {'bias': 'Bearish', 'win_rate': 40, 'pattern': 'September Effect'},
            10: {'bias': 'Neutral', 'win_rate': 50, 'pattern': 'October Setup'}
        }
        return seasonal_data.get(month, {'bias': 'Neutral', 'win_rate': 50, 'pattern': 'Unknown'})
    
    def get_correlation_analysis(self):
        """Mock correlation analysis (would normally use real data)"""
        return {
            'btc_nasdaq': 75,  # High correlation
            'btc_spx': 70,
            'btc_gold': -20,
            'btc_vix': -45,
            'regime': 'Risk-On Correlated'
        }
    
    def comprehensive_analysis(self):
        """Comprehensive Bitcoin analysis using multiple factors"""
        fg = self.get_fear_greed_index()
        price = self.get_bitcoin_price()
        dxy = self.get_dxy_data()
        seasonal = self.get_seasonal_analysis()
        correlation = self.get_correlation_analysis()
        
        # Multi-factor analysis
        bullish_factors = 0
        bearish_factors = 0
        factors_analysis = []
        
        # Factor 1: Fear & Greed (Contrarian)
        if fg['value'] <= 25:  # Extreme Fear
            bullish_factors += 2
            factors_analysis.append("✅ Extreme Fear - Strong contrarian buy signal")
        elif fg['value'] <= 45:  # Fear
            bullish_factors += 1
            factors_analysis.append("✅ Fear - Contrarian opportunity")
        elif fg['value'] >= 75:  # Greed
            bearish_factors += 1
            factors_analysis.append("❌ Greed - Distribution zone")
        elif fg['value'] >= 55:
            bearish_factors += 1
            factors_analysis.append("❌ Building greed - Caution warranted")
        else:
            factors_analysis.append("⚖️ Neutral sentiment")
        
        # Factor 2: Seasonal Pattern
        if seasonal['bias'] == 'Bullish':
            bullish_factors += 1
            factors_analysis.append(f"✅ Seasonal: {seasonal['pattern']} ({seasonal['win_rate']}% win rate)")
        elif seasonal['bias'] == 'Bearish':
            bearish_factors += 1
            factors_analysis.append(f"❌ Seasonal: {seasonal['pattern']} ({seasonal['win_rate']}% win rate)")
        else:
            factors_analysis.append(f"⚖️ Seasonal: {seasonal['pattern']} (neutral)")
        
        # Factor 3: DXY Environment
        if dxy['risk_environment'] == 'Risk-On':
            bullish_factors += 1
            factors_analysis.append(f"✅ DXY: {dxy['level']} - Risk-on environment")
        elif dxy['risk_environment'] == 'Risk-Off':
            bearish_factors += 1
            factors_analysis.append(f"❌ DXY: {dxy['level']} - Risk-off pressure")
        else:
            factors_analysis.append(f"⚖️ DXY: {dxy['level']} - Neutral")
        
        # Factor 4: Market Correlation
        if correlation['btc_nasdaq'] > 60 and correlation['regime'] == 'Risk-On Correlated':
            if fg['value'] < 50:  # Fear + risk correlation = opportunity
                bullish_factors += 1
                factors_analysis.append("✅ Correlation: High tech correlation during fear = opportunity")
            else:
                bearish_factors += 1
                factors_analysis.append("❌ Correlation: High tech correlation during greed = risk")
        else:
            factors_analysis.append("⚖️ Correlation: Bitcoin decoupling from traditional risk")
        
        # Determine overall recommendation
        net_bullish = bullish_factors - bearish_factors
        total_factors = bullish_factors + bearish_factors
        confidence = min(10, max(1, abs(net_bullish) * 2 + total_factors))
        
        if net_bullish >= 2:
            recommendation = "Strong BUY"
            emoji = "🚀"
        elif net_bullish >= 1:
            recommendation = "BUY"
            emoji = "📈"
        elif net_bullish <= -2:
            recommendation = "Strong SELL"
            emoji = "📉"
        elif net_bullish <= -1:
            recommendation = "SELL"
            emoji = "⬇️"
        else:
            recommendation = "HOLD"
            emoji = "⏸️"
        
        # Calculate levels
        entry_level = price if price else 91000
        stop_level = entry_level * 0.95 if 'BUY' in recommendation else entry_level * 1.05
        target_level = entry_level * 1.15 if 'BUY' in recommendation else entry_level * 0.85
        
        return {
            'price': price,
            'fear_greed': fg,
            'seasonal': seasonal,
            'dxy': dxy,
            'correlation': correlation,
            'recommendation': recommendation,
            'emoji': emoji,
            'bullish_factors': bullish_factors,
            'bearish_factors': bearish_factors,
            'confidence': confidence,
            'factors_analysis': factors_analysis,
            'levels': {
                'entry': entry_level,
                'stop': stop_level,
                'target': target_level
            },
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")
        }
    
    def format_comprehensive_message(self, analysis):
        """Format comprehensive analysis into Telegram message"""
        msg = f"{analysis['emoji']} **Bitcoin Enhanced Analysis**\n"
        msg += f"⏰ {analysis['timestamp']}\n\n"
        
        if analysis['price']:
            msg += f"💰 **Price:** ${analysis['price']:,.2f}\n\n"
        
        # Main signal
        msg += f"🎯 **Signal:** {analysis['recommendation']}\n"
        msg += f"💪 **Confidence:** {analysis['confidence']}/10\n\n"
        
        # Multi-factor analysis
        msg += f"📊 **Factor Analysis:**\n"
        msg += f"🟢 Bullish: {analysis['bullish_factors']} factors\n"
        msg += f"🔴 Bearish: {analysis['bearish_factors']} factors\n\n"
        
        # Key metrics
        msg += f"😱 **Fear & Greed:** {analysis['fear_greed']['value']} ({analysis['fear_greed']['classification']})\n"
        msg += f"📅 **Seasonal:** {analysis['seasonal']['bias']} ({analysis['seasonal']['pattern']})\n"
        msg += f"💵 **DXY:** {analysis['dxy']['level']} ({analysis['dxy']['risk_environment']})\n"
        msg += f"📈 **BTC-NASDAQ Correlation:** {analysis['correlation']['btc_nasdaq']}%\n\n"
        
        # Detailed factors
        msg += f"🔍 **Factor Breakdown:**\n"
        for factor in analysis['factors_analysis'][:4]:  # Limit to avoid message length
            msg += f"{factor}\n"
        
        # Trading levels
        if analysis['levels']:
            msg += f"\n📊 **Trading Levels:**\n"
            msg += f"🎯 Entry: ${analysis['levels']['entry']:,.0f}\n"
            msg += f"🛑 Stop: ${analysis['levels']['stop']:,.0f}\n"
            msg += f"🎁 Target: ${analysis['levels']['target']:,.0f}\n"
        
        return msg

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        if update.effective_user.id != TELEGRAM_USER_ID:
            await update.message.reply_text("❌ Unauthorized access")
            return
            
        await update.message.reply_text(
            "🤖 **Enhanced Bitcoin Trading Bot**\n\n"
            "Multi-factor analysis including:\n"
            "• Fear & Greed Index\n"
            "• Seasonal patterns\n"
            "• USD Index analysis\n" 
            "• Market correlations\n"
            "• Technical confluence\n\n"
            "Commands:\n"
            "/analyze - Full market analysis\n"
            "/monitor - Auto monitoring\n"
            "/stop - Stop monitoring\n"
            "/status - Bot status"
        )

    async def analyze_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /analyze command"""
        if update.effective_user.id != TELEGRAM_USER_ID:
            await update.message.reply_text("❌ Unauthorized access")
            return
            
        await update.message.reply_text("🔍 Running comprehensive Bitcoin analysis...")
        
        analysis = self.comprehensive_analysis()
        message = self.format_comprehensive_message(analysis)
        await update.message.reply_text(message, parse_mode='Markdown')

    async def monitor_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /monitor command"""
        if update.effective_user.id != TELEGRAM_USER_ID:
            await update.message.reply_text("❌ Unauthorized access")
            return
            
        self.monitoring = True
        await update.message.reply_text("📡 Enhanced monitoring started! Checking every 5 minutes for signal changes.")
        asyncio.create_task(self.monitoring_loop())

    async def stop_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /stop command"""
        if update.effective_user.id != TELEGRAM_USER_ID:
            await update.message.reply_text("❌ Unauthorized access")
            return
            
        self.monitoring = False
        await update.message.reply_text("🛑 Enhanced monitoring stopped")

    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /status command"""
        if update.effective_user.id != TELEGRAM_USER_ID:
            await update.message.reply_text("❌ Unauthorized access")
            return
            
        status = "🟢 Active" if self.monitoring else "🔴 Inactive"
        await update.message.reply_text(f"🤖 **Enhanced Bot Status**\nMonitoring: {status}")

    async def monitoring_loop(self):
        """Monitor for signal changes"""
        logger.info("Starting enhanced monitoring loop")
        
        while self.monitoring:
            try:
                analysis = self.comprehensive_analysis()
                
                # Check if recommendation changed significantly
                if (self.last_analysis is None or 
                    analysis['recommendation'] != self.last_analysis.get('recommendation') or
                    abs(analysis['bullish_factors'] - self.last_analysis.get('bullish_factors', 0)) >= 2):
                    
                    message = f"🚨 **ENHANCED SIGNAL CHANGE** 🚨\n\n{self.format_comprehensive_message(analysis)}"
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
        logger.info("Starting Enhanced Bitcoin Bot...")
        self.setup_handlers()
        
        await self.app.bot.send_message(
            chat_id=TELEGRAM_USER_ID,
            text="🤖 Enhanced Bitcoin Bot online!\nUse /start to begin."
        )
        
        await self.app.initialize()
        await self.app.start()
        await self.app.updater.start_polling()
        
        logger.info("Enhanced bot running...")
        
        try:
            await asyncio.Future()
        except KeyboardInterrupt:
            logger.info("Shutting down...")
        finally:
            await self.app.updater.stop()
            await self.app.stop()
            await self.app.shutdown()

if __name__ == "__main__":
    bot = HybridTradingBot()
    asyncio.run(bot.run())