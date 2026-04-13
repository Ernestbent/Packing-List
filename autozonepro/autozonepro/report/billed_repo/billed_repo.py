import frappe
from frappe.utils import cint

def execute(filters=None):
    filters = filters or {}
    show_all_entries = cint(filters.get("show_all_entries", 1))

    if show_all_entries:
        return get_entry_columns(), get_entry_data(filters)

    return get_summary_columns(), get_summary_data(filters)


def get_summary_columns():
    return [
        {"label": "Code",                    "fieldname": "Code",                "fieldtype": "Link",     "options": "Item", "width": 120},
        {"label": "Brand",                   "fieldname": "Brand",               "fieldtype": "Data",     "width": 120},
        {"label": "Description",             "fieldname": "Description",         "fieldtype": "Data",     "width": 200},
        {"label": "Model",                   "fieldname": "Model",               "fieldtype": "Data",     "width": 120},

        {"label": "Buying Rate",             "fieldname": "Buying_Rate",         "fieldtype": "Currency", "width": 120},
        {"label": "Selling Rate",            "fieldname": "Selling_Rate",        "fieldtype": "Currency", "width": 120},

        ## Stock in the 3 known locations + total across all warehouses
        {"label": "Stock (Main & Containers)", "fieldname": "Stock",             "fieldtype": "Float",    "width": 180},
        {"label": "Total Stock",             "fieldname": "Total_Stock",         "fieldtype": "Float",    "width": 120},

        {"label": "Sold Quantity",           "fieldname": "Sold_Quantity",       "fieldtype": "Float",    "width": 120},
        {"label": "Returned Quantities",     "fieldname": "Returned_Quantities", "fieldtype": "Float",    "width": 150},

        {"label": "Gross Amount",            "fieldname": "Gross_Amount",        "fieldtype": "Currency", "width": 120},
        {"label": "Returns Amount",          "fieldname": "Returns_Amount",      "fieldtype": "Currency", "width": 120},
        {"label": "Net Amount",              "fieldname": "Net_Amount",          "fieldtype": "Currency", "width": 120},

        {"label": "Profit / Loss",           "fieldname": "Profit_Loss",         "fieldtype": "Currency", "width": 120},
    ]


def get_entry_columns():
    return [
        {"label": "Code",                    "fieldname": "Code",                "fieldtype": "Link",     "options": "Item", "width": 120},
        {"label": "Brand",                   "fieldname": "Brand",               "fieldtype": "Data",     "width": 120},
        {"label": "Description",             "fieldname": "Description",         "fieldtype": "Data",     "width": 220},
        {"label": "Model",                   "fieldname": "Model",               "fieldtype": "Data",     "width": 120},
        {"label": "Buying Rate",             "fieldname": "Buying_Rate",         "fieldtype": "Currency", "width": 120},
        {"label": "Selling Rate",            "fieldname": "Selling_Rate",        "fieldtype": "Currency", "width": 120},
        {"label": "Stock (Main & Containers)", "fieldname": "Stock",             "fieldtype": "Float",    "width": 180},
        {"label": "Total Stock",             "fieldname": "Total_Stock",         "fieldtype": "Float",    "width": 120},
        {"label": "Sold Quantity",           "fieldname": "Sold_Quantity",       "fieldtype": "Float",    "width": 120},
        {"label": "Returned Quantities",     "fieldname": "Returned_Quantities", "fieldtype": "Float",    "width": 150},
        {"label": "Gross Amount",            "fieldname": "Gross_Amount",        "fieldtype": "Currency", "width": 120},
        {"label": "Returns Amount",          "fieldname": "Returns_Amount",      "fieldtype": "Currency", "width": 120},
        {"label": "Qty",                     "fieldname": "Qty",                 "fieldtype": "Float",    "width": 100},
        {"label": "Price List Rate",         "fieldname": "Price_List_Rate",     "fieldtype": "Currency", "width": 120},
        {"label": "Rate",                    "fieldname": "Rate",                "fieldtype": "Currency", "width": 120},
        {"label": "Discount Amount",         "fieldname": "Discount_Amount",     "fieldtype": "Currency", "width": 130},
        {"label": "Net Amount",              "fieldname": "Net_Amount",          "fieldtype": "Currency", "width": 130},
        {"label": "Profit / Loss",           "fieldname": "Profit_Loss",         "fieldtype": "Currency", "width": 120},
    ]


def get_summary_conditions(filters):
    conditions = ""

    ## Filter by specific item
    if filters.get("item_code"):
        conditions += " AND i.item_code = %(item_code)s"

    ## Filter by item group
    if filters.get("item_group"):
        conditions += " AND i.item_group = %(item_group)s"

    ## Filter by brand
    if filters.get("brand"):
        conditions += " AND i.brand = %(brand)s"

    return conditions


