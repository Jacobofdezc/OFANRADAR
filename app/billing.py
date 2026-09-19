import os
import json
import datetime
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from app.models import User, Organization

STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", None)
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", None)
DOMAIN_URL = os.getenv("DOMAIN_URL", "http://127.0.0.1:8000")

try:
    import stripe
    if STRIPE_SECRET_KEY:
        stripe.api_key = STRIPE_SECRET_KEY
except ImportError:
    stripe = None


class BillingService:
    """
    Stripe Integration Engine for Business Radar SaaS V5 (Feature 21).
    Supports live Stripe API keys as well as developer Sandbox simulation mode.
    """

    @staticmethod
    def create_checkout_session(user: User, plan: str = "pro") -> Dict[str, Any]:
        """
        Generates a Stripe Checkout Session URL for upgrading to Pro or Institutional plans.
        """
        price_id = "price_pro_99_monthly" if plan.lower() == "pro" else "price_inst_499_monthly"

        # If live Stripe secret key is available and stripe module installed
        if stripe and STRIPE_SECRET_KEY:
            try:
                # Ensure customer exists or create one
                customer_id = user.stripe_customer_id
                if not customer_id:
                    customer = stripe.Customer.create(
                        email=user.email,
                        name=user.full_name,
                        metadata={"user_id": user.id, "tenant_id": user.tenant_id}
                    )
                    customer_id = customer.id

                checkout_session = stripe.checkout.Session.create(
                    customer=customer_id,
                    payment_method_types=['card'],
                    line_items=[{
                        'price': price_id,
                        'quantity': 1,
                    }],
                    mode='subscription',
                    success_url=f"{DOMAIN_URL}/app?checkout_success=true&session_id={{CHECKOUT_SESSION_ID}}",
                    cancel_url=f"{DOMAIN_URL}/app?checkout_canceled=true",
                    client_reference_id=user.id,
                    metadata={"user_id": user.id, "plan": plan}
                )
                return {"checkout_url": checkout_session.url, "mode": "stripe_live"}
            except Exception as e:
                print(f"[WARN] Stripe Live API Checkout Error: {e}. Falling back to Sandbox mode.")

        # Sandbox Developer Simulation Mode (When no Stripe secret key is configured)
        mock_session_id = f"cs_sim_{user.id[:8]}_{int(datetime.datetime.utcnow().timestamp())}"
        simulated_checkout_url = f"{DOMAIN_URL}/app?checkout_success=true&session_id={mock_session_id}&plan={plan}"
        return {
            "checkout_url": simulated_checkout_url,
            "mode": "sandbox_simulation",
            "message": "Simulación Sandbox de Pago en Stripe (Sin llaves en vivo requeridas)."
        }

    @staticmethod
    def create_customer_portal_session(user: User) -> Dict[str, Any]:
        """
        Generates Stripe Customer Portal URL for managing billing, downloading invoices, or canceling.
        """
        if stripe and STRIPE_SECRET_KEY and user.stripe_customer_id:
            try:
                portal_session = stripe.billing_portal.Session.create(
                    customer=user.stripe_customer_id,
                    return_url=f"{DOMAIN_URL}/app",
                )
                return {"portal_url": portal_session.url, "mode": "stripe_live"}
            except Exception as e:
                print(f"[WARN] Stripe Portal Error: {e}")

        # Sandbox fallback
        return {
            "portal_url": f"{DOMAIN_URL}/app?billing_portal=active&user_id={user.id}",
            "mode": "sandbox_simulation",
            "message": "Portal del Cliente Stripe (Modo Simulación)."
        }

    @staticmethod
    def process_webhook_payload(payload_bytes: bytes, sig_header: Optional[str], db: Session) -> Dict[str, Any]:
        """
        Handles Stripe Webhook events (checkout.session.completed, customer.subscription.deleted).
        """
        event = None

        if stripe and STRIPE_WEBHOOK_SECRET and sig_header:
            try:
                event = stripe.Webhook.construct_event(
                    payload_bytes, sig_header, STRIPE_WEBHOOK_SECRET
                )
            except Exception as e:
                raise ValueError(f"Firma de Webhook Stripe inválida: {str(e)}")
        else:
            try:
                event = json.loads(payload_bytes.decode('utf-8'))
            except Exception:
                raise ValueError("Payload JSON no válido para webhook")

        event_type = event.get("type")
        event_data = event.get("data", {}).get("object", {})

        print(f"[STRIPE WEBHOOK] Evento recibido: {event_type}")

        if event_type == "checkout.session.completed":
            user_id = event_data.get("client_reference_id") or event_data.get("metadata", {}).get("user_id")
            email = event_data.get("customer_email") or event_data.get("customer_details", {}).get("email")

            user = None
            if user_id:
                user = db.query(User).filter(User.id == user_id).first()
            if not user and email:
                user = db.query(User).filter(User.email == email).first()

            if user:
                user.subscription_status = "active"
                if event_data.get("customer"):
                    user.stripe_customer_id = str(event_data.get("customer"))
                db.commit()
                print(f"[BILLING SUCCESS] Suscripción activada exitosamente para usuario {user.email}")
                return {"status": "success", "event": event_type, "user_email": user.email, "subscription_status": "active"}

        elif event_type in ["customer.subscription.deleted", "customer.subscription.updated"]:
            sub_status = event_data.get("status", "canceled")
            customer_id = event_data.get("customer")
            
            user = db.query(User).filter(User.stripe_customer_id == customer_id).first()
            if user:
                user.subscription_status = "canceled" if sub_status in ["canceled", "unpaid"] else "active"
                db.commit()
                return {"status": "success", "event": event_type, "user_email": user.email, "subscription_status": user.subscription_status}

        return {"status": "ignored", "event": event_type}
