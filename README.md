# Tennis AceCast 🎾

AI-powered tennis match prediction system using Elo ratings and Amazon Bedrock for intelligent analysis.

## Features

- **Player Profiles**: Detailed player statistics with Elo ratings across different surfaces
- **Match Prediction**: AI-powered match analysis with win probabilities and head-to-head records
- **Tournament Simulation**: Monte Carlo simulation for tournament brackets with upset risk analysis
- **Surface-Specific Analysis**: Separate ratings for hard, clay, grass, and indoor hard courts
- **Interactive Web UI**: Streamlit-based interface for easy interaction
- **CLI Tool**: Command-line interface for batch processing and automation

## Quick Start

### Prerequisites

- Python 3.8+
- AWS account with Bedrock access
- ATP match data in CSV format

### Installation

```bash
git clone https://github.com/freestyledjokic/tennis_acecast.git
cd tennis_acecast
pip install -r requirements.txt
```

### Setup

1. Configure AWS credentials:
```bash
aws configure
```

2. Add ATP match data to `data/` directory:
```
data/
├── atp_matches_2023.csv
└── atp_matches_2024.csv
```

3. Create system prompt:
```bash
mkdir prompts
# Add your AI system prompt to prompts/system.txt
```

## Usage

### Web Interface

```bash
streamlit run streamlit_app.py
```

Navigate to `http://localhost:8501` to access:
- **Player Profiles**: View detailed player statistics and Elo ratings
- **Match Prediction**: Get AI analysis for head-to-head matchups
- **Tournament Simulator**: Run Monte Carlo simulations for tournament brackets

### Command Line

**Match Prediction:**
```bash
python app.py match \
  --playerA "Jannik Sinner" \
  --playerB "Carlos Alcaraz" \
  --surface hard \
  --csv data/atp_matches_2024.csv \
  --model-id anthropic.claude-3-sonnet-20240229-v1:0
```

**Tournament Analysis:**
```bash
python app.py tournament \
  --players "Jannik Sinner,Carlos Alcaraz,Novak Djokovic,Daniil Medvedev" \
  --surface hard \
  --csv data/atp_matches_2024.csv \
  --model-id anthropic.claude-3-sonnet-20240229-v1:0 \
  --simulate 1000
```

## Project Structure

```
tennis_acecast/
├── streamlit_app.py    # Main Streamlit application
├── app.py              # CLI application
├── elo.py              # Core Elo rating system
├── elo_system.py       # Streamlit-friendly Elo wrapper
├── ui/                 # UI modules
│   ├── profiles.py     # Player profile interface
│   ├── match.py        # Match prediction interface
│   └── tournament.py   # Tournament simulation interface
├── data/               # ATP match data (CSV files)
├── prompts/            # AI system prompts
└── requirements.txt    # Python dependencies
```

## Core Components

### Elo Rating System
- Surface-specific ratings (hard, clay, grass, indoor hard)
- Recency weighting for recent matches
- Head-to-head tracking
- Match history analysis

### AI Integration
- Amazon Bedrock integration for match analysis
- Contextual prompts with statistical data
- Intelligent tournament briefings
- Upset risk assessment

### Data Processing
- ATP CSV format support
- Automatic player name normalization
- Surface type standardization
- Historical match ingestion

## Requirements

```
streamlit>=1.28.0
boto3>=1.34.0
pandas>=2.0.0
```

## Configuration

### AWS Bedrock Models
Supported models:
- `anthropic.claude-3-sonnet-20240229-v1:0`
- `anthropic.claude-3-haiku-20240307-v1:0`

### Surface Types
- `hard`: Hard courts
- `clay`: Clay courts  
- `grass`: Grass courts
- `indoor_hard`: Indoor hard courts

## Data Format

ATP CSV files should contain columns:
- `tourney_date`: Tournament date (YYYYMMDD)
- `surface`: Court surface
- `winner_name`: Winner name
- `loser_name`: Loser name
- `score`: Match score
- `best_of`: Best of format (3 or 5)
- `round`: Tournament round


## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## Acknowledgments

- ATP for match data
- Amazon Web Services for Bedrock AI capabilities
- Streamlit for the web interface framework