def get_entry_conditions(filters):
    conditions = ""

    if filters.get("item_code"):
        conditions += " AND sii.item_code = %(item_code)s"

    if filters.get("item_group"):
        conditions += " AND i.item_group = %(item_group)s"

    if filters.get("brand"):
        conditions += " AND i.brand = %(brand)s"

    return conditions


def get_summary_data(filters):
    conditions = get_summary_conditions(filters)

    ## Date range applied to all invoice subqueries
    from_date = filters.get("from_date")
    to_date   = filters.get("to_date")

    ## Date condition reused across all invoice subqueries
    date_condition = ""
    if from_date:
        date_condition += " AND si.posting_date >= %(from_date)s"
    if to_date:
        date_condition += " AND si.posting_date <= %(to_date)s"

    return frappe.db.sql(f"""
        SELECT
            i.item_code                                     AS 'Code',
            i.brand                                         AS 'Brand',
            i.description                                   AS 'Description',
            i.custom_model                                  AS 'Model',

            COALESCE(
                NULLIF(latest_buying.buying_rate, 0),
                NULLIF(std_buying.standard_buying_rate, 0),
                0
            )                                               AS 'Buying_Rate',
            COALESCE(
                NULLIF(std_selling.standard_selling_rate, 0),
                NULLIF(latest_selling.selling_rate, 0),
                0
            )                                               AS 'Selling_Rate',

            -- Combined qty from the 3 known warehouse locations
            (
                COALESCE(stock.main_stock, 0)
                + COALESCE(stock.container_1, 0)
                + COALESCE(stock.container_2, 0)
            )                                               AS 'Stock',

            -- Total qty across ALL warehouses in the system
            COALESCE(all_stock.total_qty, 0)                AS 'Total_Stock',

            -- Net sold = gross sold minus returned
            (
                COALESCE(gross.qty_sold, 0)
                - COALESCE(returns.qty_returned, 0)
            )                                               AS 'Sold_Quantity',

            COALESCE(returns.qty_returned, 0)               AS 'Returned_Quantities',

            COALESCE(gross.total_gross, 0)                  AS 'Gross_Amount',
            COALESCE(returns.total_returns, 0)              AS 'Returns_Amount',

            -- Net amount = gross + returns (returns amount is negative)
            COALESCE(gross.total_gross, 0) + COALESCE(returns.total_returns, 0) AS 'Net_Amount',

            ROUND(
                (
                    COALESCE(
                        NULLIF(std_selling.standard_selling_rate, 0),
                        NULLIF(latest_selling.selling_rate, 0),
                        0
                    )
                    - COALESCE(
                        NULLIF(latest_buying.buying_rate, 0),
                        NULLIF(std_buying.standard_buying_rate, 0),
                        0
                    )
                )
                * (COALESCE(gross.qty_sold, 0) - COALESCE(returns.qty_returned, 0)),
            2)                                              AS 'Profit_Loss'

        FROM `tabItem` i

        -- Latest buying rate within date range from stock ledger
        LEFT JOIN (
            SELECT sle.item_code, MAX(sle.valuation_rate) AS buying_rate
            FROM `tabStock Ledger Entry` sle
            WHERE 1=1
              AND sle.posting_date >= %(from_date)s
              AND sle.posting_date <= %(to_date)s
            GROUP BY sle.item_code
        ) latest_buying ON latest_buying.item_code = i.item_code

        -- Standard Buying from Item Price (fallback when buying rate is missing/zero)
        LEFT JOIN (
            SELECT ranked.item_code, ranked.price_list_rate AS standard_buying_rate
            FROM (
                SELECT
                    ip.item_code,
                    ip.price_list_rate,
                    ROW_NUMBER() OVER (
                        PARTITION BY ip.item_code
                        ORDER BY
                            COALESCE(ip.valid_from, '1900-01-01') DESC,
                            ip.modified DESC,
                            ip.name DESC
                    ) AS rn
                FROM `tabItem Price` ip
                WHERE ip.price_list = 'Standard Buying'
                  AND ip.buying = 1
                  AND (ip.valid_from IS NULL OR ip.valid_from <= CURDATE())
            ) ranked
            WHERE ranked.rn = 1
        ) std_buying ON std_buying.item_code = i.item_code

        -- Latest selling rate within date range from submitted non-return invoices
        LEFT JOIN (
            SELECT sii.item_code, MAX(sii.rate) AS selling_rate
            FROM `tabSales Invoice Item` sii
            INNER JOIN `tabSales Invoice` si ON sii.parent = si.name
            WHERE si.docstatus = 1
              AND si.is_return = 0
              {date_condition}
            GROUP BY sii.item_code
        ) latest_selling ON latest_selling.item_code = i.item_code

        -- Standard Selling from Item Price (fallback when selling rate is missing/zero)
        LEFT JOIN (
            SELECT ranked.item_code, ranked.price_list_rate AS standard_selling_rate
            FROM (
                SELECT
                    ip.item_code,
                    ip.price_list_rate,
                    ROW_NUMBER() OVER (
                        PARTITION BY ip.item_code
                        ORDER BY
                            COALESCE(ip.valid_from, '1900-01-01') DESC,
                            ip.modified DESC,
                            ip.name DESC
                    ) AS rn
                FROM `tabItem Price` ip
                WHERE ip.price_list = 'Standard Selling'
                  AND ip.selling = 1
                  AND (ip.valid_from IS NULL OR ip.valid_from <= CURDATE())
            ) ranked
            WHERE ranked.rn = 1
        ) std_selling ON std_selling.item_code = i.item_code

        -- Stock split across the 3 known warehouse locations (live, no date filter)
        LEFT JOIN (
            SELECT
                bin.item_code,
                SUM(CASE WHEN bin.warehouse = 'Main Loc - APL'
                    THEN bin.actual_qty ELSE 0 END)                     AS main_stock,
                SUM(CASE WHEN bin.warehouse = 'Cont. No. 1 = MAEU-8382503 - APL'
                    THEN bin.actual_qty ELSE 0 END)                     AS container_1,
                SUM(CASE WHEN bin.warehouse = 'Cont. No. 2 = FTBU-8875500 - APL'
                    THEN bin.actual_qty ELSE 0 END)                     AS container_2
            FROM `tabBin` bin
            INNER JOIN `tabWarehouse` wh ON bin.warehouse = wh.name
            GROUP BY bin.item_code
        ) stock ON stock.item_code = i.item_code

        -- Total stock across every warehouse (live, no date filter)
        LEFT JOIN (
            SELECT item_code, SUM(actual_qty) AS total_qty
            FROM `tabBin`
            GROUP BY item_code
        ) all_stock ON all_stock.item_code = i.item_code

        -- Gross sales: qty and amount within date range
        LEFT JOIN (
            SELECT
                sii.item_code,
                SUM(sii.qty)    AS qty_sold,
                SUM(sii.amount) AS total_gross
            FROM `tabSales Invoice Item` sii
            INNER JOIN `tabSales Invoice` si ON sii.parent = si.name
            WHERE si.docstatus = 1
              AND si.is_return = 0
              {date_condition}
            GROUP BY sii.item_code
        ) gross ON gross.item_code = i.item_code

        -- Returns: qty and amount within date range
        LEFT JOIN (
            SELECT
                sii.item_code,
                SUM(ABS(sii.qty)) AS qty_returned,
                SUM(sii.amount)   AS total_returns
            FROM `tabSales Invoice Item` sii
            INNER JOIN `tabSales Invoice` si ON sii.parent = si.name
            WHERE si.docstatus = 1
              AND si.is_return = 1
              {date_condition}
            GROUP BY sii.item_code
        ) returns ON returns.item_code = i.item_code

        WHERE i.disabled = 0
        {conditions}

        ORDER BY Net_Amount DESC
    """, filters, as_dict=1)


