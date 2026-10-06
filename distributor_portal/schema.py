"""Standard DocType definitions. Bootstrap exports these through Frappe in developer mode."""


def f(name, kind="Data", options=None, **kw):
	return dict(
		fieldname=name,
		label=name.replace("_", " ").title(),
		fieldtype=kind,
		**({"options": options} if options else {}),
		**kw,
	)


SCHEMAS = []


def dt(name, fields, child=False, single=False, submit=False, **kw):
	SCHEMAS.append(
		dict(
			doctype="DocType",
			name=name,
			module="Distributor Portal",
			custom=0,
			istable=int(child),
			issingle=int(single),
			is_submittable=int(submit),
			engine="InnoDB",
			autoname="hash" if child else "format:DP-" + "".join(x[0] for x in name.split()) + "-{#####}",
			fields=fields,
			field_order=[x["fieldname"] for x in fields],
			track_changes=0 if child else 1,
			**kw,
		)
	)


dt("Partner Portal User", [f("user", "Link", "User", reqd=1, in_list_view=1)], child=True)
dt(
	"Partner Serial Item",
	[
		f("serial_no", "Link", "Partner Serial", reqd=1, in_list_view=1),
		f("item_code", "Link", "Item", read_only=1, in_list_view=1),
		f("length_m", "Float", read_only=1),
		f("decision", "Select", "Pending\nApproved\nRejected", default="Pending"),
		f("note", "Small Text"),
	],
	child=True,
)
dt(
	"Partner Order Item",
	[
		f("item_code", "Link", "Item", reqd=1, in_list_view=1),
		f("qty_reels", "Int", reqd=1, in_list_view=1),
		f("rate", "Currency", read_only=1, in_list_view=1),
		f("amount", "Currency", read_only=1),
		f("stock_qty", "Float", read_only=1),
		f("stock_uom", "Link", "UOM", read_only=1),
	],
	child=True,
)
dt(
	"Partner Declaration Item",
	[
		f("item_code", "Link", "Item", reqd=1, in_list_view=1),
		f("expected", "Int", read_only=1, in_list_view=1),
		f("counted", "Int", in_list_view=1),
		f("difference", "Int", read_only=1),
		f("treatment", "Select", "Sold, not scanned\nDamage", default="Sold, not scanned", in_list_view=1),
	],
	child=True,
)
dt(
	"Partner Forecast Item",
	[
		f("item_code", "Link", "Item", in_list_view=1),
		f("history", "Small Text"),
		f("forecast_qty", "Int", in_list_view=1),
		f("stock_qty", "Int"),
		f("in_transit", "Int"),
		f("projected_qty", "Int"),
		f("safety_qty", "Int"),
		f("suggested_qty", "Int", in_list_view=1),
	],
	child=True,
)
dt(
	"Distributor Portal Settings",
	[
		f("portal_title", default="Distributor Portal"),
		f("logo", "Attach Image"),
		f("accent_colour", "Color", default="#2563eb"),
		f("support_email"),
		f("support_phone"),
		f("company", "Link", "Company"),
		f("price_list", "Link", "Price List"),
		f("default_warehouse", "Link", "Warehouse"),
		f(
			"territory_rule",
			"Select",
			"Warn and flag HQ\nBlock the sale\nAllow, log only",
			default="Warn and flag HQ",
		),
		f("outlet_approval_required", "Check", default=1),
		f("declaration_due_day", "Int", default=5),
		f("damage_window_days", "Int", default=7),
		f("damage_photos_required", "Check", default=1),
		f(
			"credit_rule",
			"Select",
			"Hold for Accounts approval\nBlock submit",
			default="Hold for Accounts approval",
		),
		f("minimum_order_reels", "Int", default=1),
		f(
			"forecast_method",
			"Select",
			"Weighted moving average\nSimple moving average",
			default="Weighted moving average",
		),
		f("history_months", "Int", default=6),
		f("safety_stock_percent", "Percent", default=25),
		f("forecast_day", "Int", default=1),
	],
	single=True,
)
dt(
	"Channel Partner",
	[
		f("partner_name", reqd=1, in_list_view=1),
		f("customer", "Link", "Customer", reqd=1, unique=1, in_list_view=1),
		f("company", "Link", "Company", reqd=1),
		f("territory", "Link", "Territory", reqd=1, in_list_view=1),
		f("active", "Check", default=1),
		f("portal_users", "Table", "Partner Portal User"),
	],
	title_field="partner_name",
	search_fields="partner_name,customer",
)
dt(
	"Channel Outlet",
	[
		f("outlet_name", reqd=1, in_list_view=1),
		f("channel_partner", "Link", "Channel Partner", reqd=1, in_list_view=1),
		f("outlet_type", "Select", "Dealer\nRetailer\nSystem integrator\nProject", default="Dealer"),
		f("territory", "Link", "Territory", reqd=1, in_list_view=1),
		f("pincode"),
		f("address", "Small Text"),
		f("gstin"),
		f("approval_status", "Select", "Pending\nApproved\nRejected", default="Pending", in_list_view=1),
	],
	title_field="outlet_name",
	search_fields="outlet_name",
)
dt(
	"Partner Serial",
	[
		f("serial_no", "Link", "Serial No", reqd=1, unique=1, in_list_view=1),
		f("channel_partner", "Link", "Channel Partner", reqd=1, in_list_view=1),
		f("item_code", "Link", "Item", reqd=1, in_list_view=1),
		f("batch_no", "Link", "Batch"),
		f("length_m", "Float"),
		f(
			"status",
			"Select",
			"In transit\nIn stock\nSold\nReturn pending\nReturned\nDamaged",
			default="In transit",
			in_list_view=1,
		),
		f("delivery_note", "Link", "Delivery Note"),
		f("received_on", "Date"),
		f("sold_on", "Date"),
		f("sold_to", "Link", "Channel Outlet"),
		f("last_voucher"),
		f("return_previous_status"),
	],
	search_fields="serial_no,item_code",
)
dt(
	"Partner Stock Ledger",
	[
		f("channel_partner", "Link", "Channel Partner", reqd=1, in_list_view=1),
		f("item_code", "Link", "Item", reqd=1, in_list_view=1),
		f("serial_no", "Link", "Partner Serial"),
		f("posting_date", "Date", reqd=1, in_list_view=1),
		f("qty_reels", "Int"),
		f("qty_m", "Float"),
		f(
			"movement",
			"Select",
			"Dispatch\nReceipt\nSale\nSale-Declared\nReturn\nDamage\nReversal",
			reqd=1,
			in_list_view=1,
		),
		f("voucher_type"),
		f("voucher_no"),
		f("reversal_of", "Link", "Partner Stock Ledger"),
		f("entry_key", unique=1),
	],
)
dt(
	"Sell Out Entry",
	[
		f("channel_partner", "Link", "Channel Partner", reqd=1, in_list_view=1),
		f("outlet", "Link", "Channel Outlet", reqd=1, in_list_view=1),
		f("posting_date", "Date", default="Today", reqd=1, in_list_view=1),
		f("bill_no"),
		f("explanation", "Small Text"),
		f("items", "Table", "Partner Serial Item", reqd=1),
		f("total_reels", "Int", read_only=1),
		f("territory_flagged", "Check", read_only=1),
	],
	submit=True,
)
dt(
	"Stock Declaration",
	[
		f("channel_partner", "Link", "Channel Partner", reqd=1, in_list_view=1),
		f("period", "Date", reqd=1, in_list_view=1, description="First day of the month being declared"),
		f("method", "Select", "Scan\nCount", default="Scan"),
		f("period_key", unique=1, read_only=1),
		f("counted_serials", "Long Text", description="One serial per line"),
		f("items", "Table", "Partner Declaration Item"),
		f("notes", "Small Text"),
		f("total_difference", "Int", read_only=1),
	],
	submit=True,
)
dt(
	"Partner Order",
	[
		f("channel_partner", "Link", "Channel Partner", reqd=1, in_list_view=1),
		f("posting_date", "Date", default="Today", reqd=1),
		f("required_by", "Date", reqd=1),
		f("po_number"),
		f("shipping_address", "Link", "Address"),
		f("note", "Small Text"),
		f("items", "Table", "Partner Order Item", reqd=1),
		f("total", "Currency", read_only=1, in_list_view=1),
		f("currency", "Link", "Currency", read_only=1),
		f(
			"status",
			"Select",
			"Draft\nPending HQ approval\nCredit approval required\nApproved\nRejected",
			default="Draft",
			read_only=1,
			in_list_view=1,
			allow_on_submit=1,
		),
		f("credit_available", "Currency", read_only=1),
		f("sales_order", "Link", "Sales Order", read_only=1, allow_on_submit=1),
		f("resolution", "Small Text", read_only=1, allow_on_submit=1),
	],
	submit=True,
)
dt(
	"Partner Return",
	[
		f("channel_partner", "Link", "Channel Partner", reqd=1, in_list_view=1),
		f("posting_date", "Date", default="Today", reqd=1),
		f(
			"reason",
			"Select",
			"Damaged in transit\nManufacturing defect\nWrong item supplied\nUnsold / excess stock\nDamaged at godown",
			reqd=1,
			in_list_view=1,
		),
		f("description", "Small Text", reqd=1),
		f("photo", "Attach"),
		f("items", "Table", "Partner Serial Item", reqd=1),
		f(
			"status",
			"Select",
			"Draft\nSubmitted\nReceived\nInspected\nApproved\nRejected\nPartly approved",
			default="Draft",
			read_only=1,
			in_list_view=1,
			allow_on_submit=1,
		),
		f("credit_note", "Link", "Sales Invoice", allow_on_submit=1, read_only=1),
		f("resolution", "Small Text", allow_on_submit=1, read_only=1),
	],
	submit=True,
)
dt(
	"Territory Flag",
	[
		f("channel_partner", "Link", "Channel Partner", reqd=1, in_list_view=1),
		f("serial_no", "Link", "Partner Serial", in_list_view=1),
		f("outlet", "Link", "Channel Outlet", reqd=1),
		f("holder_territory", "Link", "Territory"),
		f("outlet_territory", "Link", "Territory", in_list_view=1),
		f("source_voucher"),
		f("status", "Select", "Open\nExplained\nAccepted\nAction taken", default="Open", in_list_view=1),
		f("explanation", "Small Text"),
		f("resolution", "Small Text"),
	],
)
dt(
	"Partner Forecast",
	[
		f("channel_partner", "Link", "Channel Partner", reqd=1, in_list_view=1),
		f("period", "Date", reqd=1, in_list_view=1),
		f("period_key", unique=1),
		f("generated_on", "Datetime"),
		f("method"),
		f("items", "Table", "Partner Forecast Item"),
		f("suggested_total", "Int", in_list_view=1),
	],
)
