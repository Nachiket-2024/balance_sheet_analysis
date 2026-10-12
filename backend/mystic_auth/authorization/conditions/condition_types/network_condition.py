import ipaddress
import traceback

from ....logging.logging_config import get_logger
from ..condition_handler import ConditionHandler

logger = get_logger(__name__)


class NetworkCondition(ConditionHandler):
    """{"allowed_ips": ["10.0.0.0/8", "203.0.113.7"]}: the caller's IP
    (from context["ip_address"]) must match one of the listed IPs or CIDR
    ranges. Denies if allowed_ips or ip_address is missing, or either
    address string fails to parse.
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
            # Logged so a misconfigured policy's silent denial is traceable.
            logger.warning("network condition failed to evaluate, denying:\n%s", traceback.format_exc())
            return False
