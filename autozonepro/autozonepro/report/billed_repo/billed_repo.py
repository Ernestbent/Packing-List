import frappe

def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)
    return columns, data


def get_columns():
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


def get_conditions(filters):
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


def get_data(filters):
    conditions = get_conditions(filters)

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

            COALESCE(latest_buying.buying_rate, 0)          AS 'Buying_Rate',
            COALESCE(latest_selling.selling_rate, 0)        AS 'Selling_Rate',

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
                (COALESCE(latest_selling.selling_rate, 0) - COALESCE(latest_buying.buying_rate, 0))
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