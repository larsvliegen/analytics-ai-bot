import os
import json
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, render_template
from dotenv import load_dotenv

# Google Analytics
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import RunReportRequest

# Facebook API
from facebook_business.api import FacebookAdsApi
from facebook_business.adobjects.adaccount import AdAccount

# OpenAI
from openai import OpenAI

# ======== 1. Environment variables laden ========

load_dotenv()

GA4_SERVICE_ACCOUNT_JSON = os.getenv("GA4_SERVICE_ACCOUNT_JSON")
GA4_PROPERTY_ID = os.getenv("GA4_PROPERTY_ID")

FB_APP_ID = os.getenv("FB_APP_ID")
FB_APP_SECRET = os.getenv("FB_APP_SECRET")
FB_ACCESS_TOKEN = os.getenv("FB_ACCESS_TOKEN")
FB_AD_ACCOUNT_ID = os.getenv("FB_AD_ACCOUNT_ID")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

required_vars = {
    "GA4_SERVICE_ACCOUNT_JSON": GA4_SERVICE_ACCOUNT_JSON,
    "GA4_PROPERTY_ID": GA4_PROPERTY_ID,
    "FB_APP_ID": FB_APP_ID,
    "FB_APP_SECRET": FB_APP_SECRET,
    "FB_ACCESS_TOKEN": FB_ACCESS_TOKEN,
    "FB_AD_ACCOUNT_ID": FB_AD_ACCOUNT_ID,
    "OPENAI_API_KEY": OPENAI_API_KEY,
}
missing = [k for k, v in required_vars.items() if not v]
if missing:
    raise RuntimeError(
        f"De volgende environment variables ontbreken of zijn leeg: {', '.join(missing)}"
    )

openai_client = OpenAI(api_key=OPENAI_API_KEY)

# ======== 2. Functie om GA4-data op te halen ========

def get_ga4_metrics(property_id: str, start_date: str, end_date: str) -> dict:
    try:
        client = BetaAnalyticsDataClient.from_service_account_json(GA4_SERVICE_ACCOUNT_JSON)
        request = RunReportRequest(
            property=f"properties/{property_id}",
            dimensions=[{"name": "date"}],
            metrics=[{"name": "sessions"}, {"name": "bounceRate"}],
            date_ranges=[{"start_date": start_date, "end_date": end_date}],
        )
        response = client.run_report(request)
    except Exception as e:
        raise RuntimeError(f"Fout bij ophalen GA4-data: {e}")

    total_sessions, sum_bounce, row_count = 0, 0.0, 0
    for row in response.rows:
        total_sessions += int(row.metric_values[0].value)
        sum_bounce += float(row.metric_values[1].value)
        row_count += 1

    avg_bounce = sum_bounce / row_count if row_count else 0.0
    return {
        "sessions": total_sessions,
        "avg_bounce_rate": round(avg_bounce, 2),
    }

# Helper om metrics voor meerdere GA4-properties op te halen
def get_multiple_ga4_metrics(property_ids: list[str], start_date: str, end_date: str) -> dict:
    metrics = {}
    for pid in property_ids:
        metrics[pid] = get_ga4_metrics(pid, start_date, end_date)
    return metrics

# ======== 3. Functie om Facebook Ads-data op te halen ========

def get_fb_ads_metrics(ad_account_id: str, start_date: str, end_date: str) -> dict:
    try:
        FacebookAdsApi.init(FB_APP_ID, FB_APP_SECRET, FB_ACCESS_TOKEN)
        account = AdAccount(f"act_{ad_account_id}")
        params = {
            "time_range": {"since": start_date, "until": end_date},
            "fields": ["impressions", "clicks", "spend", "ctr"],
        }
        insights = account.get_insights(params=params)
        if not insights:
            raise RuntimeError("Geen Facebook Ads-data gevonden voor deze periode.")
        data = insights[0]
    except Exception as e:
        raise RuntimeError(f"Fout bij ophalen Facebook Ads-data: {e}")

    return {
        "impressions": int(data.get("impressions", 0)),
        "clicks": int(data.get("clicks", 0)),
        "spend": float(data.get("spend", 0.0)),
        "ctr": float(data.get("ctr", 0.0)),
    }

# ======== 4. Functie om inzichten te genereren via GPT-4 ========

