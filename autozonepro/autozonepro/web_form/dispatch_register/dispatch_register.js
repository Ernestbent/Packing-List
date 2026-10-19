frappe.ready(function() {
	const delivery_note_input =
		'.grid-body [data-fieldname="delivery_note"] input[data-fieldtype="Link"], ' +
		'.grid-body [data-fieldname="delivery_note"] input';
	const expense_inputs =
		'.grid-body [data-fieldname="number_of_bundles"] input, ' +
		'.grid-body [data-fieldname="total_expense"] input';
	const history_inputs =
		'.grid-body [data-fieldname="driver_name"] input, ' +
		'.grid-body [data-fieldname="telephone"] input';
	const history_fields = new Set(["driver_name", "telephone"]);
	const history_suggestion_method =
		"autozonepro.autozonepro.doctype.dispatch_register.dispatch_register.get_dispatch_history_suggestions";

	function position_delivery_note_dropdown(input) {
		const $input = $(input);
		const $list = $input.closest(".awesomplete").children("ul");
		if (!$list.length) return;

		const rect = input.getBoundingClientRect();
		const viewport_padding = 12;
		const preferred_width = Math.max(rect.width, 360);
		const width = Math.min(preferred_width, window.innerWidth - viewport_padding * 2);
		const left = Math.max(
			viewport_padding,
			Math.min(rect.left, window.innerWidth - width - viewport_padding)
		);
		const room_below = window.innerHeight - rect.bottom - viewport_padding;
		const room_above = rect.top - viewport_padding;
		const open_above = room_below < 180 && room_above > room_below;
		const available_height = Math.max(
			140,
			Math.min(300, open_above ? room_above - 6 : room_below - 6)
		);
		const top = open_above
			? Math.max(viewport_padding, rect.top - available_height - 4)
			: rect.bottom + 4;

		$list.addClass("dispatch-floating-link-options").css({
			left: `${left}px`,
			top: `${top}px`,
			width: `${width}px`,
			maxHeight: `${available_height}px`,
		});
	}

	function schedule_dropdown_position(input) {
		window.requestAnimationFrame(() => position_delivery_note_dropdown(input));
		window.setTimeout(() => position_delivery_note_dropdown(input), 80);
	}

	function get_history_query(fieldname) {
		return {
			query: history_suggestion_method,
			params: { fieldname },
		};
	}

	function apply_history_query_to_input(input) {
		const fieldname = $(input).attr("data-fieldname");
		if (!history_fields.has(fieldname)) return;

		const grid_row = $(input).closest(".grid-row").data("grid_row");
		const field = grid_row?.on_grid_fields_dict?.[fieldname];
		if (!field) return;

		field.df.ignore_validation = true;
		field.get_query = () => get_history_query(fieldname);
	}

	function setup_history_autocomplete(attempt = 0) {
		const rows_field = frappe.web_form?.fields_dict?.rows;
		if (!rows_field?.grid) {
			if (attempt < 20) {
				window.setTimeout(() => setup_history_autocomplete(attempt + 1), 100);
			}
			return;
		}
		if (rows_field.grid.dispatch_history_autocomplete_ready) return;
		rows_field.grid.dispatch_history_autocomplete_ready = true;

		history_fields.forEach((fieldname) => {
			const grid_field = rows_field.grid.get_field(fieldname);
			if (!grid_field) return;
			grid_field.ignore_validation = true;
			grid_field.get_query = () => get_history_query(fieldname);
		});

		(rows_field.grid.grid_rows || []).forEach((grid_row) => {
			history_fields.forEach((fieldname) => {
				const field = grid_row.on_grid_fields_dict?.[fieldname];
				if (!field) return;
				field.df.ignore_validation = true;
				field.get_query = () => get_history_query(fieldname);
			});
		});
	}

	async function populate_customer_name(input) {
		const grid_row = $(input).closest(".grid-row").data("grid_row");
		const delivery_note = (input.value || grid_row?.doc?.delivery_note || "").trim();
		if (!grid_row?.doc) return;
		if (!delivery_note) {
			grid_row.doc.customer_name = "";
			grid_row.refresh_field("customer_name");
			return;
		}

		const request_id = `${delivery_note}:${Date.now()}`;
		$(input).data("customer-fetch-request", request_id);

		try {
			const response = await frappe.call({
				method:
					"autozonepro.autozonepro.doctype.dispatch_register.dispatch_register.get_delivery_note_customer",
				args: { delivery_note },
			});

			if ($(input).data("customer-fetch-request") !== request_id) return;
			if ((input.value || "").trim() !== delivery_note) return;

			grid_row.doc.customer_name = response.message || "";
			grid_row.refresh_field("customer_name");
			frappe.web_form.make_form_dirty();
		} catch (error) {
			if ($(input).data("customer-fetch-request") !== request_id) return;
			grid_row.doc.customer_name = "";
			grid_row.refresh_field("customer_name");
		}
	}

	function schedule_customer_name(input) {
		window.clearTimeout($(input).data("customer-fetch-timer"));
		const timer = window.setTimeout(() => populate_customer_name(input), 150);
		$(input).data("customer-fetch-timer", timer);
	}

	function get_row_input_value(grid_row, fieldname) {
		const field = grid_row.on_grid_fields_dict?.[fieldname];
		if (field?.$input?.length) return field.$input.val();
		return grid_row.doc[fieldname];
	}

	function update_cost_per_bundle(input) {
		const grid_row = $(input).closest(".grid-row").data("grid_row");
		if (!grid_row?.doc) return;

		const bundles = Math.trunc(flt(get_row_input_value(grid_row, "number_of_bundles")));
		const total_expense = flt(get_row_input_value(grid_row, "total_expense"));
		const cost_per_bundle = bundles > 0 ? flt(total_expense / bundles, 2) : 0;

		grid_row.doc.cost_per_bundle = cost_per_bundle;
		grid_row.refresh_field("cost_per_bundle");
	}

	function get_delivery_note_query() {
		return {
			query:
				"autozonepro.autozonepro.doctype.dispatch_register.dispatch_register.get_dispatch_ready_delivery_notes",
			filters: {
				posting_date: frappe.web_form?.fields_dict?.date_time?.get_value() || "",
			},
		};
	}

	function apply_delivery_note_query_to_input(input) {
		const grid_row = $(input).closest(".grid-row").data("grid_row");
		const field = grid_row?.on_grid_fields_dict?.delivery_note;
		if (!field) return;

		field.get_query = get_delivery_note_query;
		if (field.$input?.length) field.$input.cache = {};
	}

	function setup_delivery_note_query(attempt = 0) {
		const web_form = frappe.web_form;
		const date_field = web_form?.fields_dict?.date_time;
		const rows_field = web_form?.fields_dict?.rows;
		const delivery_note_field = rows_field?.grid?.get_field("delivery_note");

		if (!date_field || !rows_field?.grid || !delivery_note_field) {
			if (attempt < 20) {
				window.setTimeout(() => setup_delivery_note_query(attempt + 1), 100);
			}
			return;
		}
		if (rows_field.grid.dispatch_delivery_note_query_ready) return;
		rows_field.grid.dispatch_delivery_note_query_ready = true;

		delivery_note_field.get_query = get_delivery_note_query;
		(rows_field.grid.grid_rows || []).forEach((grid_row) => {
			const field = grid_row.on_grid_fields_dict?.delivery_note;
			if (field) field.get_query = get_delivery_note_query;
		});

		const existing_change = date_field.df.change;
		date_field.df.change = function (...args) {
			if (existing_change) existing_change.apply(this, args);
			$(delivery_note_input).each(function () {
				apply_delivery_note_query_to_input(this);
			});

			let cleared = false;
			(rows_field.grid.get_data() || []).forEach((row) => {
				if (row.delivery_note || row.customer_name) {
					row.delivery_note = "";
					row.customer_name = "";
					row.sales_order = "";
					row.third_party_shipment = "";
					row.row_status = "Pending";
					cleared = true;
				}
			});

			if (cleared) {
				rows_field.grid.refresh();
				web_form.make_form_dirty();
				frappe.show_alert({
					message: __("Delivery Notes were cleared. Select notes for the new date."),
					indicator: "orange",
				});
			}
		};
	}

	function setup_dispatch_list_filters(attempt = 0) {
		if (!window.location.pathname.endsWith("/list")) return;
		if (!frappe.web_form_list) {
			if (attempt < 20) {
				window.setTimeout(() => setup_dispatch_list_filters(attempt + 1), 100);
			}
			return;
		}
		if ($(".dispatch-register-list-filters").length) return;

		const list = frappe.web_form_list;
		const $filter_area = $(".web-list-filters");
		$filter_area
			.removeClass("hide")
			.addClass("dispatch-register-list-filters")
			.html(`
				<div class="dispatch-filter-field">
					<label for="dispatch-filter-customer">Customer</label>
					<input id="dispatch-filter-customer" class="form-control" type="search" placeholder="Customer name">
				</div>
				<div class="dispatch-filter-field">
					<label for="dispatch-filter-date">Date</label>
					<input id="dispatch-filter-date" class="form-control" type="date">
				</div>
				<div class="dispatch-filter-field">
					<label for="dispatch-filter-delivery-note">Delivery Note</label>
					<input id="dispatch-filter-delivery-note" class="form-control" type="search" placeholder="Delivery Note number">
				</div>
				<div class="dispatch-filter-actions">
					<button type="button" class="btn btn-secondary btn-sm dispatch-clear-filters">Clear filters</button>
				</div>
			`);

		const filter_values = () => ({
			customer: $("#dispatch-filter-customer").val().trim(),
			dispatch_date: $("#dispatch-filter-date").val(),
			delivery_note: $("#dispatch-filter-delivery-note").val().trim(),
		});

		list.fetch_data = function () {
			return frappe.call({
				method:
					"autozonepro.autozonepro.doctype.dispatch_register.dispatch_register.get_dispatch_register_list",
				args: {
					...filter_values(),
					limit_start: this.web_list_start,
					limit: this.page_length,
				},
			});
		};

		let refresh_timer;
		const refresh_list = () => {
			window.clearTimeout(refresh_timer);
			refresh_timer = window.setTimeout(() => list.refresh(), 300);
		};

		$filter_area.on(
			"input",
			"#dispatch-filter-customer, #dispatch-filter-delivery-note",
			refresh_list
		);
		$filter_area.on("change", "#dispatch-filter-date", () => list.refresh());
		$filter_area.on("click", ".dispatch-clear-filters", function () {
			$filter_area.find("input").val("");
			list.refresh();
		});

		list.refresh();
	}

	$(document).on(
		"pointerdown touchstart",
		delivery_note_input,
		function () {
			apply_delivery_note_query_to_input(this);
		}
	);

	$(document).on(
		"focus input keyup click awesomplete-open",
		delivery_note_input,
		function (event) {
			apply_delivery_note_query_to_input(this);
			if (
				event.type === "focus" &&
				document.activeElement === this &&
				!frappe.web_form?.fields_dict?.date_time?.get_value()
			) {
				frappe.show_alert({
					message: __("Select a Date before choosing a Delivery Note."),
					indicator: "orange",
				});
			}
			if (event.type === "focus") $(this).trigger("input");
			schedule_dropdown_position(this);
		}
	);

	$(document).on(
		"change awesomplete-selectcomplete",
		delivery_note_input,
		function () {
			schedule_customer_name(this);
		}
	);

	$(document).on(
		"pointerdown touchstart focus input awesomplete-open",
		history_inputs,
		function () {
			apply_history_query_to_input(this);
			if (document.activeElement === this) schedule_dropdown_position(this);
		}
	);

	$(document).on("input change", expense_inputs, function () {
		update_cost_per_bundle(this);
	});

	$(window).on("resize scroll", function () {
		const input = document.activeElement;
		if ($(input).is(`${delivery_note_input}, ${history_inputs}`)) {
			schedule_dropdown_position(input);
		}
	});

	$(document).on("scroll", ".form-grid-container", function () {
		const input = document.activeElement;
		if ($(input).is(`${delivery_note_input}, ${history_inputs}`)) {
			schedule_dropdown_position(input);
		}
	});

	setup_delivery_note_query();
	setup_history_autocomplete();
	setup_dispatch_list_filters();
});
