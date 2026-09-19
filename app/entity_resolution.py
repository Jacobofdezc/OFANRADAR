import re
from typing import Optional
from sqlalchemy.orm import Session
from app.models import Company, CompanyAlias


CIF_NIF_REGEX = re.compile(r'^[ABCDEFGHJNPQRSUVW]\d{7}[0-9A-J]$', re.IGNORECASE)
NIE_REGEX = re.compile(r'^[XYZ]\d{7}[A-Z]$', re.IGNORECASE)


def normalize_domain(domain_str: str) -> str:
    """
    Cleans domain URL into canonical root domain format.
    Example: 'https://www.techscale.io/pricing?ref=1' -> 'techscale.io'
    """
    if not domain_str:
        return ""
    d = domain_str.strip().lower()
    d = re.sub(r'^https?://', '', d)
    d = re.sub(r'^www\.', '', d)
    d = d.split('/')[0].split('?')[0].split('#')[0]
    return d


def validate_spanish_tax_id(tax_id: str) -> bool:
    """
    Validates format of Spanish CIF / NIF / NIE.
    """
    if not tax_id:
        return False
    clean_id = tax_id.strip().upper().replace("-", "").replace(" ", "")
    return bool(CIF_NIF_REGEX.match(clean_id) or NIE_REGEX.match(clean_id))


def resolve_canonical_company(db: Session, identifier: str) -> Optional[Company]:
    """
    Resolves messy input (UUID, domain, tax_id, or name alias) to canonical Company.
    """
    if not identifier:
        return None

    clean_ident = identifier.strip()

    # 1. Exact UUID match
    company = db.query(Company).filter(Company.id == clean_ident).first()
    if company:
        return company

    # 2. Domain match
    norm_dom = normalize_domain(clean_ident)
    if norm_dom:
        company = db.query(Company).filter(Company.domain == norm_dom).first()
        if company:
            return company

    # 3. Tax ID match
    clean_tax = clean_ident.upper().replace("-", "").replace(" ", "")
    company = db.query(Company).filter(Company.tax_id == clean_tax).first()
    if company:
        return company

    # 4. Alias lookup table
    alias = db.query(CompanyAlias).filter(CompanyAlias.alias_name.ilike(clean_ident)).first()
    if alias:
        return alias.company

    # 5. Fallback canonical name fuzzy match
    company = db.query(Company).filter(Company.canonical_name.ilike(f"%{clean_ident}%")).first()
    return company