def get_entry_data(filters):
    conditions = get_entry_conditions(filters)
    from_date = filters.get("from_date")
    to_date = filters.get("to_date")

    date_condition = ""
    if from_date:
        date_condition += " AND si.posting_date >= %(from_date)s"
    if to_date:
        date_condition += " AND si.posting_date <= %(to_date)s"

    return frappe.db.sql(f"""
        SELECT
            sii.item_code                                   AS 'Code',
            i.brand                                         AS 'Brand',
            i.description                                   AS 'Description',
            i.custom_model                                  AS 'Model',

            COALESCE(
                NULLIF(latest_buying.buying_rate, 0),
                NULLIF(std_buying.standard_buying_rate, 0),
                0
            )                                               AS 'Buying_Rate',
            COALESCE(
                NULLIF(sii.rate, 0),
                NULLIF(std_selling.standard_selling_rate, 0),
                0
            )                                               AS 'Selling_Rate',
            (
                COALESCE(stock.main_stock, 0)
                + COALESCE(stock.container_1, 0)
                + COALESCE(stock.container_2, 0)
            )                                               AS 'Stock',
            COALESCE(all_stock.total_qty, 0)                AS 'Total_Stock',
            SUM(CASE WHEN si.is_return = 0 THEN sii.qty ELSE 0 END) AS 'Sold_Quantity',
            SUM(CASE WHEN si.is_return = 1 THEN ABS(sii.qty) ELSE 0 END) AS 'Returned_Quantities',
            SUM(CASE WHEN si.is_return = 0 THEN sii.amount ELSE 0 END) AS 'Gross_Amount',
            SUM(CASE WHEN si.is_return = 1 THEN sii.amount ELSE 0 END) AS 'Returns_Amount',

            SUM(CASE WHEN si.is_return = 1 THEN -ABS(sii.qty) ELSE sii.qty END) AS 'Qty',
            MAX(sii.price_list_rate)                         AS 'Price_List_Rate',
            COALESCE(
                NULLIF(sii.rate, 0),
                NULLIF(std_selling.standard_selling_rate, 0),
                0
            )                                               AS 'Rate',
            SUM(COALESCE(sii.discount_amount, 0))           AS 'Discount_Amount',
            SUM(COALESCE(sii.net_amount, sii.amount, 0))    AS 'Net_Amount',
            ROUND(
                (
                    COALESCE(
                        NULLIF(sii.rate, 0),
                        NULLIF(std_selling.standard_selling_rate, 0),
                        0
                    )
                    - COALESCE(
                        NULLIF(latest_buying.buying_rate, 0),
                        NULLIF(std_buying.standard_buying_rate, 0),
                        0
                    )
                ) * SUM(CASE WHEN si.is_return = 1 THEN -ABS(sii.qty) ELSE sii.qty END),
                2
            )                                               AS 'Profit_Loss'
        FROM `tabSales Invoice Item` sii
        INNER JOIN `tabSales Invoice` si ON si.name = sii.parent
        LEFT JOIN `tabItem` i ON i.item_code = sii.item_code

        LEFT JOIN (
            SELECT sle.item_code, MAX(sle.valuation_rate) AS buying_rate
            FROM `tabStock Ledger Entry` sle
            WHERE sle.posting_date >= %(from_date)s
              AND sle.posting_date <= %(to_date)s
            GROUP BY sle.item_code
        ) latest_buying ON latest_buying.item_code = sii.item_code

        LEFT JOIN (
            SELECT ranked.item_code, ranked.price_list_rate AS standard_buying_rate
            FROM (
                SELECT
                    ip.item_code,
                    ip.price_list_rate,
                    ROW_NUMBER() OVER (
                        PARTITION BY ip.item_code
                        ORDER BY
                            COALESCE(ip.valid_from, '1900-01-01') DESC,
                            ip.modified DESC,
                            ip.name DESC
                    ) AS rn
                FROM `tabItem Price` ip
                WHERE ip.price_list = 'Standard Buying'
                  AND ip.buying = 1
                  AND (ip.valid_from IS NULL OR ip.valid_from <= CURDATE())
            ) ranked
            WHERE ranked.rn = 1
        ) std_buying ON std_buying.item_code = sii.item_code

        LEFT JOIN (
            SELECT ranked.item_code, ranked.price_list_rate AS standard_selling_rate
            FROM (
                SELECT
                    ip.item_code,
                    ip.price_list_rate,
                    ROW_NUMBER() OVER (
                        PARTITION BY ip.item_code
                        ORDER BY
                            COALESCE(ip.valid_from, '1900-01-01') DESC,
                            ip.modified DESC,
                            ip.name DESC
                    ) AS rn
                FROM `tabItem Price` ip
                WHERE ip.price_list = 'Standard Selling'
                  AND ip.selling = 1
                  AND (ip.valid_from IS NULL OR ip.valid_from <= CURDATE())
            ) ranked
            WHERE ranked.rn = 1
        ) std_selling ON std_selling.item_code = sii.item_code

        LEFT JOIN (
            SELECT
                bin.item_code,
                SUM(CASE WHEN bin.warehouse = 'Main Loc - APL' THEN bin.actual_qty ELSE 0 END) AS main_stock,
                SUM(CASE WHEN bin.warehouse = 'Cont. No. 1 = MAEU-8382503 - APL' THEN bin.actual_qty ELSE 0 END) AS container_1,
                SUM(CASE WHEN bin.warehouse = 'Cont. No. 2 = FTBU-8875500 - APL' THEN bin.actual_qty ELSE 0 END) AS container_2
            FROM `tabBin` bin
            GROUP BY bin.item_code
        ) stock ON stock.item_code = sii.item_code

        LEFT JOIN (
            SELECT item_code, SUM(actual_qty) AS total_qty
            FROM `tabBin`
            GROUP BY item_code
        ) all_stock ON all_stock.item_code = sii.item_code

        WHERE si.docstatus = 1
          {date_condition}
          {conditions}
        GROUP BY
            sii.item_code,
            i.brand,
            i.description,
            i.custom_model,
            latest_buying.buying_rate,
            std_buying.standard_buying_rate,
            std_selling.standard_selling_rate,
            stock.main_stock,
            stock.container_1,
            stock.container_2,
            all_stock.total_qty,
            COALESCE(NULLIF(sii.rate, 0), NULLIF(std_selling.standard_selling_rate, 0), 0)
        ORDER BY sii.item_code ASC, Rate DESC
    """, filters, as_dict=1)
