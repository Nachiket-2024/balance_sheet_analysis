/**
 * Turns a raw User-Agent string into a short "Browser on OS" label for the
 * Manage Sessions card - good enough for a display list, not a security
 * control (a client can send any UA string it likes). No UA-parser
 * dependency exists on either side of this app (grepped both
 * package.json/requirements before adding this), and a full parser is more
 * than a one-line device label needs.
 */
export function parseUserAgent(userAgent: string | null): string {
    if (!userAgent) return "Unknown device";

    const ua = userAgent;

    let browser = "Unknown browser";
    if (/edg\//i.test(ua)) browser = "Edge";
    else if (/opr\//i.test(ua) || /opera/i.test(ua)) browser = "Opera";
    else if (/chrome|crios/i.test(ua)) browser = "Chrome";
    else if (/firefox|fxios/i.test(ua)) browser = "Firefox";
    else if (/safari/i.test(ua)) browser = "Safari";

    let os = "Unknown OS";
    if (/windows/i.test(ua)) os = "Windows";
    else if (/iphone|ipad|ipod/i.test(ua)) os = "iOS";
    else if (/mac os x/i.test(ua)) os = "macOS";
    else if (/android/i.test(ua)) os = "Android";
    else if (/linux/i.test(ua)) os = "Linux";

    return `${browser} on ${os}`;
}