def generate_insights(
    ga_metrics: dict,
    ga_summary: dict,
    fb_metrics: dict,
    start_date: str,
    end_date: str,
) -> str:
    """Genereer tekstuele inzichten op basis van de opgehaalde data."""

    ga_lines = []
    for pid, metrics in ga_metrics.items():
        ga_lines.append(
            f"Property {pid}: sessies {metrics['sessions']}, bounce rate {metrics['avg_bounce_rate']}%"
        )
    ga_lines.append(
        f"Totaal: {ga_summary['total_sessions']} sessies, gemiddelde bounce rate {ga_summary['overall_bounce_rate']}%"
    )
    ga_text = "\n".join(ga_lines)

    prompt = f"""
Jij bent een ervaren digital marketing consultant.
Periode: {start_date} t/m {end_date}

Google Analytics 4
{ga_text}

Facebook Ads
- Impressies: {fb_metrics['impressions']}
- Klikken: {fb_metrics['clicks']}
- Kosten: €{fb_metrics['spend']:.2f}
- CTR: {fb_metrics['ctr']*100:.2f}%

Geef eerst aanbevelingen op basis van Google Analytics en daarna voor Facebook Ads. Gebruik duidelijke koppen en bullet points.
1. Wat valt op?
2. Mogelijke oorzaken?
3. Werkpunten voor website/SEO?
4. Aanbevelingen voor Facebook Ads?
5. Concrete bullet-points per onderdeel.

Schrijf in het Nederlands, gestructureerd met koppen en bullets.
"""
    try:
        response = openai_client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "Je bent een deskundige marketinganalist."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.7,
            max_tokens=900,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        raise RuntimeError(f"Fout bij OpenAI-aanroep: {e}")

# ======== 5. Flask-app ========

app = Flask(__name__)

@app.route("/")
def index():
    today = datetime.utcnow().date()
    default_end = today.strftime("%Y-%m-%d")
    default_start = (today - timedelta(days=30)).strftime("%Y-%m-%d")
    return render_template(
        "index.html",
        default_start=default_start,
        default_end=default_end,
        default_property=GA4_PROPERTY_ID,
    )

@app.route("/insights", methods=["GET"])
def insights():
    start_date = request.args.get("start")
    end_date = request.args.get("end")
    if not start_date or not end_date:
        return jsonify({"error": "Gebruik query-parameters 'start' en 'end'."}), 400
    try:
        datetime.strptime(start_date, "%Y-%m-%d")
        datetime.strptime(end_date, "%Y-%m-%d")
    except ValueError:
        return jsonify({"error": "Datumformaat moet YYYY-MM-DD zijn."}), 400

    property_ids = request.args.getlist("ga_property")
    if not property_ids:
        property_ids = [GA4_PROPERTY_ID]

    try:
        ga_metrics = get_multiple_ga4_metrics(property_ids, start_date, end_date)

        total_sessions = sum(m["sessions"] for m in ga_metrics.values())
        if total_sessions:
            weighted = sum(
                m["avg_bounce_rate"] * m["sessions"] for m in ga_metrics.values()
            )
            overall_bounce = round(weighted / total_sessions, 2)
        else:
            overall_bounce = 0.0

        ga_summary = {
            "total_sessions": total_sessions,
            "overall_bounce_rate": overall_bounce,
        }

        fb_metrics = get_fb_ads_metrics(FB_AD_ACCOUNT_ID, start_date, end_date)
        ai_text = generate_insights(
            ga_metrics, ga_summary, fb_metrics, start_date, end_date
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    return jsonify({
        "ga_metrics": ga_metrics,
        "ga_summary": ga_summary,
        "fb_metrics": fb_metrics,
        "ai_insights": ai_text,
    })


@app.route("/operator", methods=["POST"])
def operator():
    data = request.get_json(silent=True)
    if not data or not data.get("instruction"):
        return jsonify({"error": "Ontbrekende 'instruction' in request body."}), 400

    prompt = (
        "Je bent een ervaren analytics specialist. "
        "Voer de volgende opdracht uit of geef een concreet stappenplan: "
        f"{data['instruction']}"
    )
    try:
        response = openai_client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=500,
        )
        content = response.choices[0].message.content.strip()
    except Exception as e:
        return jsonify({"error": f"Fout bij OpenAI-aanroep: {e}"}), 500

    return jsonify({"response": content})

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
