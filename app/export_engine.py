import csv
import io
from typing import Dict, Any, List


class ExportEngine:
    """
    Export Engine for OFANRADAR Business Intelligence.
    Generates print-ready HTML executive reports (browser printable to PDF) and CSV data feeds.
    """

    @staticmethod
    def generate_company_csv(companies_data: List[Dict[str, Any]]) -> str:
        """
        Generates CSV string from list of company dictionary records.
        """
        output = io.StringIO()
        fieldnames = [
            "id", "canonical_name", "legal_name", "domain", "tax_id",
            "industry", "employee_range", "hq_city", "hq_country",
            "primary_label", "composite_score", "growth_intent",
            "hiring_intent", "expansion_intent", "technology_change_intent",
            "financial_stress", "website_url", "linkedin_url"
        ]

        writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()

        for comp in companies_data:
            intent = comp.get("latest_intent") or {}
            row = {
                "id": comp.get("id", ""),
                "canonical_name": comp.get("canonical_name", ""),
                "legal_name": comp.get("legal_name", ""),
                "domain": comp.get("domain", ""),
                "tax_id": comp.get("tax_id", ""),
                "industry": comp.get("industry", ""),
                "employee_range": comp.get("employee_range", ""),
                "hq_city": comp.get("hq_city", ""),
                "hq_country": comp.get("hq_country", ""),
                "primary_label": comp.get("primary_label", ""),
                "composite_score": intent.get("composite_score", 0.0) if isinstance(intent, dict) else 0.0,
                "growth_intent": intent.get("growth_intent", 0.0) if isinstance(intent, dict) else 0.0,
                "hiring_intent": intent.get("hiring_intent", 0.0) if isinstance(intent, dict) else 0.0,
                "expansion_intent": intent.get("expansion_intent", 0.0) if isinstance(intent, dict) else 0.0,
                "technology_change_intent": intent.get("technology_change_intent", 0.0) if isinstance(intent, dict) else 0.0,
                "financial_stress": intent.get("financial_stress", 0.0) if isinstance(intent, dict) else 0.0,
                "website_url": comp.get("website_url", ""),
                "linkedin_url": comp.get("linkedin_url", "")
            }
            writer.writerow(row)

        return output.getvalue()

    @staticmethod
    def generate_html_dossier_pdf_view(company_data: Dict[str, Any], intent_data: Dict[str, Any]) -> str:
        """
        Generates print-ready HTML page styled for PDF export (A4 page format).
        """
        name = company_data.get("canonical_name", "Empresa")
        domain = company_data.get("domain", "")
        legal_name = company_data.get("legal_name", name)
        industry = company_data.get("industry", "Servicios B2B")
        emp_range = company_data.get("employee_range", "50-200")
        hq = f"{company_data.get('hq_city', 'Madrid')}, {company_data.get('hq_country', 'ES')}"
        tax_id = company_data.get("tax_id", "N/A")
        logo_url = company_data.get("logo_url") or f"https://logo.clearbit.com/{domain}"

        intent_scores = intent_data.get("intent_scores", {})
        comp_score = intent_scores.get("composite_score", 0.0)
        label = intent_data.get("primary_label", "Intención Moderada")
        summary = intent_data.get("business_summary", "")
        action = intent_data.get("recommended_action", "")
        dossier = intent_data.get("institutional_dossier") or {}

        financials = dossier.get("financials", {})
        playbook = dossier.get("sales_playbook", {})
        personas = playbook.get("target_personas", [])
        pain_points = playbook.get("pain_points", [])
        competitors = dossier.get("competitors", [])

        personas_html = "".join([
            f"<div class='card-item' style='margin-bottom: 8px; padding-bottom: 6px; border-bottom: 1px solid #e2e8f0;'><strong>{p.get('role', '')}</strong> — <span style='color:#0284c7;'>Enfoque:</span> {p.get('focus', '')}" + (f" | <span style='color:#059669;'><strong>KPI Target:</strong> {p.get('kpi')}</span>" if p.get('kpi') else "") + "</div>"
            for p in personas
        ])

        pain_points_html = "".join([
            f"<li>{pt}</li>" for pt in pain_points
        ])

        competitors_html = "".join([
            f"<tr><td>{c.get('name')}</td><td>{c.get('size')}</td><td>{c.get('score')}</td><td><span class='badge'>{c.get('status')}</span></td></tr>"
            for c in competitors
        ])

        return f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <title>Informe Ejecutivo - {name}</title>
    <style>
        @page {{ size: A4; margin: 15mm; }}
        body {{
            font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, Roboto, sans-serif;
            color: #0f172a;
            background: #ffffff;
            margin: 0;
            padding: 20px;
            font-size: 13px;
            line-height: 1.5;
        }}
        .header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 3px solid #00e5ff;
            padding-bottom: 15px;
            margin-bottom: 20px;
        }}
        .logo-box {{
            display: flex;
            align-items: center;
            gap: 15px;
        }}
        .logo-img {{
            width: 50px;
            height: 50px;
            border-radius: 8px;
            object-fit: contain;
            border: 1px solid #e2e8f0;
        }}
        .brand-title {{
            font-size: 22px;
            font-weight: 700;
            color: #0f172a;
            margin: 0;
        }}
        .subtitle {{
            color: #64748b;
            font-size: 12px;
            margin: 2px 0 0 0;
        }}
        .score-pill {{
            background: #0f172a;
            color: #00e5ff;
            padding: 10px 18px;
            border-radius: 10px;
            text-align: right;
        }}
        .score-val {{
            font-size: 26px;
            font-weight: 800;
        }}
        .section-title {{
            font-size: 14px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            color: #0284c7;
            border-bottom: 1px solid #e2e8f0;
            padding-bottom: 5px;
            margin-top: 20px;
            margin-bottom: 12px;
        }}
        .grid-2 {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 15px;
        }}
        .grid-4 {{
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 10px;
        }}
        .card {{
            background: #f8fafc;
            border: 1px solid #e2e8f0;
            border-radius: 8px;
            padding: 12px;
        }}
        .card-label {{
            font-size: 11px;
            color: #64748b;
            text-transform: uppercase;
            font-weight: 600;
        }}
        .card-val {{
            font-size: 14px;
            font-weight: 700;
            color: #0f172a;
            margin-top: 4px;
        }}
        .badge {{
            display: inline-block;
            background: #e0f2fe;
            color: #0369a1;
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 11px;
            font-weight: 600;
        }}
        ul {{ margin: 0; padding-left: 18px; }}
        li {{ margin-bottom: 4px; }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 8px;
        }}
        th, td {{
            padding: 8px 10px;
            text-align: left;
            border-bottom: 1px solid #e2e8f0;
        }}
        th {{
            background: #f1f5f9;
            color: #475569;
            font-size: 11px;
            text-transform: uppercase;
        }}
        .pitch-box {{
            background: #eff6ff;
            border-left: 4px solid #2563eb;
            padding: 12px;
            border-radius: 4px;
            white-space: pre-wrap;
            font-family: monospace;
            font-size: 12px;
        }}
        .footer {{
            margin-top: 30px;
            text-align: center;
            font-size: 11px;
            color: #94a3b8;
            border-top: 1px solid #e2e8f0;
            padding-top: 10px;
        }}
        @media print {{
            .no-print {{ display: none; }}
            body {{ padding: 0; }}
        }}
    </style>
