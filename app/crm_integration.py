import datetime
from typing import Dict, Any, Optional


class CRMIntegrationEngine:
    """
    Simulates / handles enterprise CRM integrations for HubSpot and Salesforce.
    Formats company intent profiles and target personas into native CRM Lead & Opportunity objects.
    """

    @classmethod
    def push_to_hubspot(cls, company_data: Dict[str, Any], intent_data: Optional[Dict[str, Any]] = None, target_email: Optional[str] = None) -> Dict[str, Any]:
        """
        Maps company data to HubSpot CRM Company & Deal Objects.
        """
        domain = company_data.get("domain", "")
        name = company_data.get("canonical_name", domain)
        score = 0.0
        if intent_data and isinstance(intent_data, dict):
            scores = intent_data.get("intent_scores") or {}
            score = scores.get("composite_score", 0.0)

        hubspot_payload = {
            "properties": {
                "domain": domain,
                "name": name,
                "industry": company_data.get("industry", "Software"),
                "numberofemployees": company_data.get("employee_range", "50-200"),
                "city": company_data.get("hq_city", "Madrid"),
                "country": company_data.get("hq_country", "ES"),
                "ofan_intent_score": str(score),
                "ofan_intent_label": intent_data.get("primary_label", "High Intent") if intent_data else "High Intent",
                "lifecyclestage": "marketingqualifiedlead",
                "hubspot_owner_id": target_email or "sales_team@radar.com"
            }
        }

        return {
            "status": "success",
            "provider": "HubSpot CRM",
            "hubspot_object_id": f"hs_company_{abs(hash(domain)) % 8999999 + 1000000}",
            "deal_id": f"hs_deal_{abs(hash(domain)) % 8999999 + 1000000}",
            "synced_at": datetime.datetime.utcnow().isoformat(),
            "payload_sent": hubspot_payload,
            "message": f"Empresa '{name}' sincronizada con éxito en HubSpot CRM como Lead Cualificado."
        }

    @classmethod
    def push_to_salesforce(cls, company_data: Dict[str, Any], intent_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Maps company data to Salesforce CRM Account & Opportunity Objects.
        """
        domain = company_data.get("domain", "")
        name = company_data.get("canonical_name", domain)
        score = 0.0
        if intent_data and isinstance(intent_data, dict):
            scores = intent_data.get("intent_scores") or {}
            score = scores.get("composite_score", 0.0)

        salesforce_payload = {
            "Account": {
                "Name": name,
                "Website": company_data.get("website_url") or f"https://{domain}",
                "Industry": company_data.get("industry", "Software"),
                "NumberOfEmployees": company_data.get("employee_range", "50-200"),
                "BillingCity": company_data.get("hq_city", "Madrid"),
                "BillingCountry": company_data.get("hq_country", "ES"),
                "Intent_Score__c": score
            },
            "Opportunity": {
                "Name": f"Oportunidad - {name} (Business Radar)",
                "StageName": "Qualification",
                "CloseDate": (datetime.date.today() + datetime.timedelta(days=30)).isoformat(),
                "Amount": 15000
            }
        }

        return {
            "status": "success",
            "provider": "Salesforce Sales Cloud",
            "salesforce_account_id": f"001800000{abs(hash(domain)) % 8999999 + 1000000}AAA",
            "opportunity_id": f"006800000{abs(hash(domain)) % 8999999 + 1000000}BBB",
            "synced_at": datetime.datetime.utcnow().isoformat(),
            "payload_sent": salesforce_payload,
            "message": f"Cuenta '{name}' y Oportunidad asociadas en Salesforce Sales Cloud."
        }
