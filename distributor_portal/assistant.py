"""Read-only fixed questions answered from authorized portal records."""

import frappe
from frappe.rate_limiter import rate_limit
from frappe.utils import add_months, get_first_day, today

from distributor_portal import domain as d
from distributor_portal.permissions import is_manager, partner_names, require_partner


@frappe.whitelist(methods=["POST"])
@rate_limit(limit=30, seconds=60)
def ask(question: str, partner: str = ""):
	question = question.strip()
	if not question or len(question) > 1200:
		frappe.throw("Enter a question of up to 1,200 characters")
	if not partner and not is_manager():
		names = partner_names()
		partner = names[0] if len(names) == 1 else ""
	if not partner:
		frappe.throw("Select a distributor above before asking about their data")
	p = require_partner(partner)
	q = question.casefold()
	if any(word in q for word in ("record a sale", "record sales", "how to sell", "बिक्री कैसे")):
		answer = "Open Record sales, select an approved outlet, enter the sale date and scan or enter the reel serial numbers. Submit to reduce distributor stock. This records sell-out; it does not create an ERP invoice."
	elif any(word in q for word in ("reorder", "forecast", "मंगाना", "मँगाना", "पूर्वानुमान")):
		rows = d.forecast_rows(p, get_first_day(add_months(today(), 1)))
		needed = [r for r in rows if r["suggested_qty"] > 0]
		answer = "Suggested replenishment for next month: " + str(sum(r["suggested_qty"] for r in needed)) + " reels."
		if needed:
			answer += "\n" + "\n".join(f"• {r['item_code']}: {r['suggested_qty']} reels" for r in needed[:20])
		else:
			answer += " No additional reels are suggested from the available history."
		answer += "\nThis uses past consumption, stock, incoming reels and safety stock. It is an estimate; no order has been created."
		if len(needed) > 20:
			answer += "\nShowing the first 20 products; open Forecast for the full calculation."
	elif any(word in q for word in ("credit", "outstanding", "account", "बकाया", "क्रेडिट")):
		a = d.account(p)
		answer = f"Outstanding: {a['currency']} {a['outstanding']:,.2f}.\nOverdue invoices: {a['currency']} {a['overdue']:,.2f}."
		answer += ("\nNo credit limit is set." if a["unlimited"] else f"\nAvailable credit: {a['currency']} {a['available']:,.2f}.")
		answer += "\nBased on ERP accounting records. New order commitments are not deducted here."
	elif any(word in q for word in ("order", "ऑर्डर")):
		rows = frappe.db.sql(
			"select status, count(*) as total from `tabPartner Order` where channel_partner=%s and docstatus<2 group by status order by status",
			(p.name,), as_dict=True,
		)
		answer = f"{sum(r.total for r in rows)} orders (excluding cancelled orders)."
		answer += "\n" + "\n".join(f"• {r.status}: {r.total}" for r in rows) if rows else " No orders yet."
	elif any(word in q for word in ("sale", "sold", "sales", "बिक्री", "बेचा")):
		quantities = d.consumption(p.name, get_first_day(today()), today())
		answer = f"Sold this month: {sum(quantities.values())} reels. Includes recorded sales and declared unscanned sales."
		if quantities:
			answer += "\n" + "\n".join(f"• {item}: {qty} reels" for item, qty in list(quantities.items())[:20])
		if len(quantities) > 20:
			answer += "\nShowing the first 20 products."
	elif any(word in q for word in ("stock", "reels", "inventory", "स्टॉक", "माल")):
		stock = d.stock(p.name)
		incoming = frappe.db.count("Partner Serial", {"channel_partner": p.name, "status": "In transit"})
		answer = f"Stock on hand: {sum(row['qty'] for row in stock.values())} reels.\nIn transit: {incoming} reels."
		if stock:
			answer += "\n" + "\n".join(f"• {item}: {row['qty']} reels" for item, row in list(stock.items())[:20])
		answer += "\nThis is distributor stock, not the company warehouse. Pending returns may still be included until approved."
		if len(stock) > 20:
			answer += "\nShowing the first 20 products."
	else:
		answer = "I currently support fixed questions about stock, sales this month, order status, credit, reorder suggestions, and recording a sale. Please choose a suggested question. General AI chat is not connected in this mode."
	return {"answer": answer, "distributor": p.partner_name, "as_of": today(), "mode": "fixed_questions"}