</head>
<body>
    <div class="no-print" style="margin-bottom: 15px; text-align: right; display: flex; justify-content: flex-end; align-items: center; gap: 12px; background: #f1f5f9; padding: 12px 16px; border-radius: 8px; border: 1px solid #cbd5e1;">
        <span style="font-size: 13px; font-weight: 600; color: #475569; margin-right: auto;">📄 Dossier Ejecutivo de Inteligencia Económica</span>
        <button type="button" onclick="triggerPrint();" style="background: #0284c7; color: white; border: none; padding: 10px 18px; border-radius: 6px; cursor: pointer; font-weight: 700; font-size: 13px; box-shadow: 0 2px 8px rgba(2, 132, 199, 0.3); display: flex; align-items: center; gap: 6px;">
            <span>🖨️</span> Imprimir / Guardar PDF
        </button>
        <button type="button" onclick="downloadHtmlDossier();" style="background: #059669; color: white; border: none; padding: 10px 18px; border-radius: 6px; cursor: pointer; font-weight: 700; font-size: 13px; box-shadow: 0 2px 8px rgba(5, 150, 105, 0.3); display: flex; align-items: center; gap: 6px;">
            <span>📥</span> Descargar Documento HTML
        </button>
    </div>

    <div class="header">
        <div class="logo-box">
            <img src="{logo_url}" class="logo-img" alt="Logo" onerror="this.src='https://via.placeholder.com/50?text=BRAND'">
            <div>
                <h1 class="brand-title">{name}</h1>
                <p class="subtitle">{legal_name} | {domain} | CIF: {tax_id}</p>
            </div>
        </div>
        <div class="score-pill">
            <div class="score-val">{comp_score}/100</div>
            <div style="font-size: 11px;">{label}</div>
        </div>
    </div>

    <div class="grid-4">
        <div class="card">
            <div class="card-label">Sector</div>
            <div class="card-val">{industry}</div>
        </div>
        <div class="card">
            <div class="card-label">Plantilla</div>
            <div class="card-val">{emp_range} empl.</div>
        </div>
        <div class="card">
            <div class="card-label">Sede Principal</div>
            <div class="card-val">{hq}</div>
        </div>
        <div class="card">
            <div class="card-label">Facturación / ARR</div>
            <div class="card-val" style="font-size: 12px;">{financials.get('arr_estimate', 'N/A')}</div>
        </div>
    </div>

    <div class="section-title">Síntesis Ejecutiva & Diagnóstico de Intención</div>
    <div class="card" style="margin-bottom: 15px;">
        <p><strong>Resumen de Negocio:</strong> {summary}</p>
        <p style="margin-bottom: 0;"><strong>Recomendación de Acción:</strong> {action}</p>
    </div>

    <div class="grid-2">
        <div>
            <div class="section-title">Métricas Financieras Auditadas</div>
            <div class="card">
                <p><strong>Crecimiento YoY:</strong> {financials.get('yoy_growth', 'N/A')}</p>
                <p><strong>Burn Rate Est.:</strong> {financials.get('burn_rate', 'N/A')}</p>
                <p><strong>Runway Disponible:</strong> {financials.get('runway', 'N/A')}</p>
                <p><strong>Riesgo de Solvencia:</strong> {financials.get('solvency_risk', 'N/A')}</p>
                <p style="margin-bottom:0;"><strong>Información Mercantil:</strong> {financials.get('mercantil_info', 'N/A')}</p>
            </div>
        </div>
        <div>
            <div class="section-title">Puntos de Dolor & Ventana de Oportunidad</div>
            <div class="card">
                <p><strong>Ventana:</strong> {playbook.get('buying_window', 'Abierta')}</p>
                <p><strong>Desafíos Detectados:</strong></p>
                <ul>
                    {pain_points_html}
                </ul>
            </div>
        </div>
    </div>

    <div class="section-title">Decisores Clave (Target Personas)</div>
    <div class="card" style="margin-bottom: 15px;">
        {personas_html}
    </div>



    <div class="section-title">Benchmarking Competitivo</div>
    <table>
        <thead>
            <tr>
                <th>Empresa Competidora</th>
                <th>Tamaño</th>
                <th>Intent Score</th>
                <th>Estado</th>
            </tr>
        </thead>
        <tbody>
            {competitors_html}
        </tbody>
    </table>

    <div class="footer">
        Documento generado automáticamente por OFANRADAR Business Intelligence Terminal | Registro Confidencial de Inteligencia Económica
    </div>
    <script>
        function triggerPrint() {{
            window.focus();
            setTimeout(function() {{
                window.print();
            }}, 100);
        }}

        function downloadHtmlDossier() {{
            try {{
                var content = "<!DOCTYPE html>\n" + document.documentElement.outerHTML;
                var blob = new Blob([content], {{ type: "text/html;charset=utf-8" }});
                var a = document.createElement("a");
                a.href = URL.createObjectURL(blob);
                a.download = "Dossier_Ejecutivo_{domain}.html";
                document.body.appendChild(a);
                a.click();
                setTimeout(function() {{ a.remove(); }}, 500);
            }} catch (e) {{
                console.error("Error al descargar HTML:", e);
            }}
        }}

        window.addEventListener('load', function() {{
            // Automatically open print/PDF dialog 500ms after opening page
            setTimeout(triggerPrint, 500);
        }});
    </script>
</body>
</html>
"""
