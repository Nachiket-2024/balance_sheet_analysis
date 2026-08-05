import ipaddress
import traceback

from ....logging.logging_config import get_logger
from ..condition_handler import ConditionHandler

logger = get_logger(__name__)


class NetworkCondition(ConditionHandler):
    """
    "network": {"allowed_ips": ["10.0.0.0/8", "203.0.113.7"]}: the
    caller's IP (read from context["ip_address"], the only place this app
    surfaces the request's source IP into the condition-evaluation
    context) must match one of the listed single IPs or CIDR ranges.

    Fails safe (denies) if allowed_ips is empty, the context carries no
    ip_address at all, or either address string fails to parse, per
    missing IP context and invalid IP
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
            # Fails safe (see class docstring): a malformed IP/CIDR entry
            # denies rather than raising, but logged so a misconfigured
            # policy doesn't silently deny forever with no trail an
            # operator can find.
            logger.warning("network condition failed to evaluate, denying:\n%s", traceback.format_exc())
            return False
