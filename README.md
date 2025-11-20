# Bitcoin Trading Bot

🤖 Advanced Bitcoin trading bot powered by Microsoft Azure AI Foundry with comprehensive market analysis.

## Features

- **Multi-Factor Analysis**: Fear & Greed Index, seasonal patterns, USD Index (DXY), market correlations
- **Real-Time Data**: Live market sentiment and institutional flow analysis
- **Interactive Chat**: Direct conversation with AI agent for market questions
- **Professional Signals**: Buy/sell recommendations with confidence scoring
- **Azure AI Integration**: Powered by Microsoft Foundry for institutional-grade analysis

## Setup

### Prerequisites

- Python 3.10+
- Microsoft Azure account with AI Foundry access
- Telegram bot token
- Azure CLI

### Installation

1. **Clone the repository**
```bash
git clone https://github.com/yourusername/bitcoin-trading-bot.git
cd bitcoin-trading-bot
```

2. **Install dependencies**
```bash
pip install -r requirements.txt
```

3. **Install Azure CLI and login**
```bash
curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash
az login
```

4. **Configure environment variables**
```bash
cp .env.example .env
# Edit .env with your credentials
```

5. **Run the bot**
```bash
python3 bitcoin_trading_bot.py
```

## Configuration

Create a `.env` file with:

```env
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_USER_ID=your_telegram_user_id
FOUNDRY_ENDPOINT=your_azure_ai_endpoint
FOUNDRY_API_KEY=your_azure_api_key
CHECK_INTERVAL=300
```

## Usage

### Commands

- `/start` - Initialize the bot
- `/analyze` - Get comprehensive Bitcoin market analysis

### Direct Chat

Send any message to chat directly with the AI agent about Bitcoin markets.

## Architecture

- **Telegram Bot**: User interface and command handling
- **Azure AI Foundry**: Advanced market analysis engine
- **Real-time APIs**: Fear & Greed Index, market data feeds
- **Multi-factor Analysis**: Confluence-based signal generation

## Analysis Components

1. **Sentiment Analysis**: Fear & Greed Index with contrarian signals
2. **Seasonal Patterns**: Historical monthly/quarterly performance
3. **Macro Environment**: USD Dollar Index impact analysis
4. **Market Correlations**: NASDAQ, S&P500, Gold, VIX relationships
5. **Technical Analysis**: Support/resistance levels with confluence
6. **Institutional Flows**: ETF movements and whale activity

## Example Output

```
🤖 Bitcoin Analysis Update
⏰ 2025-11-20 13:21:56 UTC

📈 BUY (with moderate conviction) 🚀

😱 Fear & Greed: 15 (Extreme Fear)
🎯 Confluence: 5/7 Bullish / 2/7 Bearish
💪 Confidence: 8/10

📊 Key Levels:
🎯 Entry: $91,500–93,000
🛑 Stop Loss: Below $88,800
🎁 Target: $104,000

💭 Analysis:
Extreme fear readings, historical November bullish bias, 
strong whale accumulation, support zone confirmed.
```

## License

MIT License - See LICENSE file for details.

## Disclaimer

This bot is for educational and informational purposes only. Not financial advice. Trade at your own risk.

## Contributing

Pull requests welcome! Please read contributing guidelines first.