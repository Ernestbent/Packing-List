from autozonepro.autozonepro.custom_scripts.sales_order_hooks import validate as existing_validate
from autozonepro.autozonepro.custom_scripts.sales_order_item_limit import (
    validate_sales_order_item_limits,
)
from autozonepro.autozonepro.custom_scripts.check_packing_lists import (
    before_update_after_submit as validate_start_packing_prerequisites,
)
from autozonepro.autozonepro.custom_scripts.sales_order_pick_list_stock import (
    validate as validate_pick_list_stock,
    before_update_after_submit as validate_pick_list_stock_transition,
)


def validate(doc, method=None):
    existing_validate(doc, method)
    validate_pick_list_stock(doc, method)
    validate_sales_order_item_limits(doc)


def before_update_after_submit(doc, method=None):
    validate_pick_list_stock_transition(doc, method)
    validate_start_packing_prerequisites(doc, method)
