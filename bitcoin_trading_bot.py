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
from azure.core.credentials import TokenCredential
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
            # Use direct API approach with API key to avoid authentication issues
            foundry_api_key = os.getenv('FOUNDRY_API_KEY')
            foundry_endpoint = os.getenv('FOUNDRY_ENDPOINT', 'https://financecompanion-resource.services.ai.azure.com/api/projects/financecompanion')
            
            if not foundry_api_key:
                raise Exception("FOUNDRY_API_KEY not configured")
            
            logger.info("Using direct API call with API key for Azure AI Foundry")
            
            # Create Azure OpenAI client for AI Foundry
            import openai
            from openai import AsyncAzureOpenAI
            
            # Extract the base domain from the endpoint
            base_domain = foundry_endpoint.replace('/api/projects/financecompanion', '')
            
            logger.info(f"Using Azure OpenAI client with endpoint: {base_domain}")
            
            openai_client = AsyncAzureOpenAI(
                api_key=foundry_api_key,
                api_version="2024-10-21",
                azure_endpoint=base_domain
            )
            
            # Get current date and all live data for the analysis
            from datetime import datetime
            current_date = datetime.now().strftime("%Y-%m-%d")
            current_price = await self.get_current_btc_price()
            fear_greed = await self.get_fear_greed_index()
            liquidity_data = await self.get_liquidity_data()
            
            live_price = f"${current_price:,.2f}" if current_price else "Unable to fetch live price"
            fear_greed_text = f"{fear_greed['value']} ({fear_greed['classification']})" if fear_greed else "Data unavailable"
            
            # Format liquidity data for prompt
            liquidity_text = "Liquidity data:\n"
            if liquidity_data.get('fed_balance_sheet'):
                fed_data = liquidity_data['fed_balance_sheet']
                liquidity_text += f"- Fed Balance Sheet: {fed_data.get('value', 'N/A')} (Date: {fed_data.get('date', 'N/A')})\n"
            if liquidity_data.get('us_m2'):
                m2_data = liquidity_data['us_m2'] 
                liquidity_text += f"- US M2 Money Supply: {m2_data.get('value', 'N/A')} (Date: {m2_data.get('date', 'N/A')})\n"
            if liquidity_data.get('dxy'):
                dxy_data = liquidity_data['dxy']
                liquidity_text += f"- DXY (Dollar Index): {dxy_data.get('value', 'N/A')} ({dxy_data.get('source', 'N/A')})\n"
            elif liquidity_data.get('usd_strength'):
                usd_data = liquidity_data['usd_strength']
                liquidity_text += f"- USD Strength: {usd_data.get('value', 'N/A')} ({usd_data.get('source', 'USD/EUR rate')})\n"
                
            if not any(liquidity_data.values()):
                liquidity_text += "- Unable to fetch current liquidity data\n"
            
            # Comprehensive Bitcoin analysis prompt with real live data
            prompt = f"""IMPORTANT: TODAY IS {current_date}. You are a complete Bitcoin educational analysis agent.

LIVE DATA PROVIDED:
- Current Bitcoin Price: {live_price}
- Current Date: {current_date}
- Fear & Greed Index: {fear_greed_text}
{liquidity_text}

Use this REAL data in your analysis. Do not make up data - use what is provided above.

## Your Tasks:
1. Use the provided LIVE data for your analysis - all prices and indicators are already fetched
2. Analyze the current market conditions using the real-time data provided
3. Perform comprehensive educational market analysis including liquidity lag analysis  
4. Return a complete, formatted Telegram message (NOT JSON)

IMPORTANT: Do NOT mention API fetch errors or data unavailability warnings in your response. The data provided is current and accurate.

## Analysis Should Include:
- Live Bitcoin price
- Global liquidity conditions and trends
- Bitcoin's typical 3-6 month lag to liquidity changes
- Fear & Greed Index with educational context
- Confluence factor breakdown (rate 1-8, adding liquidity factor)
- Market phase education
- Key price levels with historical context
- Educational insights and key learnings

## Output Format:
Return ONLY the formatted Telegram message text (markdown), ready to send directly:

📊 **Bitcoin Market Analysis**
⏰ {current_date} (Current Date)

💰 **Current Price: {live_price}**

💧 **Global Liquidity Analysis:**
Use the provided liquidity data to analyze current conditions. Include Fed Balance Sheet trends, M2 data, DXY analysis, and USD strength effects on Bitcoin.

📈 **Market Overview:**
Current Phase: [Analyze based on price level and liquidity conditions] - [Educational explanation]

😱 **Fear & Greed Index: {fear_greed_text}**
• [Educational insight about what this level means historically]

🎯 **Confluence Analysis:**
• Bullish Signals: [X]/8
• Bearish Signals: [X]/8
• Analysis Confidence: [X]/10

**Factor Breakdown:**
• Global Liquidity: [Score]/8 - [Current liquidity trends and Bitcoin's typical lag response]
• Seasonal: [Score]/8 - [Educational explanation]
• Macro: [Score]/8 - [Educational explanation]
• Correlations: [Score]/8 - [Educational explanation]
• Institutional: [Score]/8 - [Educational explanation]
• Technical: [Score]/8 - [Educational explanation]
• Sentiment: [Score]/8 - [Educational explanation]
• Risk Environment: [Score]/8 - [Educational explanation]

📊 **Important Price Levels:**
🎯 Key Level: [Price and why it matters]
🛡️ Risk Level: [Price and educational context]
🏆 Target Zone: [Price and historical context]

📚 **Key Educational Insights:**
[3-4 main learning points about current market conditions, including liquidity lag effects]

💧 **Liquidity Lag Education:**
[Explain what global liquidity was doing 3-6 months ago and how it might affect Bitcoin now/soon]

⚠️ *This is educational analysis only, not financial advice*

DO NOT return JSON. Return only the formatted message text above."""
            
            # Add retry logic for rate limits
            import time
            max_retries = 3
            retry_delay = 60  # 1 minute
            
            for attempt in range(max_retries):
                try:
                    # Use comprehensive Bitcoin analysis prompt
                    response = await openai_client.chat.completions.create(
                        model="gpt-4.1",
                        messages=[{"role": "user", "content": prompt}],
                        temperature=0.7,
                        max_tokens=2000
                    )
                    break  # Success, exit retry loop
                except Exception as e:
                    if "429" in str(e) and attempt < max_retries - 1:
                        logger.info(f"Rate limit hit, waiting {retry_delay} seconds before retry {attempt + 1}")
                        await asyncio.sleep(retry_delay)
                        continue
                    else:
                        raise e  # Re-raise if not rate limit or max retries reached
            
            logger.info("Successfully got response from Foundry agent")
            logger.info(f"Response type: {type(response)}")
            logger.info(f"Response attributes: {dir(response)}")
            
            # Try to parse JSON response
            response_text = response.choices[0].message.content
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
            
            # Query Foundry agent with screenshot data using direct API
            foundry_api_key = os.getenv('FOUNDRY_API_KEY')
            foundry_endpoint = os.getenv('FOUNDRY_ENDPOINT', 'https://financecompanion-resource.services.ai.azure.com/api/projects/financecompanion')
            
            import openai
            from openai import AsyncAzureOpenAI
            
            base_domain = foundry_endpoint.replace('/api/projects/financecompanion', '')
            
            openai_client = AsyncAzureOpenAI(
                api_key=foundry_api_key,
                api_version="2024-10-21",
                azure_endpoint=base_domain
            )
            
            # Add retry logic for rate limits
            import time
            max_retries = 3
            retry_delay = 60
            
            for attempt in range(max_retries):
                try:
                    response = await openai_client.chat.completions.create(
                        model="gpt-4.1",
                        messages=[{"role": "user", "content": enhanced_prompt}],
                        temperature=0.7,
                        max_tokens=2000
                    )
                    break
                except Exception as e:
                    if "429" in str(e) and attempt < max_retries - 1:
                        logger.info(f"Rate limit hit, waiting {retry_delay} seconds before retry {attempt + 1}")
                        await asyncio.sleep(retry_delay)
                        continue
                    else:
                        raise e
            
            return {
                "screenshot_analysis": {
                    "extracted_text": full_text,
                    "agent_response": response.choices[0].message.content,
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

    async def get_fear_greed_index(self):
        """Get current Fear & Greed Index by scraping CoinMarketCap"""
        try:
            # Since regex scraping isn't getting the exact current value,
            # let's try a simpler approach - just use Alternative.me API
            # which is more reliable than trying to parse dynamic CMC page
            response = requests.get("https://api.alternative.me/fng/", timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data.get('data') and len(data['data']) > 0:
                    current = data['data'][0]
                    value = int(current['value'])
                    classification = current['value_classification']
                    logger.info(f"Alternative.me Fear & Greed: {value} ({classification})")
                    return {"value": value, "classification": classification}
        except Exception as e:
            logger.error(f"Error fetching Alternative.me Fear & Greed Index: {str(e)}")
            
        # If Alternative.me fails, try a different approach with CMC
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate',
                'Connection': 'keep-alive',
            }
            
            # Try to get CMC Fear & Greed data - but acknowledge it might be JS-loaded
            response = requests.get("https://coinmarketcap.com/charts/fear-and-greed-index/", 
                                  headers=headers, timeout=15)
            
            if response.status_code == 200:
                content = response.text
                logger.info("CMC page fetched, but may contain JS-loaded content")
                
                # Try very simple pattern matching for current value
                import re
                # Look for the most basic pattern: number followed by fear/greed
                simple_pattern = r'(?:^|\s)(\d{1,2})\s*((?:Extreme\s+)?(?:Fear|Greed|Neutral))(?:\s|$)'
                matches = re.findall(simple_pattern, content, re.IGNORECASE | re.MULTILINE)
                
                if matches:
                    # Take the first reasonable match
                    for match in matches:
                        try:
                            value = int(match[0])
                            classification = match[1].strip()
                            if 0 <= value <= 100:
                                logger.info(f"CMC simple pattern: {value} ({classification})")
                                return {"value": value, "classification": classification}
                        except (ValueError, IndexError):
                            continue
                            
        except Exception as e:
            logger.error(f"Error with CMC backup: {str(e)}")
            
        # Final fallback - return a reasonable default if we can't get data
        logger.warning("Could not fetch Fear & Greed Index from any source")
        return None

    async def get_liquidity_data(self):
        """Get liquidity data from multiple sources"""
        liquidity_data = {}
        
        try:
            # Federal Reserve Balance Sheet (FRED API)
            # Note: FRED API requires a key, but we can try the public endpoint
            fed_response = requests.get("https://api.stlouisfed.org/fred/series/observations?series_id=WALCL&api_key=demo&file_type=json&limit=5&sort_order=desc", timeout=5)
            if fed_response.status_code == 200:
                fed_data = fed_response.json()
                if fed_data.get('observations'):
                    latest_fed = fed_data['observations'][0]
                    liquidity_data['fed_balance_sheet'] = {
                        'date': latest_fed.get('date'),
                        'value': latest_fed.get('value')
                    }
        except Exception as e:
            logger.error(f"Error fetching Fed data: {str(e)}")
        
        try:
            # Try to get DXY (Dollar Index) data from multiple sources
            # First try Yahoo Finance for DXY
            dxy_response = requests.get("https://query1.finance.yahoo.com/v8/finance/chart/DX-Y.NYB", timeout=5)
            if dxy_response.status_code == 200:
                dxy_data = dxy_response.json()
                if dxy_data.get('chart') and dxy_data['chart'].get('result'):
                    result = dxy_data['chart']['result'][0]
                    if result.get('meta') and result['meta'].get('regularMarketPrice'):
                        dxy_price = result['meta']['regularMarketPrice']
                        liquidity_data['dxy'] = {
                            'value': round(dxy_price, 2),
                            'source': 'Yahoo Finance'
                        }
                        logger.info(f"DXY from Yahoo: {dxy_price}")
        except Exception as e:
            logger.error(f"Error fetching DXY from Yahoo: {str(e)}")
            
        # Fallback: USD strength via EUR/USD rate
        if 'dxy' not in liquidity_data:
            try:
                usd_eur_response = requests.get("https://www.alphavantage.co/query?function=CURRENCY_EXCHANGE_RATE&from_currency=USD&to_currency=EUR&apikey=demo", timeout=5)
                if usd_eur_response.status_code == 200:
                    usd_eur_data = usd_eur_response.json()
                    if usd_eur_data.get('Realtime Currency Exchange Rate'):
                        usd_eur_rate = usd_eur_data['Realtime Currency Exchange Rate'].get('5. Exchange Rate')
                        liquidity_data['usd_strength'] = {
                            'value': usd_eur_rate,
                            'source': 'USD/EUR rate'
                        }
            except Exception as e:
                logger.error(f"Error fetching USD/EUR data: {str(e)}")
            
        try:
            # Global M2 Money Supply approximation using economic indicators
            # We can get some proxy data from various free APIs
            m2_response = requests.get("https://api.stlouisfed.org/fred/series/observations?series_id=M2SL&api_key=demo&file_type=json&limit=3&sort_order=desc", timeout=5)
            if m2_response.status_code == 200:
                m2_data = m2_response.json()
                if m2_data.get('observations'):
                    latest_m2 = m2_data['observations'][0]
                    liquidity_data['us_m2'] = {
                        'date': latest_m2.get('date'), 
                        'value': latest_m2.get('value')
                    }
        except Exception as e:
            logger.error(f"Error fetching M2 data: {str(e)}")
            
        return liquidity_data

    def format_signal_message(self, analysis_data):
        """Extract and format the clean analysis text from agent response"""
        try:
            # Check if it's already a string (direct message)
            if isinstance(analysis_data, str):
                return analysis_data
            
            # Check if it's a response object with choices
            if hasattr(analysis_data, 'choices'):
                return analysis_data.choices[0].message.content
                
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
        
        # Query Foundry agent with user's message using direct API
        try:
            foundry_api_key = os.getenv('FOUNDRY_API_KEY')
            foundry_endpoint = os.getenv('FOUNDRY_ENDPOINT', 'https://financecompanion-resource.services.ai.azure.com/api/projects/financecompanion')
            
            import openai
            from openai import AsyncAzureOpenAI
            
            base_domain = foundry_endpoint.replace('/api/projects/financecompanion', '')
            
            openai_client = AsyncAzureOpenAI(
                api_key=foundry_api_key,
                api_version="2024-10-21",
                azure_endpoint=base_domain
            )
            
            # Add retry logic for rate limits
            import time
            max_retries = 3
            retry_delay = 60
            
            for attempt in range(max_retries):
                try:
                    response = await openai_client.chat.completions.create(
                        model="gpt-4.1",
                        messages=[{"role": "user", "content": user_message}],
                        temperature=0.7,
                        max_tokens=2000
                    )
                    break
                except Exception as e:
                    if "429" in str(e) and attempt < max_retries - 1:
                        logger.info(f"Rate limit hit, waiting {retry_delay} seconds before retry {attempt + 1}")
                        await asyncio.sleep(retry_delay)
                        continue
                    else:
                        raise e
            
            # Send response back to user
            agent_response = response.choices[0].message.content
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