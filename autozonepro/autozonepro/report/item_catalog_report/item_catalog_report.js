frappe.query_reports["Item Catalog Report"] = {

    filters: [
        {
            fieldname: "item_group",
            label: "Item Group",
            fieldtype: "Link",
            options: "Item Group"
        },
        {
            fieldname: "item_code",
            label: "Item Code",
            fieldtype: "Link",
            options: "Item"
        }
    ],

    after_datatable_render(datatable) {
        const data = frappe.query_report.data;
        if (!data || !data.length) return;

        // Inject print styles once into page head
        if (!document.getElementById("item-catalog-print-style")) {
            const style = document.createElement("style");
            style.id = "item-catalog-print-style";
            style.innerHTML = `
                @media print {
                    .navbar, .sidebar, .page-actions,
                    .report-filter-section, .datatable {
                        display: none !important;
                    }
                    .item-catalog-grid {
                        display: flex !important;
                        flex-wrap: wrap;
                        gap: 10px;
                        padding: 10px;
                        background: #fff !important;
                    }
                    .item-catalog-grid > div {
                        page-break-inside: avoid;
                        width: 160px;
                    }
                }
            `;
            document.head.appendChild(style);
        }

        // Remove any previously injected catalog render
        $(".item-catalog-grid").remove();

        // Build card grid HTML
        let cards = data.map(row => {
            const img = row.image
                ? `<img src="${row.image}"
                        style="width:100%; height:130px; object-fit:contain; border-bottom:1px solid #ddd; padding:6px;"
                        onerror="this.style.display='none'">`
                : `<div style="height:130px; background:#f9f9f9; display:flex;
                        align-items:center; justify-content:center;
                        color:#bbb; font-size:11px; border-bottom:1px solid #ddd;">
                        No Image
                   </div>`;

            return `
                <div style="width:180px; border:1px solid #ddd; background:#fff; page-break-inside:avoid;">
                    ${img}
                    <div style="padding:8px;">
                        <div style="font-size:12px; font-weight:600; color:#222;">${row.item_code}</div>
                        <div style="font-size:11px; color:#555; margin-top:2px;">${row.item_name}</div>
                        <div style="font-size:10px; color:#888; margin-top:4px;">
                            ${row.item_group || ""} &nbsp;|&nbsp; ${row.stock_uom || ""}
                        </div>
                    </div>
                </div>`;
        }).join("");

        // Wrap all cards in a flex container
        const grid = `
            <div class="item-catalog-grid"
                 style="display:flex; flex-wrap:wrap; gap:12px; padding:16px; background:#f4f4f4;">
                ${cards}
            </div>`;

        // Inject grid after the report datatable
        $(frappe.query_report.$report_wrapper).find(".report-wrapper").after(grid);
    },

    // Pass through default datatable options unchanged
    get_datatable_options(options) {
        return options;
    }
};