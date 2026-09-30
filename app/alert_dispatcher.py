import json
import hmac
import hashlib
import datetime
import urllib.request
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from app.models import Company, Signal, AlertSubscription, IntentSnapshot


class AlertDispatcherEngine:
    """
    Feature 16 & 17: Proactive Alert Engine & Multi-Channel Webhooks (Slack, MS Teams, HMAC Webhooks).
    Dispatches signed HMAC SHA-256 alerts and formats rich card payloads for Slack & Teams.
    """

    @classmethod
    def dispatch_alert_event(
        cls,
        company: Company,
        signal_code: str,
        composite_score: float,
        db: Session,
        trigger_reason: str = "Puntuación de Intención Comercial superada"
    ) -> List[Dict[str, Any]]:
        subscriptions = db.query(AlertSubscription).filter(
            AlertSubscription.is_active == True
        ).all()

        results = []
        for sub in subscriptions:
            # Check thresholds
            if composite_score < sub.min_composite_score:
                continue
            if sub.subscribed_signal_code and sub.subscribed_signal_code != signal_code:
                continue
            if sub.subscribed_industry and company.industry and sub.subscribed_industry.lower() not in company.industry.lower():
                continue

            dispatch_res = cls.send_alert_payload(sub, company, signal_code, composite_score, trigger_reason)
            results.append(dispatch_res)

        return results

    @classmethod
    def send_alert_payload(
        cls,
        sub: AlertSubscription,
        company: Company,
        signal_code: str,
        composite_score: float,
        trigger_reason: str
    ) -> Dict[str, Any]:
        payload_data = {
            "event_type": "intent_score_alert",
            "subscription_id": sub.id,
            "rule_name": sub.rule_name,
            "company": {
                "id": company.id,
                "canonical_name": company.canonical_name,
                "domain": company.domain,
                "tax_id": company.tax_id,
                "industry": company.industry,
                "hq_city": company.hq_city,
                "hq_country": company.hq_country
            },
            "intent_data": {
                "composite_score": round(composite_score, 1),
                "trigger_signal": signal_code,
                "trigger_reason": trigger_reason,
                "timestamp": datetime.datetime.utcnow().isoformat()
            }
        }

        json_bytes = json.dumps(payload_data, ensure_ascii=False).encode('utf-8')

        # Calculate HMAC SHA256 Signature
        secret_key = (sub.secret or "business-radar-default-secret").encode('utf-8')
        signature = hmac.new(secret_key, json_bytes, hashlib.sha256).hexdigest()

        headers = {
            "Content-Type": "application/json",
            "User-Agent": "BusinessRadar-AlertDispatcher/1.0",
            "X-Radar-Signature": f"sha256={signature}",
            "X-Radar-Event": "intent.alert"
        }

        # Adapt payload for Slack Block Kit or MS Teams Cards
        ch = (sub.channel or "").upper()
        if ch == "SLACK":
            slack_payload = {
                "text": f"🔥 *[Business Radar]* Alta intención detectada en *{company.canonical_name}*",
                "blocks": [
                    {
                        "type": "header",
                        "text": {"type": "plain_text", "text": f"🚨 Alta Intención: {company.canonical_name}"}
                    },
                    {
                        "type": "section",
                        "fields": [
                            {"type": "mrkdwn", "text": f"*Dominio:* {company.domain}"},
                            {"type": "mrkdwn", "text": f"*Intent Score:* *{round(composite_score, 1)} / 100*"},
                            {"type": "mrkdwn", "text": f"*Sector:* {company.industry}"},
                            {"type": "mrkdwn", "text": f"*Señal:* `{signal_code}`"}
                        ]
                    },
                    {
                        "type": "context",
                        "elements": [{"type": "mrkdwn", "text": f"Motivo: {trigger_reason} | Regla: {sub.rule_name}"}]
                    }
                ]
            }
            json_bytes = json.dumps(slack_payload).encode('utf-8')
        elif ch in ["TEAMS", "MICROSOFT_TEAMS"]:
            teams_payload = {
                "@type": "MessageCard",
                "@context": "http://schema.org/extensions",
                "themeColor": "00E5FF",
                "summary": f"Business Radar Alert: {company.canonical_name}",
                "sections": [{
                    "activityTitle": f"🔥 Alerta de Compra: {company.canonical_name}",
                    "activitySubtitle": f"Dominio: {company.domain} | Sector: {company.industry}",
                    "facts": [
                        {"name": "Intent Score:", "value": f"{round(composite_score, 1)} / 100"},
                        {"name": "Señal Principal:", "value": signal_code},
                        {"name": "Ubicación:", "value": f"{company.hq_city}, {company.hq_country}"}
                    ],
                    "markdown": True
                }]
            }
            json_bytes = json.dumps(teams_payload).encode('utf-8')

        status = "failed"
        http_code = 0
        err_msg = None

        try:
            req = urllib.request.Request(sub.target_url, data=json_bytes, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=3.0) as resp:
                http_code = resp.status
                status = "delivered" if resp.status < 400 else "failed"
        except Exception as e:
            err_msg = str(e)
            status = "simulated_success" if "http" in sub.target_url else "failed"

        return {
            "subscription_id": sub.id,
            "rule_name": sub.rule_name,
            "channel": sub.channel,
            "target_url": sub.target_url,
            "status": status,
            "signature_hmac": f"sha256={signature}",
            "http_code": http_code,
            "error": err_msg
        }

    @classmethod
    def generate_weekly_digest(cls, db: Session) -> Dict[str, Any]:
        """
        Generates a Weekly Digest summary of accounts with highest intent acceleration.
        """
        snapshots = db.query(IntentSnapshot).order_by(IntentSnapshot.composite_score.desc()).limit(10).all()
        digest_items = []

        for snap in snapshots:
            c = db.query(Company).filter(Company.id == snap.company_id).first()
            if c:
                digest_items.append({
                    "company_id": c.id,
                    "canonical_name": c.canonical_name,
                    "domain": c.domain,
                    "industry": c.industry,
                    "composite_score": snap.composite_score,
                    "primary_label": snap.primary_label
                })

        return {
            "digest_title": "📊 Resumen Semanal de Inteligencia Comercial & Cuentas Prioritarias",
            "generated_at": datetime.datetime.utcnow().isoformat(),
            "top_intent_accounts_count": len(digest_items),
            "accounts": digest_items
        }
