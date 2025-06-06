# Analytics AI Bot

Demo‑bot die Google Analytics 4‑ en Facebook Ads‑data ophaalt en via GPT‑4 beantwoordt met inzichten en aanbevelingen.

## Installatie

```bash
git clone <jouw‑repo‑url> analytics-ai-bot
cd analytics-ai-bot
pip install -r requirements.txt
```

Vereist OpenAI Python SDK 1.x

## Credentials (.env)

```
# Google Analytics (GA4)
GA4_SERVICE_ACCOUNT_JSON=/pad/naar/ga4-service-account.json
GA4_PROPERTY_ID=123456789

# Facebook Ads
FB_APP_ID=your_fb_app_id
FB_APP_SECRET=your_fb_app_secret
FB_ACCESS_TOKEN=your_fb_access_token
FB_AD_ACCOUNT_ID=1234567890

# OpenAI
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxx
```

## Starten

```bash
python bot.py
```

Server luistert standaard op `http://127.0.0.1:5000/`.

## Webinterface

Navigeer in je browser naar `http://127.0.0.1:5000/`. Vul een start- en
einddatum in en klik op **Vraag inzichten** om direct het antwoord van de bot
te zien. Je kunt meerdere GA4 property ID's toevoegen via de knop *Voeg property toe*.
De belangrijkste statistieken en de gegenereerde AI-tekst worden in de pagina
getoond.

## Voorbeeld‑call

```bash
curl "http://127.0.0.1:5000/insights?start=2025-05-01&end=2025-05-31&ga_property=123456789&ga_property=987654321"
```
