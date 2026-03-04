# Enterprise Voice-Based AI Gateway

A production-ready voice AI system for enterprise customer operations that integrates IVR, intelligent routing, and human agent management.

## 🎯 Features

✅ **Voice Intelligence**
- Speech-to-text using OpenAI Whisper
- AI-powered conversational responses (GPT-4)
- Text-to-speech for natural interactions
- Sentiment analysis of customer calls

✅ **Smart Routing**
- Intent classification (billing, technical, sales, logistics, escalation)
- Context-aware transfers without repeat explanations
- Automated logistics query handling
- Mid-call transfer detection

✅ **Call Management**
- Real-time call monitoring dashboard
- AI agent profiles and assignments
- Complete conversation transcripts
- Sentiment tracking and call summaries

✅ **Enterprise Features**
- Twilio integration for inbound/outbound calls
- Audit logging for compliance
- Analytics and performance metrics
- WebSocket live updates
- RESTful admin API

---

## 🚀 Quick Start

### Prerequisites
- Python 3.9+
- Twilio Account ([Sign up here](https://www.twilio.com))
- OpenAI API Key ([Get here](https://platform.openai.com/api-keys))
- FFmpeg (for audio processing)

### Installation

1. **Clone / Extract the project**
```bash
cd AI-Voice-Agent
```

2. **Create virtual environment**
```bash
python -m venv venv
venv\Scripts\activate  # Windows
# or
source venv/bin/activate  # Linux/Mac
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Configure environment**
```bash
cp .env.example .env
# Edit .env with your credentials:
# - TWILIO_ACCOUNT_SID
# - TWILIO_AUTH_TOKEN
# - TWILIO_PHONE_NUMBER
# - OPENAI_API_KEY
# - BASE_URL (for webhook callbacks)
```

5. **Initialize database & seed demo data**
```bash
python seed_demo_data.py
```

6. **Start the server**
```bash
python main.py
```

The system will be available at `http://localhost:8000`

---

## 📋 Configuration

### Environment Variables (.env)

```env
# Twilio
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=your_auth_token
TWILIO_PHONE_NUMBER=+1234567890

# OpenAI
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
OPENAI_MODEL=gpt-4o-mini

# Application
APP_NAME=Enterprise Voice Gateway
COMPANY_NAME=Acme Corp
PORT=8000
BASE_URL=http://localhost:8000

# Voice
WHISPER_MODEL=base  # or small, medium, large
MAX_CALL_DURATION=300
RECORDING_TIMEOUT=5

# Database
DATABASE_URL=sqlite+aiosqlite:///./voice_gateway.db
# PostgreSQL: postgresql+asyncpg://user:pass@localhost/dbname
```

### Deploy to Production

For production deployment:

1. **Use PostgreSQL/MySQL instead of SQLite**
```env
DATABASE_URL=postgresql+asyncpg://user:password@host/dbname
```

2. **Set secure secret key**
```env
SECRET_KEY=your-very-secure-random-string-min-32-chars
```

3. **Configure Twilio webhooks**
   - Point Status Callback to: `https://yourdomaincom/voice/status`
   - Recording Callback to: `https://yourdomain.com/voice/recording-status`

4. **Use production ASGI server**
```bash
gunicorn -w 4 -k uvicorn.workers.UvicornWorker main:app --bind 0.0.0.0:8000
```

---

## 🎮 Usage

### Web Dashboard

Navigate to `http://localhost:8000` to access:

- **Live Calls**: Real-time monitoring of active calls
- **Call History**: View past calls with transcripts
- **Analytics**: Call volume, agent performance, sentiment breakdown
- **Agent Management**: Create/edit AI agent profiles
- **Audit Logs**: Compliance and security tracking

### API Endpoints

#### Voice Webhooks (Twilio)
- `POST /voice/incoming` - Inbound call entry
- `POST /voice/menu` - IVR menu selection
- `POST /voice/collect` - Voice recording prompt
- `POST /voice/process` - Recording processing
- `POST /voice/status` - Call status updates
- `POST /voice/recording-status` - Recording storage

#### Admin API
- `GET /api/dashboard` - Dashboard metrics
- `GET /api/calls` - List calls
- `GET /api/calls/{call_id}/transcript` - Full transcript
- `POST /api/agents` - Create agent
- `GET /api/agents` - List agents
- `PATCH /api/agents/{agent_id}` - Update agent
- `GET /api/analytics/calls-over-time` - Volume analytics
- `GET /api/analytics/department-breakdown` - Department stats
- `GET /api/audit` - Audit log
- `WebSocket /api/ws/live` - Real-time event stream

#### Outbound Calls
```bash
curl -X POST http://localhost:8000/voice/outbound \
  -F "to=+18005551234" \
  -F "agent_dtmf=2"
```

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────┐
│         Twilio Voice Network                │
└──────────────────┬──────────────────────────┘
                   │
        ┌──────────▼──────────┐
        │  Main FastAPI App   │
        └──────────┬──────────┘
                   │
    ┌──────────────┼──────────────┐
    │              │              │
┌───▼────┐  ┌─────▼────┐  ┌──────▼──────┐
│ Voice  │  │ Admin    │  │ Dashboard   │
│ Router │  │ API      │  │ WebSocket   │
└───┬────┘  └─────┬────┘  └──────┬──────┘
    │             │              │
    └─────────────┼──────────────┘
                  │
    ┌─────────────┼─────────────┐
    │             │             │
┌───▼────┐  ┌────▼───┐  ┌──────▼──────┐
│ AI     │  │ Call   │  │ Database    │
│ Engine │  │Manager │  │ (SQLite)    │
└───┬────┘  └────────┘  └─────────────┘
    │
    ├─► Whisper (STT)
    ├─► OpenAI GPT (LLM)
    ├─► gTTS (TTS)
    └─► Sentiment Analysis
```

---

## 👥 Sample AI Agents (Default)

1. **Aria** (Customer Support) - Press 1
   - Handles product issues, billing queries, service requests

2. **Maxwell** (Sales & Partnerships) - Press 2
   - Enterprise pricing, licensing, partnership inquiries

3. **Priya** (Technical Support) - Press 3
   - API integration, setup, troubleshooting

4. **Operator** (General Inquiries) - Press 0
   - General routing and company information

---

## 📊 Demo Data

Run `seed_demo_data.py` to populate 7 days of realistic demo call data:

```bash
python seed_demo_data.py
```

This creates:
- 30-60+ demo calls with timestamps
- Realistic conversation transcripts
- Sentiment and Summary data
- Audit trail entries

---

## 🔒 Security & Compliance

- ✅ All call data is encrypted in transit (HTTPS)
- ✅ Immutable audit logs for compliance
- ✅ Call recordings stored securely on Twilio
- ✅ Sentiment-sensitive escalation rules
- ✅ GDPR-ready with data retention policies

---

## 🐛 Troubleshooting

### Port 8000 Already in Use
```bash
lsof -i :8000  # Check what's using it
kill -9 <PID>  # Kill the process
# Or change PORT in .env
```

### Database Locked
Delete `voice_gateway.db` and restart:
```bash
rm voice_gateway.db
python main.py
```

### Twilio Webhook Not Connecting
- Verify `BASE_URL` in .env points to publicly accessible URL
- Check Twilio phone number configuration
- Ensure firewall allows inbound HTTPS

### Audio Not Transcribing
- Verify `OPENAI_API_KEY` is valid
- Ensure FFmpeg is installed (`ffmpeg --version`)
- Check Whisper model download (`pip install openai-whisper`)

---

## 📈 Performance

- **STT Latency**: ~2-5s per 10s audio (Whisper base)
- **LLM Response**: ~1-2s per request (GPT-4o-mini)
- **Concurrent Calls**: 50+ (depends on hardware)
- **Database**: SQLite for dev, PostgreSQL for 100+ concurrent

---

## 📝 License

Enterprise License - All Rights Reserved

---

## 🤝 Support

For issues or questions:
1. Check logs: `tail -f voice_gateway.log`
2. Review audit: `/api/audit`
3. Test endpoints: `/docs` (Swagger UI)

---

## 🎓 Next Steps

- [ ] Custom system prompts for your use case
- [ ] Integration with CRM (Salesforce, HubSpot)
- [ ] Multi-language support
- [ ] Advanced NLU (intent confidence tuning)
- [ ] Recording/compliance storage (AWS S3, Google Cloud)
- [ ] Escalation to human agents (integration with Zendesk, Intercom)

