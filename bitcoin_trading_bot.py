#!/usr/bin/env python3
import os
import json
import asyncio
import logging
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters
import requests
from dotenv import load_dotenv
from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient
from azure.core.credentials import AzureKeyCredential
from azure.cognitiveservices.vision.computervision import ComputerVisionClient
from azure.cognitiveservices.vision.computervision.models import OperationStatusCodes
from msrest.authentication import CognitiveServicesCredentials
from PIL import Image
import io

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

# Computer Vision configuration
VISION_ENDPOINT = os.getenv('VISION_ENDPOINT')
VISION_API_KEY = os.getenv('VISION_API_KEY')

class BitcoinTradingBot:
    def __init__(self):
        self.app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
        self.last_signal = None
        self.monitoring = False
        
        # Initialize Computer Vision client
        self.cv_client = ComputerVisionClient(
            VISION_ENDPOINT,
            CognitiveServicesCredentials(VISION_API_KEY)
        )
        
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
            
            # Get current Bitcoin price locally (since Foundry can't access live APIs reliably)
            current_price = await self.get_current_btc_price()
            price_info = f"Current Bitcoin Price: ${current_price:,.2f}" if current_price else "Unable to fetch current price"
            
            # Enhanced prompt with live price data
            prompt = f"""Provide a complete Bitcoin educational market analysis using this LIVE price data:

{price_info}

Use this exact price in your analysis. Create a comprehensive educational analysis including global liquidity, market correlations, seasonal patterns, and confluence factors.

IMPORTANT FORMATTING REQUIREMENTS:
- Use PLAIN TEXT format only - no markdown formatting like ** or __ 
- Use simple emojis and clear spacing for readability
- Do NOT include Fear & Greed Index data unless you have current accurate data
- Focus on factual price action, liquidity analysis, and educational insights
- Include global liquidity analysis with 3-6 month lag effects

Return a clean, readable message for Telegram without any markdown formatting.

Focus on education, not trading advice. Include appropriate educational disclaimers."""
            
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
            logger.info(f"Response type: {type(response)}")
            logger.info(f"Response attributes: {dir(response)}")
            
            # Try to parse JSON response
            response_text = response.output_text
            logger.info(f"Response text preview: {response_text[:200] if response_text else 'None'}")
            
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

    async def analyze_screenshot(self, image_stream):
        """Analyze TradingView screenshot using Computer Vision OCR"""
        try:
            logger.info("Starting screenshot analysis with Computer Vision")
            
            # Use OCR to extract text from image
            ocr_result = self.cv_client.read_in_stream(image_stream, raw=True)
            operation_id = ocr_result.headers["Operation-Location"].split("/")[-1]
            
            # Wait for OCR to complete
            import time
            while True:
                result = self.cv_client.get_read_result(operation_id)
                if result.status not in [OperationStatusCodes.running, OperationStatusCodes.not_started]:
                    break
                time.sleep(1)
            
            # Extract text from OCR results
            extracted_text = []
            if result.status == OperationStatusCodes.succeeded:
                for page in result.analyze_result.read_results:
                    for line in page.lines:
                        extracted_text.append(line.text)
            
            # Combine all text
            full_text = " ".join(extracted_text)
            logger.info(f"Extracted text from screenshot: {full_text[:200]}...")
            
            # Send extracted text to Foundry agent for analysis
            enhanced_prompt = f"""
            Analyze this TradingView screenshot data and provide trading insights:

            EXTRACTED TEXT FROM SCREENSHOT:
            {full_text}

            Please identify:
            1. Current price levels and support/resistance
            2. Technical indicators (RSI, MACD, volume, etc.)
            3. Chart patterns or trends
            4. Key trading levels
            5. Market sentiment signals
            6. Trading recommendations based on screenshot data

            Combine this screenshot analysis with current market conditions to provide comprehensive trading guidance.
            """
            
            # Query Foundry agent with screenshot data
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
                        input=[{"role": "user", "content": enhanced_prompt}],
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
            
            return {
                "screenshot_analysis": {
                    "extracted_text": full_text,
                    "agent_response": response.output_text,
                    "timestamp": datetime.now().isoformat()
                }
            }
            
        except Exception as e:
            logger.error(f"Error analyzing screenshot: {str(e)}")
            return {
                "screenshot_analysis": {
                    "error": str(e),
                    "extracted_text": full_text if 'full_text' in locals() else "Failed to extract text",
                    "timestamp": datetime.now().isoformat()
                }
            }

    async def get_current_btc_price(self):
        """Get current Bitcoin price from multiple sources"""
        try:
            # Try CoinGecko first
            response = requests.get("https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd", timeout=5)
            if response.status_code == 200:
                data = response.json()
                return float(data['bitcoin']['usd'])
        except:
            pass
            
        try:
            # Fallback to Coinbase
            response = requests.get("https://api.coinbase.com/v2/exchange-rates?currency=BTC", timeout=5)
            if response.status_code == 200:
                data = response.json()
                return float(data['data']['rates']['USD'])
        except:
            pass
            
        return None

    def format_signal_message(self, analysis_data):
        """Extract and format the clean analysis text from agent response"""
        try:
            # Check if it's already a string (direct message)
            if isinstance(analysis_data, str):
                return analysis_data
            
            # Check if it's a response object with output_text
            if hasattr(analysis_data, 'output_text'):
                return analysis_data.output_text
                
            # If it's a dict, look for the reasoning text in the nested structure
            if isinstance(analysis_data, dict):
                # Try to extract the clean analysis from the nested structure
                if 'action' in analysis_data and 'reasoning' in analysis_data['action']:
                    reasoning_text = analysis_data['action']['reasoning']
                    # Clean up formatting and improve readability
                    cleaned_text = reasoning_text.replace('\\n', '\n').replace('  ', ' ')
                    # Remove all markdown formatting
                    cleaned_text = cleaned_text.replace('**', '').replace('*', '').replace('__', '').replace('_', '')
                    # Clean up extra spaces and improve formatting
                    cleaned_text = '\n'.join(line.strip() for line in cleaned_text.split('\n') if line.strip())
                    return cleaned_text
                elif 'output_text' in analysis_data:
                    return analysis_data['output_text']
            
            # If we get here, something unexpected happened
            logger.warning(f"Unexpected analysis_data format: {type(analysis_data)}")
            return f"📊 **Bitcoin Analysis**\n⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}\n\n❌ Unable to parse agent response format"
            
        except Exception as e:
            logger.error(f"Error in format_signal_message: {str(e)}")
            return f"📊 **Bitcoin Analysis Error**\n⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}\n\n❌ Error processing analysis from agent: {str(e)}"

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
            "Features:\n"
            "📷 Send TradingView screenshots for analysis\n"
            "💬 Chat directly about Bitcoin markets\n"
            "📊 AI-powered chart pattern recognition"
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
            
            # Split message if too long (Telegram limit is 4096 chars)
            max_length = 4000  # Leave some buffer
            if len(message) > max_length:
                # Split into chunks
                chunks = []
                for i in range(0, len(message), max_length):
                    chunks.append(message[i:i + max_length])
                
                # Send each chunk
                for i, chunk in enumerate(chunks):
                    try:
                        if i == 0:
                            await update.message.reply_text(f"📊 Bitcoin Analysis (Part {i+1}/{len(chunks)})\n\n{chunk}")
                        else:
                            await update.message.reply_text(f"Part {i+1}/{len(chunks)}\n\n{chunk}")
                    except Exception as e:
                        logger.warning(f"Failed to send chunk {i+1}: {e}")
                        # Send as plain text without formatting
                        clean_chunk = chunk.replace("**", "").replace("*", "").replace("__", "").replace("_", "")
                        await update.message.reply_text(clean_chunk)
            else:
                # Message is short enough, send normally
                try:
                    await update.message.reply_text(message)
                except Exception as e:
                    logger.warning(f"Failed to send message: {e}")
                    # Strip markdown and send as plain text
                    plain_message = message.replace("**", "").replace("*", "").replace("__", "").replace("_", "")
                    await update.message.reply_text(plain_message)
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

    async def handle_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle screenshot uploads for analysis"""
        if update.effective_user.id != TELEGRAM_USER_ID:
            await update.message.reply_text("❌ Unauthorized access")
            return
            
        await update.message.reply_text("📷 Screenshot received! Analyzing TradingView data...\n\n🔍 Extracting text with OCR\n🤖 Sending to AI agent for analysis\n⚡ Estimated wait: 2-4 minutes\n\nAnalyzing chart patterns, indicators, and price levels...")
        
        try:
            # Get the largest photo size
            photo = update.message.photo[-1]
            photo_file = await photo.get_file()
            
            # Download photo to memory
            photo_bytes = await photo_file.download_as_bytearray()
            image_stream = io.BytesIO(photo_bytes)
            
            # Analyze screenshot
            analysis = await self.analyze_screenshot(image_stream)
            
            # Format and send response
            if "error" in analysis.get("screenshot_analysis", {}):
                await update.message.reply_text(f"❌ Analysis failed: {analysis['screenshot_analysis']['error']}")
            else:
                response_text = analysis["screenshot_analysis"]["agent_response"]
                extracted_text = analysis["screenshot_analysis"]["extracted_text"]
                
                # Format response
                message = f"📊 **TradingView Screenshot Analysis**\n\n"
                message += f"🔍 **Extracted Data:**\n{extracted_text[:300]}...\n\n" if extracted_text else ""
                message += f"🤖 **AI Analysis:**\n{response_text}"
                
                # Split long messages
                if len(message) > 4000:
                    chunks = [message[i:i+4000] for i in range(0, len(message), 4000)]
                    for chunk in chunks:
                        await update.message.reply_text(chunk)
                else:
                    await update.message.reply_text(message)
                    
        except Exception as e:
            logger.error(f"Error handling photo: {str(e)}")
            await update.message.reply_text(f"❌ Error processing screenshot: {str(e)}")

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
        self.app.add_handler(CommandHandler("start", self.start_command))
        self.app.add_handler(CommandHandler("analyze", self.analyze_command))
        self.app.add_handler(CommandHandler("monitor", self.monitor_command))
        self.app.add_handler(CommandHandler("stop", self.stop_command))
        self.app.add_handler(CommandHandler("status", self.status_command))
        
        # Add handler for photo uploads (screenshots)
        self.app.add_handler(MessageHandler(filters.PHOTO, self.handle_photo))
        
        # Add handler for regular text messages (not commands)
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