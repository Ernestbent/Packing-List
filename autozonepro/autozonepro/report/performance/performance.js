// Copyright (c) 2026, Ernest Benedict and contributors
// For license information, please see license.txt

frappe.query_reports["Performance"] = {
	filters: [],

	formatter: function(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);

		if (!data) {
			return value;
		}

		if (column.fieldname === "section") {
			if (data.section === "DISPATCH DEPT") {
				return `<span style="font-weight:700;color:#1f4e79;">${value}</span>`;
			}
			if (data.section === "STORES EXECUTIVES") {
				return `<span style="font-weight:700;color:#2f6f3e;">${value}</span>`;
			}
		}

		if (column.fieldname === "category") {
			const isMain = ["CENTRAL", "UP COUNTRY", "ALL STORES"].includes((data.category || "").toUpperCase());
			if (isMain) {
				return `<span style="font-weight:700;">${value}</span>`;
			}
		}

		if (column.fieldname === "total_weighted_score" && data.total_weighted_score !== null && data.total_weighted_score !== undefined) {
			const score = flt(data.total_weighted_score);
			let color = "#b42318";
			if (score >= 0.85) {
				color = "#067647";
			} else if (score >= 0.70) {
				color = "#b54708";
			}
			return `<span style="font-weight:700;color:${color};">${value}</span>`;
		}

		if (column.fieldname === "total_weighted_pct" && data.total_weighted_pct !== null && data.total_weighted_pct !== undefined) {
			const pct = flt(data.total_weighted_pct);
			let color = "#b42318";
			if (pct >= 85) {
				color = "#067647";
			} else if (pct >= 70) {
				color = "#b54708";
			}
			return `<span style="font-weight:700;color:${color};">${value}</span>`;
		}

		return value;
	}
};
