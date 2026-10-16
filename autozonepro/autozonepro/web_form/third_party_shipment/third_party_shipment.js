frappe.ready(function () {
	const delivery_note_name = new URLSearchParams(window.location.search)
		.get("delivery_note")
		?.trim();
	const delivery_note_field = frappe.web_form.fields_dict.delivery_note;
	const customer_field = frappe.web_form.fields_dict.customer;
	const web_form = $(".web-form");
	let shipment_check_pending = Boolean(delivery_note_name);
	let shipment_already_submitted = false;

	function show_already_submitted(delivery_note) {
		shipment_already_submitted = true;
		web_form.hide();
		$(".web-form-introduction").hide();
		$(".shipment-already-submitted").remove();
		$(
			`<div class="shipment-already-submitted">
				<h3>${__("Courier Details Already Submitted")}</h3>
				<p>${__("Courier details for Delivery Note {0} have already been recorded.", [
					`<strong>${frappe.utils.escape_html(delivery_note)}</strong>`,
				])}</p>
				<p>${__("No further action is required.")}</p>
			</div>`
		).insertAfter(".web-form-header");
	}

	if (delivery_note_name && delivery_note_field) {
		web_form.hide();
		delivery_note_field.set_value(delivery_note_name);
		delivery_note_field.df.read_only = 1;
		delivery_note_field.refresh();

		if (customer_field) {
			customer_field.df.read_only = 1;
			customer_field.refresh();
		}

		frappe.call({
			method:
				"autozonepro.autozonepro.web_form.third_party_shipment.third_party_shipment.get_delivery_note_customer",
			args: { delivery_note: delivery_note_name },
			callback: function (response) {
				shipment_check_pending = false;
				if (response.message?.already_submitted) {
					show_already_submitted(delivery_note_name);
					return;
				}
				if (response.message?.customer && customer_field) {
					customer_field.set_value(response.message.customer);
				}
				web_form.show();
			},
			error: function () {
				shipment_check_pending = false;
				web_form.show();
			},
		});
	}

	const date_field = frappe.web_form.fields_dict.date;
	const time_field = frappe.web_form.fields_dict.time;

	const date_value = date_field && date_field.get_value();
	const time_value = time_field && time_field.get_value();

	if (date_field && (!date_value || String(date_value).toLowerCase() === "today")) {
		date_field.set_value(frappe.datetime.get_today());
	}
	if (time_field && (!time_value || String(time_value).toLowerCase() === "now")) {
		time_field.set_value(frappe.datetime.now_time());
	}

	const bundle_table = frappe.web_form.fields_dict.table_qwyw;
	if (!bundle_table || !bundle_table.grid) return;

	const existing_rows = bundle_table.get_value() || [];
	const bundle_html = $(
		`<div class="shipment-bundles form-group">
			<label class="control-label">
				${__("Number of Bundles")} <span class="text-danger">*</span>
			</label>
			<input class="form-control bundle-count" type="number" min="1" max="100" inputmode="numeric">
			<p class="help-box small text-muted">${__("Enter the number of tyre bundles.")}</p>
			<label class="control-label bundle-rate-label">
				${__("@ Expense per Bundle (UGX)")} <span class="text-muted">${__("(Optional)")}</span>
			</label>
			<input class="form-control bundle-unit-expense" type="number" min="0" step="1" inputmode="decimal">
			<p class="help-box small text-muted">${__("Enter one amount to apply the same expense to every bundle, or leave it blank to enter each expense separately.")}</p>
			<div class="bundle-list"></div>
		</div>`
	);

	bundle_html.insertBefore(bundle_table.$wrapper);
	bundle_table.$wrapper.hide();

	const count_input = bundle_html.find(".bundle-count");
	const unit_expense_input = bundle_html.find(".bundle-unit-expense");
	const bundle_list = bundle_html.find(".bundle-list");

	function unit_expense() {
		return String(unit_expense_input.val() ?? "").trim();
	}

	function current_expenses() {
		return bundle_list
			.find(".bundle-expense")
			.map(function () {
				return $(this).val();
			})
			.get();
	}

	function sync_child_table() {
		const rows = bundle_list
			.find(".bundle-row")
			.map(function (index) {
				const expense = $(this).find(".bundle-expense").val();
				return {
					idx: index + 1,
					bundle: `Bundle ${index + 1}`,
					expense: expense === "" ? 0 : flt(expense),
				};
			})
			.get();

		bundle_table.df.data = rows;
		bundle_table.grid.df.data = rows;
		frappe.web_form.make_form_dirty();
	}

	function render_bundles(value, initial_expenses = []) {
		const previous_expenses = current_expenses();
		const expenses = previous_expenses.length ? previous_expenses : initial_expenses;
		const count = Math.min(100, Math.max(0, cint(value)));
		const shared_expense = unit_expense();

		bundle_list.empty();
		for (let index = 0; index < count; index++) {
			const expense = shared_expense || expenses[index] || "";
			bundle_list.append(
				`<div class="bundle-row">
					<div class="bundle-label">${__("Bundle")} ${index + 1}</div>
					<label>
						<span>${__("Expense (UGX)")}</span>
						<input class="form-control bundle-expense" type="number" min="0" step="1" inputmode="decimal" value="${frappe.utils.escape_html(String(expense))}" ${shared_expense ? "disabled" : ""}>
					</label>
				</div>`
			);
		}

		sync_child_table();
	}

	count_input.on("input", function () {
		let count = cint($(this).val());
		if (count > 100) {
			count = 100;
			$(this).val(count);
		}
		render_bundles(count);
	});

	unit_expense_input.on("input", function () {
		const expense = unit_expense();
		const expense_inputs = bundle_list.find(".bundle-expense");
		if (expense) {
			expense_inputs.val(expense).prop("disabled", true);
		} else {
			expense_inputs.prop("disabled", false);
		}
		sync_child_table();
	});

	bundle_list.on("input", ".bundle-expense", sync_child_table);

	if (existing_rows.length) {
		count_input.val(existing_rows.length);
		render_bundles(
			existing_rows.length,
			existing_rows.map((row) => row.expense ?? "")
		);
	}

	frappe.web_form.validate = function () {
		if (shipment_check_pending || shipment_already_submitted) {
			return false;
		}
		if (cint(count_input.val()) < 1) {
			frappe.msgprint(__("Please enter at least one bundle."));
			count_input.trigger("focus");
			return false;
		}

		sync_child_table();
		return true;
	};
});
