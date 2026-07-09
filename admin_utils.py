from typing import Optional
def resolve_admin_for_signup(email: str, invite_code: Optional[str], admin_email: Optional[str], admins: list, domain_mapping: dict) -> Optional[dict]:
    if invite_code:
        for admin in admins:
            if str(admin.get("invite_code") or "").strip().lower() == str(invite_code).strip().lower():
                return admin

    if admin_email:
        for admin in admins:
            if str(admin.get("email") or "").strip().lower() == str(admin_email).strip().lower():
                return admin

    if email:
        domain = email.split("@")[-1].strip().lower()
        mapped_admin_email = domain_mapping.get(domain)
        if mapped_admin_email:
            for admin in admins:
                if str(admin.get("email") or "").strip().lower() == str(mapped_admin_email).strip().lower():
                    return admin
    return None
