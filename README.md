# Distributor Portal

A standalone Frappe / ERPNext application with a Vue 3 interface at `/distributor` and a Distributor Portal app tile on Desk. Built against the supplied Distributor Portal Wireframes, using the installed CRM application's standalone frontend structure as a reference.

## Initial setup

1. Open **Distributor Portal → Portal settings** as Administrator or Channel Manager.
2. Select the company, selling price list and dispatch warehouse. Review territory policy, credit handling, damage reporting window and forecast settings.
3. In **Channel partners**, link an existing ERPNext Customer to its company and territory. Assign existing portal users. The app assigns the Channel Partner role to linked users.
4. Maintain serialized sales Items and valid Item Prices in ERPNext. Set each Item's **Distributor Reel Length (m)** (default 305). Meter-based stock UOM prices are converted using the configured reel length; other stock UOMs represent one reel per stock unit. Confirm your serialization/UOM model before real dispatches.
5. Create outlets and approve them in the portal. Submit new ERPNext Delivery Notes to linked distributor Customers. The portal captures their serials; distributors acknowledge receipt before selling.

Installation does not insert sample distributor, invoice or inventory records. A separate, explicitly run demo seeder is available in `demo.py`; it is restricted to the original local demo site and does not post ERP invoices, payments or stock transactions. Existing historical dispatches are not imported automatically.

## Implemented workflows

- Distributor/HQ overview, six-month receipt/sell-out chart, stock distribution donut chart, territory flags and pending declarations.
- Dark navy navigation, collapsible sidebar, and a floating read-only assistant with six fixed questions, distributor-scoped database answers and Clear chat. No external AI connection is required.
- Serial stock, receipt acknowledgement/reversal, movement history and CSV export.
- Desktop/mobile sell-out entry, barcode camera scanner (ZXing fallback), manual/CSV serial entry, duplicate/ownership/status checks, territory policies.
- Monthly scan or SKU-count declarations, unscanned demand and damage reconciliation. A count can be followed by a same-month scan without booking demand twice. Complete a scan count before subsequent physical stock movements; cancel subsequent movements first for historical corrections.
- Orders using server-side ERPNext selling prices and available credit; HQ approval creates a **draft Sales Order** with ERPNext taxes. Accounts Manager/System Manager authorization is required for credit overrides.
- Return request, private damage photo, receipt, inspection, per-reel decisions, and linking a submitted ERPNext credit note. Accounting creates/submits the credit note in ERPNext.
- Account balances, overdue invoices, invoice/credit-note list and latest ledger entries.
- Weighted/simple moving-average forecast, safety stock and suggested order quantities, manual regeneration and daily scheduler integration.
- Partner/outlet administration, settings, roles and server-side row-level access controls.

Stock ledger entries are insert-only. Cancelling stock transactions creates reversing entries. Per-partner row locks serialize inventory updates. Generated serial, ledger, flag and forecast records cannot be forged via ordinary document CRUD.

## Roles

- **Channel Partner**: linked website users, limited to their active assigned distributors.
- **Channel Manager**: portal administration and HQ workflows. Installation adds read/select access to linked ERPNext masters and draft Sales Order creation/editing. It does not grant Sales Order submission or accounting posting.
- **Accounts Manager** plus Channel Manager, or **System Manager**: over-credit approvals.

## Structure

- `distributor_portal/distributor_portal/doctype/`: standard DocTypes and thin controllers.
- `models.py`, `domain.py`: lifecycle validation, transaction state changes and ledger/forecast helpers.
- `api.py`, `permissions.py`: scoped API and list/document permissions.
- `integration.py`: Delivery Note hooks; `tasks.py`: scheduled work.
- `frontend/`: Vue, Vue Router, Vite and responsive UI. Built assets are shipped in `distributor_portal/public/frontend/`.
- `www/distributor.py`: authenticated SPA entry point.

## Build and install

Repository: https://github.com/milind997/distributer_portal
The Python/Frappe app name is `distributor_portal` (different spelling from the repository name).


```sh
cd apps/distributor_portal/frontend
npm ci
npm run build
# From bench root:
bench --site YOUR_SITE install-app distributor_portal
bench --site YOUR_SITE migrate
bench --site YOUR_SITE build --app distributor_portal
```

## Verification

Integration tests must run on a separate disposable site with ERPNext installed. They generate isolated fixtures and roll back test transactions.

```sh
bench --site distributor-portal-test.localhost run-tests --app distributor_portal
uvx ruff check apps/distributor_portal/distributor_portal
```

Browser scripts in `frontend/tests/` use Playwright. Set `DP_TEST_WORKDIR` to the private directory holding `test-admin-password` and the fixture JSON. The `tests.browser_support.seed` bench-only helper refuses to seed any site except `distributor-portal-test.localhost`. Test sessions are generated only through local bench execution, never through an HTTP endpoint, and should be revoked after verification.

Physical camera/barcode hardware and actual production dispatches are not certified by browser automation. Phone-camera access requires a browser-supported secure origin and camera permission.

## Remaining wireframe scope

Phase 2 (sub-distributor hierarchy/transfers, schemes, production-planning requests and seasonal forecasting) is not enabled. Invoice PDF/e-Way Bill download and PDF statements continue through ERPNext; the portal currently provides the account data and CSV stock export. Pincode mapping, configurable route and Excel workbook import are not included; territory selection and CSV/text serial import are supported.
