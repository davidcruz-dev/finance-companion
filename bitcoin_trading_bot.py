#!/usr/bin/env python3
import os
import json
import asyncio
import logging
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import requests
from dotenv import load_dotenv
from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient
from azure.core.credentials import AzureKeyCredential

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Bot configuration
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_USER_ID = int(os.getenv('TELEGRAM_USER_ID'))
FOUNDRY_ENDPOINT = os.getenv('FOUNDRY_ENDPOINT')
FOUNDRY_API_KEY = os.getenv('FOUNDRY_API_KEY')
CHECK_INTERVAL = int(os.getenv('CHECK_INTERVAL', 300))  # 5 minutes default

class BitcoinTradingBot:
    def __init__(self):
        self.app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
        self.last_signal = None
        self.monitoring = False
        
    async def query_foundry_agent(self):
        """Query the Microsoft Foundry agent for Bitcoin analysis"""
        try:
            # Use Azure AI Projects SDK
            myEndpoint = "https://financecompanion-resource.services.ai.azure.com/api/projects/financecompanion"
            
            # Use DefaultAzureCredential since user is now logged in
            project_client = AIProjectClient(
                endpoint=myEndpoint,
                credential=DefaultAzureCredential(),
            )
            
            myAgent = "FinanceCompanion"
            agent = project_client.agents.get(agent_name=myAgent)
            logger.info(f"Retrieved agent: {agent.name}")
            
            openai_client = project_client.get_openai_client()
            
            # Enhanced prompt for comprehensive Bitcoin analysis
            prompt = """Analyze current Bitcoin market conditions using all your available data sources and provide a comprehensive trading signal. Include:

1. Current Fear & Greed Index analysis
2. Seasonal patterns and historical tendencies for current month
3. USD Dollar Index impact on risk-on/risk-off environment
4. Market correlations with NASDAQ, S&P500, Gold, VIX
5. COT positioning and institutional flows
6. Technical price action and key levels
7. Multi-factor confluence analysis

Provide your analysis in JSON format with clear buy/sell/hold recommendation, reasoning, confidence score, and specific price levels."""
            
            # Add retry logic for rate limits
            import time
            max_retries = 3
            retry_delay = 60  # 1 minute
            
            for attempt in range(max_retries):
                try:
                    response = openai_client.responses.create(
                        input=[{"role": "user", "content": prompt}],
                        extra_body={"agent": {"name": agent.name, "type": "agent_reference"}},
                    )
                    break  # Success, exit retry loop
                except Exception as e:
                    if "429" in str(e) and attempt < max_retries - 1:
                        logger.info(f"Rate limit hit, waiting {retry_delay} seconds before retry {attempt + 1}")
                        time.sleep(retry_delay)
                        continue
                    else:
                        raise e  # Re-raise if not rate limit or max retries reached
            
            logger.info("Successfully got response from Foundry agent")
            
            # Try to parse JSON response
            response_text = response.output_text
            
            # If it's already structured, return it
            if isinstance(response_text, dict):
                return response_text
            
            # Try to extract JSON from the response text
            try:
                # Look for JSON in the response
                import re
                json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
                if json_match:
                    return json.loads(json_match.group())
                else:
                    # Create structured response from text
                    return {
                        "action": {
                            "recommendation": "ANALYSIS_COMPLETE",
                            "reasoning": response_text
                        },
                        "timestamp": datetime.now().isoformat()
                    }
            except:
                # Fallback to text response
                return {
                    "action": {
                        "recommendation": "ANALYSIS_COMPLETE", 
                        "reasoning": response_text
                    },
                    "timestamp": datetime.now().isoformat()
                }
                
        except Exception as e:
            logger.error(f"Error querying Foundry agent: {str(e)}")
            
            # Return fallback analysis
            return {
                "action": {
                    "recommendation": "ERROR",
                    "reasoning": f"Unable to connect to Foundry agent: {str(e)}"
                },
                "timestamp": datetime.now().isoformat()
            }

    def format_signal_message(self, analysis_data):
        """Format the analysis data into a readable Telegram message"""
        try:
            # Parse the JSON response if it's a string
            if isinstance(analysis_data, str):
                data = json.loads(analysis_data)
            else:
                data = analysis_data.get('response', analysis_data)
            
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")
            
            # Extract key information
            action = data.get('action', {})
            signals = data.get('signals', {})
            confluence = data.get('confluence', {})
            fear_greed = data.get('fearGreedAnalysis', {})
            levels = data.get('levels', {})
            
            # Create formatted message
            message = f"🤖 **Bitcoin Analysis Update**\n"
            message += f"⏰ {timestamp}\n\n"
            
            # Main recommendation
            recommendation = action.get('recommendation', 'N/A')
            if 'BUY' in recommendation:
                message += f"📈 **{recommendation}** 🚀\n"
            elif 'SELL' in recommendation:
                message += f"📉 **{recommendation}** 🔻\n"
            else:
                message += f"⏸️ **{recommendation}** ⚖️\n"
            
            # Fear & Greed
            fg_current = fear_greed.get('current', 'N/A')
            fg_class = fear_greed.get('classification', 'N/A')
            message += f"\n😱 Fear & Greed: {fg_current} ({fg_class})\n"
            
            # Confluence score
            bullish = confluence.get('bullishFactors', 0)
            bearish = confluence.get('bearishFactors', 0)
            confidence = confluence.get('confidence', 0)
            message += f"🎯 Confluence: {bullish} Bullish / {bearish} Bearish\n"
            message += f"💪 Confidence: {confidence}/10\n"
            
            # Key levels
            if levels:
                message += f"\n📊 **Key Levels:**\n"
                if levels.get('entry'):
                    message += f"🎯 Entry: ${levels['entry']}\n"
                if levels.get('stopLoss'):
                    message += f"🛑 Stop Loss: ${levels['stopLoss']}\n"
                if levels.get('target1'):
                    message += f"🎁 Target: ${levels['target1']}\n"
            
            # Reasoning
            reasoning = action.get('reasoning', '')
            if reasoning:
                message += f"\n💭 **Analysis:**\n{reasoning}\n"
            
            return message
            
        except Exception as e:
            logger.error(f"Error formatting message: {str(e)}")
            return f"🤖 Bitcoin analysis received but formatting failed. Raw data: {str(analysis_data)[:500]}..."

    async def send_signal_to_user(self, message):
        """Send trading signal to the authorized user"""
        try:
            await self.app.bot.send_message(
                chat_id=TELEGRAM_USER_ID,
                text=message,
                parse_mode='Markdown'
            )
            logger.info("Signal sent to user successfully")
        except Exception as e:
            logger.error(f"Error sending message to user: {str(e)}")

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        if update.effective_user.id != TELEGRAM_USER_ID:
            await update.message.reply_text("❌ Unauthorized access")
            return
            
        await update.message.reply_text(
            "🤖 Bitcoin Trading Bot Active\n\n"
            "Commands:\n"
            "/analyze - Get current market analysis\n\n"
            "You can also chat directly with the bot about Bitcoin markets!"
        )

    async def analyze_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /analyze command"""
        if update.effective_user.id != TELEGRAM_USER_ID:
            await update.message.reply_text("❌ Unauthorized access")
            return
            
        await update.message.reply_text("⏳ Running comprehensive Bitcoin analysis...\n\n🤖 Querying Foundry agent\n⚡ Estimated wait: 1-3 minutes\n📊 Processing multiple data sources\n\nAnalyzing Fear & Greed, seasonals, DXY, correlations...")
        
        analysis = await self.query_foundry_agent()
        if analysis:
            message = self.format_signal_message(analysis)
            await update.message.reply_text(message, parse_mode='Markdown')
        else:
            await update.message.reply_text("❌ Failed to get analysis from Foundry agent")

    async def monitor_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /monitor command"""
        if update.effective_user.id != TELEGRAM_USER_ID:
            await update.message.reply_text("❌ Unauthorized access")
            return
            
        self.monitoring = True
        await update.message.reply_text(f"📡 Automatic monitoring started! Checking every {CHECK_INTERVAL//60} minutes.")
        
        # Start monitoring loop
        asyncio.create_task(self.monitoring_loop())

    async def stop_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /stop command"""
        if update.effective_user.id != TELEGRAM_USER_ID:
            await update.message.reply_text("❌ Unauthorized access")
            return
            
        self.monitoring = False
        await update.message.reply_text("🛑 Automatic monitoring stopped")

    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /status command"""
        if update.effective_user.id != TELEGRAM_USER_ID:
            await update.message.reply_text("❌ Unauthorized access")
            return
            
        status = "🟢 Active" if self.monitoring else "🔴 Inactive"
        await update.message.reply_text(
            f"🤖 **Bot Status**\n"
            f"Monitoring: {status}\n"
            f"Check interval: {CHECK_INTERVAL//60} minutes\n"
            f"Last check: {datetime.now().strftime('%H:%M:%S')}"
        )

    async def monitoring_loop(self):
        """Main monitoring loop that checks for signals"""
        logger.info("Starting monitoring loop")
        
        while self.monitoring:
            try:
                analysis = await self.query_foundry_agent()
                if analysis:
                    # Check if this is a significant signal change
                    current_recommendation = self.extract_recommendation(analysis)
                    
                    if self.should_send_alert(current_recommendation):
                        message = self.format_signal_message(analysis)
                        await self.send_signal_to_user(f"🚨 **ALERT** 🚨\n\n{message}")
                        self.last_signal = current_recommendation
                
                await asyncio.sleep(CHECK_INTERVAL)
                
            except Exception as e:
                logger.error(f"Error in monitoring loop: {str(e)}")
                await asyncio.sleep(CHECK_INTERVAL)

    def extract_recommendation(self, analysis_data):
        """Extract recommendation from analysis data"""
        try:
            if isinstance(analysis_data, str):
                data = json.loads(analysis_data)
            else:
                data = analysis_data.get('response', analysis_data)
            
            return data.get('action', {}).get('recommendation', 'HOLD')
        except:
            return 'HOLD'

    def should_send_alert(self, current_recommendation):
        """Determine if we should send an alert based on signal change"""
        # Send alert if:
        # 1. First time running
        # 2. Recommendation changed
        # 3. Strong buy/sell signals
        if self.last_signal is None:
            return True
        
        if current_recommendation != self.last_signal:
            return True
            
        if 'Strong' in current_recommendation:
            return True
            
        return False

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle regular text messages and send to Foundry agent"""
        if update.effective_user.id != TELEGRAM_USER_ID:
            await update.message.reply_text("❌ Unauthorized access")
            return
        
        user_message = update.message.text
        await update.message.reply_text("⏳ Analyzing your request...\n\n🤖 Connecting to Foundry agent\n⚡ Estimated wait: 1-3 minutes\n📊 Running comprehensive analysis\n\nPlease wait, quality analysis takes time...")
        
        # Query Foundry agent with user's message
        try:
            myEndpoint = "https://financecompanion-resource.services.ai.azure.com/api/projects/financecompanion"
            
            project_client = AIProjectClient(
                endpoint=myEndpoint,
                credential=DefaultAzureCredential(),
            )
            
            agent = project_client.agents.get(agent_name="FinanceCompanion")
            openai_client = project_client.get_openai_client()
            
            # Add retry logic for rate limits
            import time
            max_retries = 3
            retry_delay = 60
            
            for attempt in range(max_retries):
                try:
                    response = openai_client.responses.create(
                        input=[{"role": "user", "content": user_message}],
                        extra_body={"agent": {"name": agent.name, "type": "agent_reference"}},
                    )
                    break
                except Exception as e:
                    if "429" in str(e) and attempt < max_retries - 1:
                        logger.info(f"Rate limit hit, waiting {retry_delay} seconds before retry {attempt + 1}")
                        time.sleep(retry_delay)
                        continue
                    else:
                        raise e
            
            # Send response back to user
            agent_response = response.output_text
            # Split long messages if needed
            if len(agent_response) > 4000:
                chunks = [agent_response[i:i+4000] for i in range(0, len(agent_response), 4000)]
                for chunk in chunks:
                    await update.message.reply_text(chunk)
            else:
                await update.message.reply_text(agent_response)
                
        except Exception as e:
            logger.error(f"Error in message handler: {str(e)}")
            await update.message.reply_text(f"❌ Error: {str(e)}")

    def setup_handlers(self):
        """Setup command handlers"""
        from telegram.ext import MessageHandler, filters
        
        self.app.add_handler(CommandHandler("start", self.start_command))
        self.app.add_handler(CommandHandler("analyze", self.analyze_command))
        self.app.add_handler(CommandHandler("monitor", self.monitor_command))
        self.app.add_handler(CommandHandler("stop", self.stop_command))
        self.app.add_handler(CommandHandler("status", self.status_command))
        # Add handler for regular messages (not commands)
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))

    async def run(self):
        """Run the bot"""
        logger.info("Starting Bitcoin Trading Bot...")
        self.setup_handlers()
        
        # Send startup message to user
        try:
            await self.app.bot.send_message(
                chat_id=TELEGRAM_USER_ID,
                text="🤖 Bitcoin Trading Bot is online!\nUse /start to see available commands."
            )
        except Exception as e:
            logger.error(f"Failed to send startup message: {str(e)}")
        
        # Start the bot
        await self.app.initialize()
        await self.app.start()
        await self.app.updater.start_polling()
        
        logger.info("Bot is running...")
        
        # Keep the bot running
        try:
            await asyncio.Future()  # Run forever
        except KeyboardInterrupt:
            logger.info("Shutting down bot...")
        finally:
            await self.app.updater.stop()
            await self.app.stop()
            await self.app.shutdown()

if __name__ == "__main__":
    bot = BitcoinTradingBot()
    asyncio.run(bot.run())