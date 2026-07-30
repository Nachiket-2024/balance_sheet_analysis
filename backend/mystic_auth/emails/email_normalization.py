def normalize_email(email: str) -> str:
    """Canonicalizes an email address for storage/lookup so that
    `User@Example.com` and `user@example.com` are treated as the same
    account. Casing carries no meaning in the local-part or domain for the
    providers this app supports, so a straight lowercase is sufficient;
    no Unicode/IDNA normalization is attempted."""
    return email.strip().lower()
