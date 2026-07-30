from ..core.settings import settings

# Verification and password-reset emails render the same table-based HTML
# skeleton (tables rather than flex/grid because Outlook's rendering engine,
# Word, ignores modern CSS layout). Keeping this in one place means branding,
# footer, and client-compatibility fixes only need to be made once.


def render_transactional_email(
    *,
    preheader: str,
    heading: str,
    accent_color: str,
    intro: str,
    cta_label: str,
    cta_url: str,
    expiry_note: str,
    ignore_note: str,
) -> str:
    """
    Renders a branded transactional HTML email.

    preheader: short summary shown in inbox preview text (hidden in the body).
    heading: main heading below the brand mark (e.g. "Verify your email").
    accent_color: hex color for the heading rule and CTA button.
    cta_url: destination URL, built by the caller from settings.FRONTEND_BASE_URL.

    Returns the complete HTML document string, ready to pass to send_email_task.
    """
    support_email = settings.SUPPORT_EMAIL or settings.FROM_EMAIL

    return f"""\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{heading}</title>
</head>
<body style="margin:0; padding:0; background-color:#f4f5f7; font-family:Arial, Helvetica, sans-serif;">
    <div style="display:none; max-height:0; overflow:hidden; opacity:0;">{preheader}</div>
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color:#f4f5f7; padding:24px 0;">
        <tr>
            <td align="center">
                <table role="presentation" width="600" cellpadding="0" cellspacing="0" style="max-width:600px; width:100%; background-color:#ffffff; border-radius:8px; overflow:hidden; border:1px solid #e0e0e0;">
                    <tr>
                        <td style="padding:24px 32px 8px 32px;">
                            <div style="font-size:20px; font-weight:bold; color:#2c3e50;">{settings.APP_NAME}</div>
                            <div style="font-size:12px; color:#999999; margin-top:2px;">Secure access, centrally managed</div>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding:16px 32px 0 32px;">
                            <h1 style="font-size:20px; color:#2c3e50; margin:0 0 16px 0; padding-bottom:12px; border-bottom:2px solid {accent_color};">{heading}</h1>
                            <p style="font-size:15px; line-height:1.6; color:#333333; margin:0 0 24px 0;">{intro}</p>
                        </td>
                    </tr>
                    <tr>
                        <td align="center" style="padding:0 32px 24px 32px;">
                            <a href="{cta_url}" style="background-color:{accent_color}; color:#ffffff; padding:12px 28px; text-decoration:none; border-radius:4px; font-weight:bold; font-size:15px; display:inline-block;">{cta_label}</a>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding:0 32px 24px 32px;">
                            <p style="font-size:13px; color:#666666; margin:0 0 4px 0;">If the button doesn't work, copy and paste this link into your browser:</p>
                            <p style="font-size:13px; color:{accent_color}; word-break:break-all; margin:0;">{cta_url}</p>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding:0 32px;">
                            <hr style="border:none; border-top:1px solid #e0e0e0; margin:0 0 20px 0;">
                        </td>
                    </tr>
                    <tr>
                        <td style="padding:0 32px 24px 32px;">
                            <p style="font-size:12px; color:#999999; margin:0 0 8px 0;">{expiry_note}</p>
                            <p style="font-size:12px; color:#999999; margin:0;">{ignore_note}</p>
                        </td>
                    </tr>
                    <tr>
                        <td style="background-color:#f4f5f7; padding:20px 32px; border-top:1px solid #e0e0e0;">
                            <p style="font-size:12px; color:#999999; margin:0 0 4px 0;">Need help? Contact us at <a href="mailto:{support_email}" style="color:#666666;">{support_email}</a></p>
                            <p style="font-size:12px; color:#999999; margin:0;">&copy; {settings.APP_NAME}. This is an automated message.</p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>
"""
