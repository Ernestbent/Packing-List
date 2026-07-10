from autozonepro.autozonepro.custom_scripts.sales_order_hooks import validate as existing_validate
from autozonepro.autozonepro.custom_scripts.sales_order_item_limit import (
    validate_sales_order_item_limits,
)


def validate(doc, method=None):
    existing_validate(doc, method)
    validate_sales_order_item_limits(doc)
