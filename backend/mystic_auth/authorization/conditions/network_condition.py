import ipaddress

from .condition_handler import ConditionHandler


class NetworkCondition(ConditionHandler):
    """
    "network": {"allowed_ips": ["10.0.0.0/8", "203.0.113.7"]}: the
    caller's IP (read from context["ip_address"], the only place this app
    surfaces the request's source IP into the condition-evaluation
    context) must match one of the listed single IPs or CIDR ranges.

    Fails safe (denies) if allowed_ips is empty, the context carries no
    ip_address at all, or either address string fails to parse, per
    claude.md's explicit "missing IP context denial" / "invalid IP
    rejection" requirements.
    """

    def evaluate(self, condition_value, user_email, resource, context) -> bool:
        try:
            allowed_ips = condition_value.get("allowed_ips")
            if not allowed_ips:
                return False

            caller_ip = (context or {}).get("ip_address")
            if not caller_ip:
                return False
            caller_address = ipaddress.ip_address(caller_ip)

            for entry in allowed_ips:
                if "/" in entry:
                    if caller_address in ipaddress.ip_network(entry, strict=False):
                        return True
                elif caller_address == ipaddress.ip_address(entry):
                    return True
            return False
        except Exception:
            return False
