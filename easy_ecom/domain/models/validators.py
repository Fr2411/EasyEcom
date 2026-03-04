def validate_email_format(value: str) -> str:
    email = value.strip().lower()
    if "@" not in email or email.startswith("@") or email.endswith("@"):
        msg = "Invalid email format"
        raise ValueError(msg)
    local, domain = email.split("@", 1)
    if not local or "." not in domain or domain.startswith(".") or domain.endswith("."):
        msg = "Invalid email format"
        raise ValueError(msg)
    return email
