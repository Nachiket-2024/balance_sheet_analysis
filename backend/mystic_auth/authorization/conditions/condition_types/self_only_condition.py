from ..condition_handler import ConditionHandler
from ..resource_field import get_field


class SelfOnlyCondition(ConditionHandler):
    """
    "self_only": true: the resource's owning identity (its "email") must
    match the acting user's own email. A falsy value (false, missing,
    None) means this condition imposes no restriction. Unsatisfiable
    (denied) if no resource was supplied at all, since an ownership
    condition with nothing to check ownership against cannot be assumed true.
    """

    def evaluate(self, condition_value, user_email, resource, context) -> bool:
        if not condition_value:
            return True
        if resource is None:
            return False
        owner_email = get_field(resource, "email")
        return owner_email == user_email
