<script setup>
import { ref, computed, onMounted, watch, onBeforeUnmount } from "vue";
import { useRoute, useRouter } from "vue-router";
import {
	LayoutDashboard,
	Package,
	ShoppingCart,
	ScanLine,
	ClipboardCheck,
	RotateCcw,
	Wallet,
	TrendingUp,
	Network,
	MapPin,
	Settings,
	Users,
	Store,
	ChevronDown,
	ChevronRight,
	Search,
	Plus,
	ArrowUpRight,
	Download,
	RefreshCw,
	X,
	Check,
	Menu,
	Camera,
	Upload,
	LogOut,
	ArrowRight,
	AlertCircle,
	Truck,
	CheckCircle2,
} from "lucide-vue-next";
import { request, action } from "./api";
import PortalAssistant from "./PortalAssistant.vue";
const route = useRoute(),
	router = useRouter();
const boot = ref(null),
	partner = ref(""),
	loading = ref(true),
	busy = ref(false),
	error = ref(""),
	toast = ref(""),
	mobile = ref(false);
const rows = ref([]),
	hasMore = ref(false),
	start = ref(0),
	search = ref(""),
	summary = ref(null),
	account = ref(null),
	settings = ref({});
const modal = ref(""),
	form = ref({}),
	detail = ref(null),
	catalog = ref([]),
	outlets = ref([]),
	territories = ref([]),
	companies = ref([]),
	customers = ref([]),
	users = ref([]),
	priceLists = ref([]),
	warehouses = ref([]),
	addresses = ref([]),
	scanned = ref([]),
	scanText = ref(""),
	video = ref(null),
	cameraActive = ref(false);
let cameraControls = null;
let toastTimer;
let loadId = 0;
const stockSlices = computed(() => {
 const colors = ["#1e3a8a", "#0f766e", "#7c3aed", "#b45309", "#be185d", "#334155"];
 const partners = (summary.value?.partners || []).filter(p => Number(p.stock) > 0);
 const total = partners.reduce((sum, p) => sum + Number(p.stock), 0);
 let offset = 0;
 return partners.map((p, i) => {
  const share = Number(p.stock) / total * 100;
  const slice = { ...p, share, offset, color: colors[i % colors.length] };
  offset += share;
  return slice;
 });
});
const stockPieTotal = computed(() => stockSlices.value.reduce((sum, p) => sum + Number(p.stock), 0));
const stockPieBackground = computed(() => stockSlices.value.length
 ? `conic-gradient(${stockSlices.value.map(p => `${p.color} ${p.offset}% ${p.offset + p.share}%`).join(", ")})`
 : "#e2e8f0");
const sidebarCollapsed = ref(false);
function toggleSidebar() {
 if (window.matchMedia("(max-width: 850px)").matches) mobile.value = false;
 else sidebarCollapsed.value = !sidebarCollapsed.value;
}
const manager = computed(() => !!boot.value?.manager);
const view = computed(() => String(route.params.view || "dashboard"));
const currentPartner = computed(() => boot.value?.partners.find((p) => p.name === partner.value));
const nav = [
	["dashboard", "Overview", LayoutDashboard],
	["orders", "Orders", ShoppingCart],
	["stock", "My stock", Package],
	["sales", "Record sales", ScanLine],
	["declarations", "Stock declarations", ClipboardCheck],
	["returns", "Returns & damage", RotateCcw],
	["accounts", "Account & credit", Wallet],
	["forecast", "Forecast", TrendingUp],
	["outlets", "Outlets", Store],
];
const hqNav = [
	["network", "Network overview", Network],
	["flags", "Territory flags", MapPin],
	["partners", "Channel partners", Users],
	["settings", "Portal settings", Settings],
];
const meta = computed(() => [...nav, ...hqNav].find((x) => x[0] === view.value) || nav[0]);
const selectedRows = computed(() => catalog.value.filter((r) => Number(r.qty_reels) > 0));
const orderTotal = computed(() =>
	selectedRows.value.reduce((a, r) => a + Number(r.qty_reels) * r.rate, 0),
);
const columnMap = {
	stock: ["serial_no", "item_code", "batch_no", "status", "length_m", "received_on"],
	orders: ["name", "channel_partner", "posting_date", "required_by", "total", "status"],
	sales: ["name", "outlet", "posting_date", "bill_no", "total_reels", "territory_flagged"],
	declarations: ["name", "channel_partner", "period", "method", "total_difference", "docstatus"],
	returns: ["name", "posting_date", "reason", "status", "credit_note"],
	flags: ["name", "channel_partner", "holder_territory", "outlet_territory", "status"],
	outlets: ["outlet_name", "outlet_type", "territory", "approval_status"],
	partners: ["partner_name", "customer", "company", "territory", "active"],
	forecast: ["name", "channel_partner", "period", "method", "suggested_total"],
};
const docTypes = {
	stock: "Partner Serial",
	orders: "Partner Order",
	sales: "Sell Out Entry",
	declarations: "Stock Declaration",
	returns: "Partner Return",
	flags: "Territory Flag",
	outlets: "Channel Outlet",
	partners: "Channel Partner",
	forecast: "Partner Forecast",
};
const columns = computed(() => columnMap[view.value] || []);
const titles = {
	serial_no: "Serial number",
	item_code: "Product",
	length_m: "Length (m)",
	received_on: "Received",
	name: "Reference",
	channel_partner: "Distributor",
	posting_date: "Date",
	required_by: "Required by",
	total: "Amount",
	bill_no: "Bill number",
	total_reels: "Reels",
	territory_flagged: "Territory",
	period: "Month",
	total_difference: "Difference",
	docstatus: "Status",
	credit_note: "Credit note",
	holder_territory: "From",
	outlet_territory: "Sold in",
	outlet_name: "Outlet",
	outlet_type: "Type",
	approval_status: "Approval",
	partner_name: "Distributor",
	suggested_total: "Suggested reels",
};
const currency = computed(
	() => account.value?.currency || summary.value?.partners?.[0]?.currency || "INR",
);
const money = (n, c = currency.value) =>
	new Intl.NumberFormat("en-IN", {
		style: "currency",
		currency: c,
		maximumFractionDigits: 0,
	}).format(n || 0);
function label(k) {
	return titles[k] || k.replaceAll("_", " ").replace(/^./, (s) => s.toUpperCase());
}
function display(k, v) {
	if (v === null || v === undefined || v === "") return "—";
	if (k === "total") return money(v);
	if (k === "docstatus") return ["Draft", "Submitted", "Cancelled"][v];
	if (k === "active") return v ? "Active" : "Inactive";
	if (k === "territory_flagged") return v ? "Outside territory" : "Within territory";
	if (k === "channel_partner")
		return boot.value?.partners.find((x) => x.name === v)?.partner_name || v;
	return v;
}
function badge(value) {
	const s = String(value || "").toLowerCase();
	return /approved|in stock|submitted|accepted|active/.test(s)
		? "green"
		: /pending|transit|open|credit|explained/.test(s)
			? "amber"
			: /reject|damage|flag/.test(s)
				? "red"
				: "gray";
}
function notify(text) {
	toast.value = text;
	clearTimeout(toastTimer);
	toastTimer = setTimeout(() => (toast.value = ""), 6000);
}
function go(name) {
	mobile.value = false;
	search.value = "";
	start.value = 0;
	router.push("/" + name);
}
async function run(fn) {
	error.value = "";
	busy.value = true;
	try {
		await fn();
	} catch (e) {
		error.value = e.message;
	} finally {
		busy.value = false;
	}
}
async function init() {
	try {
		boot.value = await request("bootstrap");
		const stored = localStorage.getItem("distributor_partner");
		partner.value = boot.value.partners.some((p) => p.name === stored)
			? stored
			: manager.value
				? ""
				: boot.value.partners[0]?.name || "";
		await load();
	} catch (e) {
		error.value = e.message;
	} finally {
		loading.value = false;
	}
}
async function load() {
	if (!boot.value) return;
	const id = ++loadId;
	loading.value = true;
	error.value = "";
	detail.value = null;
	try {
		let data;
		if (["dashboard", "network"].includes(view.value)) {
			data = await request("overview", { partner: partner.value });
			if (id === loadId) summary.value = data;
		} else if (view.value === "accounts") {
			if (!partner.value) {
				account.value = null;
				return;
			}
			data = await request("accounts", { partner: partner.value });
			if (id === loadId) account.value = data;
		} else if (view.value === "settings") {
			data = await request("record", {
				doctype: "Distributor Portal Settings",
				name: "Distributor Portal Settings",
			});
			if (id === loadId) settings.value = data;
			await fetchOptions(["Company", "Price List", "Warehouse"]);
		} else {
			data = await request("listing", {
				view: view.value,
				partner: partner.value,
				start: start.value,
				search: search.value,
			});
			if (id === loadId) {
				rows.value = data.rows;
				hasMore.value = data.has_more;
			}
		}
	} catch (e) {
		if (id === loadId) error.value = e.message;
	} finally {
		if (id === loadId) loading.value = false;
	}
}
watch(view, () => {
	start.value = 0;
	load();
});
watch(partner, () => {
	localStorage.setItem("distributor_partner", partner.value);
	start.value = 0;
	load();
});
async function fetchOptions(kinds) {
	const targets = {
		Warehouse: warehouses,
		Territory: territories,
		Company: companies,
		Customer: customers,
		User: users,
		"Price List": priceLists,
		"Channel Outlet": outlets,
		Address: addresses,
	};
	await Promise.all(
		kinds.map(async (kind) => {
			targets[kind].value = await request("options", { kind, partner: partner.value });
		}),
	);
}
function needPartner() {
	if (!partner.value) {
		error.value = "Select a distributor in the top bar to continue.";
		return false;
	}
	return true;
}
async function openForm(kind) {
	if (kind !== "partners" && !needPartner()) return;
	await run(async () => {
		form.value = {
			channel_partner: partner.value,
			posting_date: boot.value.today,
			required_by: boot.value.today,
			period: new Date(
				new Date(boot.value.today).getFullYear(),
				new Date(boot.value.today).getMonth() - 1,
				1,
				12,
			)
				.toISOString()
				.slice(0, 10),
			method: "Scan",
			reason: "Damaged in transit",
			outlet_type: "Dealer",
			active: 1,
			company: boot.value.settings.company || "",
			items: [],
		};
		scanned.value = [];
		scanText.value = "";
		if (kind === "orders") {
			catalog.value = (await request("catalog", { partner: partner.value })).map((x) => ({
				...x,
				qty_reels: 0,
			}));
			await fetchOptions(["Address"]);
		}
		if (kind === "sales") await fetchOptions(["Channel Outlet"]);
		if (kind === "outlets") await fetchOptions(["Territory"]);
		if (kind === "partners") await fetchOptions(["Territory", "Company", "Customer", "User"]);
		if (kind === "declarations") await previewDeclaration();
		modal.value = kind;
	});
}
async function previewDeclaration() {
	form.value.items = await request("declaration_preview", {
		partner: partner.value,
		period: form.value.period,
	});
}
async function addScan() {
	const text = scanText.value.trim();
	if (!text) return;
	await run(async () => {
		for (const sn of text.split(/[\s,;]+/).filter(Boolean)) {
			const row = await request("scan", {
				serial_no: sn,
				partner: partner.value,
				for_return: modal.value === "returns" ? 1 : 0,
			});
			if (scanned.value.some((x) => x.name === row.name)) {
				notify("Already added: " + sn);
				continue;
			}
			scanned.value.push(row);
		}
		scanText.value = "";
	});
}
async function uploadSerials(e) {
	const file = e.target.files?.[0];
	if (!file) return;
	scanText.value = await file.text();
	await addScan();
	e.target.value = "";
}
async function startCamera() {
	await run(async () => {
		cameraActive.value = true;
		await new Promise((r) => setTimeout(r, 100));
		const { BrowserMultiFormatReader } = await import("@zxing/browser");
		cameraControls = await new BrowserMultiFormatReader().decodeFromVideoDevice(
			undefined,
			video.value,
			(result) => {
				if (result && !busy.value) {
					scanText.value = result.getText();
					addScan();
				}
			},
		);
	});
}
function stopCamera() {
	cameraControls?.stop();
	cameraControls = null;
	cameraActive.value = false;
}
function closeModal() {
	stopCamera();
	modal.value = "";
}
async function uploadPhoto(e) {
	const file = e.target.files?.[0];
	if (!file) return;
	await run(async () => {
		const data = new FormData();
		data.append("file", file);
		data.append("is_private", "1");
		const r = await fetch("/api/method/upload_file", {
			method: "POST",
			headers: { "X-Frappe-CSRF-Token": window.distributor_csrf },
			body: data,
		});
		const json = await r.json();
		if (!r.ok) throw new Error("Photo upload failed");
		form.value.photo = json.message.file_url;
	});
}
async function submit() {
	await run(async () => {
		let data = { ...form.value };
		const type = docTypes[modal.value];
		if (modal.value === "orders") {
			data.items = selectedRows.value.map((r) => ({
				item_code: r.item_code,
				qty_reels: Number(r.qty_reels),
			}));
		}
		if (["sales", "returns"].includes(modal.value))
			data.items = scanned.value.map((r) => ({ serial_no: r.name }));
		if (modal.value === "partners")
			data.portal_users = data.portal_user ? [{ user: data.portal_user }] : [];
		const r = await request("submit_transaction", { doctype: type, data }, "POST");
		closeModal();
		notify("Saved " + r.name);
		if (type === "Channel Partner") boot.value = await request("bootstrap");
		await load();
	});
}
async function openDetail(row) {
	await run(async () => {
		detail.value = await request("record", { doctype: docTypes[view.value], name: row.name });
		form.value = {
			note: "",
			status: "Accepted",
			decisions: Object.fromEntries(
				(detail.value.items || []).map((r) => [r.serial_no, "Approved"]),
			),
		};
	});
}
async function doAction(method, args = {}) {
	await run(async () => {
		await action(detail.value.doctype, detail.value.name, method, args);
		notify("Updated successfully");
		detail.value = null;
		await load();
	});
}
async function receive() {
	await run(async () => {
		const count = await request(
			"receive_delivery",
			{ partner: detail.value.channel_partner, delivery_note: detail.value.delivery_note },
			"POST",
		);
		notify("Received " + count + " reels");
		detail.value = null;
		await load();
	});
}
async function forecast() {
	if (!needPartner()) return;
	await run(async () => {
		detail.value = await request("generate_forecast", { partner: partner.value }, "POST");
		notify("Forecast generated from recorded consumption");
		const data = await request("listing", { view: "forecast", partner: partner.value });
		rows.value = data.rows;
	});
}
async function useSuggestion() {
	const forecast = detail.value;
	await openForm("orders");
	const suggestions = Object.fromEntries(
		forecast.items.map((r) => [r.item_code, r.suggested_qty]),
	);
	catalog.value.forEach((r) => (r.qty_reels = suggestions[r.item_code] || 0));
	detail.value = null;
}
async function saveSettings() {
	await run(async () => {
		await request("save_settings", { data: settings.value }, "POST");
		boot.value = await request("bootstrap");
		notify("Portal settings saved");
	});
}
function page(delta) {
	start.value = Math.max(0, start.value + delta);
	load();
}
onMounted(init);
onBeforeUnmount(() => {
	stopCamera();
	clearTimeout(toastTimer);
});
</script>

<template>
	<div class="app-shell" :class="{ 'sidebar-collapsed': sidebarCollapsed }" :style="{ '--accent': boot?.settings.accent_colour || '#2563eb' }">
		<PortalAssistant v-if="boot" :partner="partner" :manager="manager" />
		<div v-if="mobile" class="mobile-shade" @click="mobile = false"></div>
		<aside :class="['sidebar', { opened: mobile }]">
			<a href="/distributor" class="brand"
				><img
					:src="boot?.settings.logo || '/assets/distributor_portal/logo.svg'"
					alt=""
				/><span
					>{{ boot?.settings.portal_title || "Distributor Portal"
					}}<small>CHANNEL OPERATIONS</small></span
				></a
			>
			<div class="workspace-tag">
				<span class="live-dot"></span
				><span class="workspace-name">{{ manager ? "Head office workspace" : "Distributor workspace" }}</span><button class="sidebar-toggle" :aria-label="sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'" :title="sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'" :aria-expanded="!sidebarCollapsed" @click="toggleSidebar"><Menu :size="17" /></button>
			</div>
			<p class="nav-caption">WORKSPACE</p>
			<nav>
				<button
					v-for="[key, title, icon] in nav"
					:key="key"
 :aria-label="title"
 :title="title"
					:class="{ active: view === key }"
					@click="go(key)"
				>
					<component :is="icon" :size="17" /><span>{{ title }}</span>
				</button>
			</nav>
			<template v-if="manager"
				><p class="nav-caption">HEAD OFFICE</p>
				<nav>
					<button
						v-for="[key, title, icon] in hqNav"
						:key="key"
 :aria-label="title"
 :title="title"
						:class="{ active: view === key }"
						@click="go(key)"
					>
						<component :is="icon" :size="17" /><span>{{ title }}</span>
					</button>
				</nav></template
			>
			<div class="sidebar-bottom">
				<div class="profile">
					<div class="avatar">{{ boot?.full_name?.slice(0, 1) || "D" }}</div>
					<span
						>{{ boot?.full_name || "Loading…"
						}}<small>{{
							manager ? "Channel administration" : "Channel partner"
						}}</small></span
					>
				</div>
			</div>
		</aside>
		<main>
			<header class="topbar">
				<div class="breadcrumb">
					<button
						class="icon-button mobile-only"
						aria-label="Open navigation"
						@click="mobile = true"
					>
						<Menu :size="20" /></button
					><span>Distributor Portal</span><ChevronRight :size="14" /><strong>{{
						meta[1]
					}}</strong>
				</div>
				<div class="topbar-right">
					<select v-if="boot" aria-label="Select distributor" v-model="partner">
						<option v-if="manager" value="">All distributors</option>
						<option v-for="p in boot.partners" :value="p.name">
							{{ p.partner_name }}
						</option>
					</select>
				</div>
			</header>
			<div class="page">
				<div class="page-heading">
					<div>
						<p class="eyebrow">
							{{ currentPartner?.territory || "YOUR DISTRIBUTION NETWORK" }}
						</p>
						<h1>{{ meta[1] }}</h1>
						<p class="subtitle">
							{{
								view === "dashboard"
									? "A clear view of your stock, sales and what needs attention."
									: view === "network"
										? "Understand performance across your entire distribution network."
										: view === "settings"
											? "Configure how your distribution network works."
											: "Manage " +
												meta[1].toLowerCase() +
												" with a complete record of every movement."
							}}
						</p>
					</div>
					<div class="heading-actions">
						<button class="button" aria-label="Refresh data" @click="load">
							<RefreshCw :size="15" /></button
						><a
							v-if="view === 'stock' && partner"
							class="button"
							:href="
								'/api/method/distributor_portal.api.export_stock?partner=' +
								encodeURIComponent(partner)
							"
							><Download :size="15" />Export CSV</a
						><button
							v-if="
								[
									'orders',
									'sales',
									'returns',
									'declarations',
									'outlets',
									'partners',
								].includes(view)
							"
							class="button primary"
							:disabled="busy"
							@click="openForm(view)"
						>
							<Plus :size="16" />{{
								view === "sales"
									? "Record sale"
									: view === "orders"
										? "Place order"
										: view === "declarations"
											? "Declare stock"
											: view === "partners"
												? "Add distributor"
												: view === "outlets"
													? "Add outlet"
													: "New return"
							}}</button
						><button
							v-if="view === 'forecast'"
							class="button primary"
							:disabled="busy"
							@click="forecast"
						>
							<TrendingUp :size="16" />Generate forecast</button
						><button
							v-if="view === 'settings'"
							class="button primary"
							:disabled="busy"
							@click="saveSettings"
						>
							<Check :size="16" />Save settings
						</button>
					</div>
				</div>
				<div v-if="error" class="alert error" role="alert">
					<AlertCircle :size="18" /><span>{{ error }}</span
					><button aria-label="Dismiss error" @click="error = ''">
						<X :size="16" />
					</button>
				</div>
				<div v-if="loading" class="loading">
					<span class="spinner"></span>Loading live data…
				</div>
				<template v-else-if="['dashboard', 'network'].includes(view) && summary">
					<div class="stats">
						<article>
							<span>Stock on hand<Package :size="18" /></span
							><strong
								>{{ summary.stock.toLocaleString() }}<small>reels</small></strong
							>
							<p>Across {{ summary.partners.length }} distributors</p>
						</article>
						<article>
							<span>Sold this month<TrendingUp :size="18" /></span
							><strong
								>{{ summary.sold.toLocaleString() }}<small>reels</small></strong
							>
							<p>Recorded sales + declared consumption</p>
						</article>
						<article>
							<span>In transit<Truck :size="18" /></span
							><strong
								>{{ summary.in_transit.toLocaleString()
								}}<small>reels</small></strong
							>
							<p>Awaiting receipt acknowledgement</p>
						</article>
						<article>
							<span>Territory flags<MapPin :size="18" /></span
							><strong>{{ summary.flags }}<small>open</small></strong>
							<p>Outside-territory sales to review</p>
						</article>
					</div>
					<div v-if="!boot.partners.length" class="onboarding">
						<div class="onboarding-icon"><Network :size="30" /></div>
						<div>
							<h2>Build your distribution network</h2>
							<p>
								Start with portal settings, then link an ERPNext customer and a
								portal user to your first distributor. Stock will arrive from
								submitted Delivery Notes.
							</p>
							<div class="actions">
								<button class="button primary" @click="openForm('partners')">
									<Plus :size="16" />Add your first distributor</button
								><button class="button" @click="go('settings')">
									Configure settings<ArrowRight :size="15" />
								</button>
							</div>
						</div>
					</div>
					<div class="dashboard-grid">
						<section class="panel">
							<div class="panel-heading">
								<div>
									<h2>Received vs. sold</h2>
									<p>Reel movement over the last six months</p>
								</div>
								<div class="legend">
									<span><i class="blue"></i>Received</span
									><span><i class="light"></i>Sold</span>
								</div>
							</div>
							<div class="chart">
								<div v-for="m in summary.monthly" class="chart-column">
									<div class="chart-bars">
										<div
											class="bar blue"
											:style="{
												height:
													Math.max(
														2,
														(m.received /
															Math.max(
																1,
																...summary.monthly.flatMap((x) => [
																	x.received,
																	x.sold,
																]),
															)) *
															145,
													) + 'px',
											}"
											:title="m.received + ' received'"
										></div>
										<div
											class="bar light"
											:style="{
												height:
													Math.max(
														2,
														(m.sold /
															Math.max(
																1,
																...summary.monthly.flatMap((x) => [
																	x.received,
																	x.sold,
																]),
															)) *
															145,
													) + 'px',
											}"
											:title="m.sold + ' sold'"
										></div>
									</div>
									<span>{{ m.month }}</span>
								</div>
							</div>
							<p class="chart-note">
								Actual channel movements. Returns and damage are excluded from
								demand.
							</p>
						</section>
						<section class="panel stock-distribution">
 <div class="panel-heading"><div><h2>Stock by distributor</h2><p>Share of current stock on hand · reels</p></div></div>
 <div v-if="stockPieTotal" class="stock-pie-content">
  <div class="stock-pie" role="img" :aria-label="'Stock by distributor: ' + stockSlices.map(p => p.partner_name + ', ' + p.stock + ' reels').join('; ')" :style="{ background: stockPieBackground }">
   <div class="stock-pie-center"><strong>{{ stockPieTotal.toLocaleString() }}</strong><span>reels in stock</span></div>
  </div>
  <ul class="stock-pie-legend"><li v-for="slice in stockSlices" :key="slice.name"><i :style="{background: slice.color}"></i><span>{{ slice.partner_name }}</span><strong>{{ slice.stock }} <small>({{ slice.share.toFixed(1) }}%)</small></strong></li></ul>
 </div>
 <p v-else class="stock-pie-empty">No stock on hand for the selected distributors.</p>
</section>
<section class="panel attention">
							<div class="panel-heading">
								<div>
									<h2>Needs attention</h2>
									<p>Keep your network moving</p>
								</div>
							</div>
							<button @click="go('declarations')">
								<span class="attention-icon amber"
									><ClipboardCheck :size="18" /></span
								><span
									>Stock declarations<small
										>{{ summary.pending_declarations }} pending for last
										month</small
									></span
								><ChevronRight :size="16" /></button
							><button @click="go('flags')">
								<span class="attention-icon red"><MapPin :size="18" /></span
								><span
									>Territory reviews<small
										>{{ summary.flags }} open flags</small
									></span
								><ChevronRight :size="16" /></button
							><button @click="go('stock')">
								<span class="attention-icon blue"><Truck :size="18" /></span
								><span
									>Incoming deliveries<small
										>{{ summary.in_transit }} reels awaiting receipt</small
									></span
								><ChevronRight :size="16" />
							</button>
						</section>
					</div>
					<section class="panel">
						<div class="panel-heading">
							<div>
								<h2>
									{{ partner ? "Distributor health" : "Distributor network" }}
								</h2>
								<p>Stock, demand and account standing at a glance</p>
							</div>
							<button class="text-button" @click="go('partners')" v-if="manager">
								Manage distributors<ArrowUpRight :size="15" />
							</button>
						</div>
						<div class="table-wrap">
							<table>
								<thead>
									<tr>
										<th>Distributor</th>
										<th>Territory</th>
										<th>Stock</th>
										<th>Sell-out</th>
										<th>Outstanding</th>
										<th>Declaration</th>
										<th>Flags</th>
									</tr>
								</thead>
								<tbody>
									<tr v-for="p in summary.partners" @click="partner = p.name">
										<td>
											<strong>{{ p.partner_name }}</strong
											><small>{{ p.name }}</small>
										</td>
										<td>{{ p.territory }}</td>
										<td>{{ p.stock }} reels</td>
										<td>{{ p.sold }} reels</td>
										<td>{{ money(p.outstanding, p.currency) }}</td>
										<td>
											<span :class="['badge', badge(p.declaration)]">{{
												p.declaration
											}}</span>
										</td>
										<td>{{ p.flags }}</td>
									</tr>
									<tr v-if="!summary.partners.length">
										<td colspan="7" class="empty-cell">
											Your distributors will appear here once added.
										</td>
									</tr>
								</tbody>
							</table>
						</div>
					</section>
				</template>
				<template v-else-if="view === 'accounts'"
					><div v-if="!account" class="empty-state">
						<Wallet :size="36" />
						<h2>Select a distributor</h2>
						<p>Choose a distributor above to view their account and credit.</p>
					</div>
					<template v-else
						><div class="stats">
							<article>
								<span>Credit limit</span
								><strong>{{
									account.unlimited ? "Not set" : money(account.limit)
								}}</strong>
								<p>
									{{
										account.unlimited
											? "No customer credit limit configured"
											: "Company currency"
									}}
								</p>
							</article>
							<article>
								<span>Outstanding</span
								><strong>{{ money(account.outstanding) }}</strong>
								<p>From ERPNext general ledger</p>
							</article>
							<article>
								<span>Available credit</span
								><strong>{{
									account.unlimited ? "No limit" : money(account.available)
								}}</strong>
								<p>Before new order commitments</p>
							</article>
							<article>
								<span>Overdue invoices</span
								><strong>{{ money(account.overdue) }}</strong>
								<p>Past invoice due dates</p>
							</article>
						</div>
						<section class="panel">
							<div class="panel-heading"><h2>Invoices & credit notes</h2></div>
							<div class="table-wrap">
								<table>
									<thead>
										<tr>
											<th>Invoice</th>
											<th>Date</th>
											<th>Due</th>
											<th>Amount</th>
											<th>Outstanding</th>
										</tr>
									</thead>
									<tbody>
										<tr v-for="r in account.invoices">
											<td>
												{{ r.name
												}}<span v-if="r.is_return" class="badge gray"
													>Credit note</span
												>
											</td>
											<td>{{ r.posting_date }}</td>
											<td>{{ r.due_date }}</td>
											<td>{{ money(r.grand_total, r.currency) }}</td>
											<td>{{ money(r.outstanding_amount, r.currency) }}</td>
										</tr>
										<tr v-if="!account.invoices.length">
											<td colspan="5" class="empty-cell">
												No submitted invoices for this distributor.
											</td>
										</tr>
									</tbody>
								</table>
							</div>
						</section>
						<section class="panel">
							<div class="panel-heading">
								<h2>Account ledger</h2>
								<span class="muted">Latest 100 entries</span>
							</div>
							<div class="table-wrap">
								<table>
									<thead>
										<tr>
											<th>Date</th>
											<th>Voucher</th>
											<th>Type</th>
											<th>Debit</th>
											<th>Credit</th>
										</tr>
									</thead>
									<tbody>
										<tr v-for="r in account.ledger">
											<td>{{ r.posting_date }}</td>
											<td>{{ r.voucher_no }}</td>
											<td>{{ r.voucher_type }}</td>
											<td>{{ money(r.debit) }}</td>
											<td>{{ money(r.credit) }}</td>
										</tr>
										<tr v-if="!account.ledger.length">
											<td colspan="5" class="empty-cell">
												No ledger entries yet.
											</td>
										</tr>
									</tbody>
								</table>
							</div>
						</section></template
					></template
				>
				<template v-else-if="view === 'settings'"
					><div class="settings-grid">
						<section class="panel settings-panel">
							<h2>Branding & company</h2>
							<p>Your identity across the distributor workspace.</p>
							<label>Portal title<input v-model="settings.portal_title" /></label
							><label
								>Accent colour<input
									type="color"
									v-model="settings.accent_colour" /></label
							><label
								>Company<select v-model="settings.company">
									<option value="">Select company</option>
									<option v-for="x in companies">{{ x.name }}</option>
								</select></label
							><label
								>Selling price list<select v-model="settings.price_list">
									<option value="">Select price list</option>
									<option v-for="x in priceLists">{{ x.name }}</option>
								</select></label
							><label
								>Dispatch warehouse<select v-model="settings.default_warehouse">
									<option value="">Select warehouse</option>
									<option v-for="x in warehouses">{{ x.name }}</option>
								</select></label
							><label
								>Support email<input
									v-model="settings.support_email"
									type="email" /></label
							><label>Support phone<input v-model="settings.support_phone" /></label>
						</section>
						<section class="panel settings-panel">
							<h2>Territory & credit</h2>
							<p>Rules are checked on the server for every transaction.</p>
							<label
								>Outside-territory sales<select v-model="settings.territory_rule">
									<option>Warn and flag HQ</option>
									<option>Block the sale</option>
									<option>Allow, log only</option>
								</select></label
							><label class="check-label"
								><input
									type="checkbox"
									v-model="settings.outlet_approval_required"
									:true-value="1"
									:false-value="0"
								/>HQ approval for new outlets</label
							><label
								>Over-credit orders<select v-model="settings.credit_rule">
									<option>Hold for Accounts approval</option>
									<option>Block submit</option>
								</select></label
							><label
								>Minimum order (reels)<input
									type="number"
									min="1"
									v-model.number="settings.minimum_order_reels"
							/></label>
							<h2 class="section-gap">Stock & returns</h2>
							<label
								>Declaration due day<input
									type="number"
									min="1"
									max="28"
									v-model.number="settings.declaration_due_day" /></label
							><label
								>Transit damage window (days)<input
									type="number"
									min="1"
									v-model.number="settings.damage_window_days" /></label
							><label class="check-label"
								><input
									type="checkbox"
									v-model="settings.damage_photos_required"
									:true-value="1"
									:false-value="0"
								/>Require photos for damage</label
							>
						</section>
						<section class="panel settings-panel">
							<h2>Demand forecasting</h2>
							<p>Suggestions use sell-out, existing stock and incoming reels.</p>
							<label
								>Method<select v-model="settings.forecast_method">
									<option>Weighted moving average</option>
									<option>Simple moving average</option>
								</select></label
							><label
								>History (months)<input
									type="number"
									min="1"
									max="24"
									v-model.number="settings.history_months" /></label
							><label
								>Safety stock (%)<input
									type="number"
									min="0"
									max="200"
									v-model.number="settings.safety_stock_percent" /></label
							><label
								>Generate on day<input
									type="number"
									min="1"
									max="28"
									v-model.number="settings.forecast_day"
							/></label>
							<div class="info-note">
								Suggestions remain editable. Orders create a draft ERPNext Sales
								Order after HQ approval.
							</div>
						</section>
					</div></template
				>
				<template v-else
					><section class="panel list-panel">
						<div class="list-toolbar">
							<div class="list-tabs">
								<span class="selected">All {{ meta[1].toLowerCase() }}</span
								><span class="count"
									>{{ rows.length }}{{ hasMore ? "+" : "" }}</span
								>
							</div>
							<form
								class="search-input"
								@submit.prevent="
									start = 0;
									load();
								"
							>
								<Search :size="15" /><input
									aria-label="Search records"
									v-model="search"
									placeholder="Search records…"
								/><button type="submit">Search</button>
							</form>
						</div>
						<div class="table-wrap">
							<table v-if="rows.length">
								<thead>
									<tr>
										<th v-for="key in columns">{{ label(key) }}</th>
										<th></th>
									</tr>
								</thead>
								<tbody>
									<tr
										v-for="row in rows"
										:key="row.name"
										tabindex="0"
										@click="openDetail(row)"
										@keydown.enter="openDetail(row)"
									>
										<td v-for="(key, i) in columns">
											<span
												v-if="
													[
														'status',
														'approval_status',
														'docstatus',
														'active',
													].includes(key)
												"
												:class="['badge', badge(display(key, row[key]))]"
												>{{ display(key, row[key]) }}</span
											><strong v-else-if="i === 0">{{
												display(key, row[key])
											}}</strong
											><span v-else>{{ display(key, row[key]) }}</span>
										</td>
										<td><ChevronRight :size="15" /></td>
									</tr>
								</tbody>
							</table>
							<div v-else class="empty-state">
								<component :is="meta[2]" :size="38" />
								<h2>No {{ meta[1].toLowerCase() }} yet</h2>
								<p>
									{{
										view === "stock"
											? "Submit a Delivery Note for a linked distributor to start tracking reels."
											: view === "forecast"
												? "Select a distributor and generate a forecast from their recorded consumption."
												: "Records will appear here as your team uses the portal."
									}}
								</p>
								<button
									v-if="
										[
											'orders',
											'sales',
											'returns',
											'declarations',
											'outlets',
											'partners',
										].includes(view)
									"
									class="button"
									@click="openForm(view)"
								>
									<Plus :size="15" />Create first record
								</button>
							</div>
						</div>
						<div class="pagination">
							<span>{{
								rows.length
									? "Showing " + (start + 1) + "–" + (start + rows.length)
									: "0 records"
							}}</span>
							<div>
								<button class="button" :disabled="start === 0" @click="page(-50)">
									Previous</button
								><button class="button" :disabled="!hasMore" @click="page(50)">
									Next
								</button>
							</div>
						</div>
					</section></template
				>
				<footer class="page-footer">
					<span>Distributor Portal</span
					><span>Connected to ERPNext · Every reel accounted for</span>
				</footer>
			</div>
		</main>
		<div v-if="toast" role="status" class="toast"><CheckCircle2 :size="18" />{{ toast }}</div>
		<div v-if="modal" class="overlay" @click.self="closeModal">
			<section class="modal" role="dialog" aria-modal="true" :aria-label="'New ' + modal">
				<header>
					<div>
						<p class="eyebrow">{{ currentPartner?.partner_name || "HEAD OFFICE" }}</p>
						<h2>
							{{
								modal === "orders"
									? "Place an order"
									: modal === "sales"
										? "Record a sale"
										: modal === "partners"
											? "Add distributor"
											: modal === "outlets"
												? "Add outlet"
												: modal === "returns"
													? "Request a return"
													: "Monthly stock declaration"
							}}
						</h2>
					</div>
					<button class="icon-button" aria-label="Close dialog" @click="closeModal">
						<X :size="20" />
					</button>
				</header>
				<form @submit.prevent="submit">
					<div class="modal-body">
						<div v-if="error" class="alert error" role="alert">{{ error }}</div>
						<template v-if="modal === 'partners'"
							><div class="form-grid">
								<label
									>Distributor name<input
										required
										v-model="form.partner_name" /></label
								><label
									>ERPNext customer<select required v-model="form.customer">
										<option v-for="x in customers">{{ x.name }}</option>
									</select></label
								><label
									>Company<select required v-model="form.company">
										<option v-for="x in companies">{{ x.name }}</option>
									</select></label
								><label
									>Territory<select
										aria-label="Territory"
										required
										v-model="form.territory"
									>
										<option v-for="x in territories">{{ x.name }}</option>
									</select></label
								><label class="full"
									>Portal user<select v-model="form.portal_user">
										<option value="">Assign later from Desk</option>
										<option v-for="x in users">{{ x.name }}</option>
									</select></label
								>
							</div>
							<p class="info-note">
								This links an existing customer to a distributor. Assigning a user
								grants the Channel Partner role and access to this distributor
								only.
							</p></template
						>
						<template v-if="modal === 'outlets'"
							><div class="form-grid">
								<label
									>Outlet name<input
										required
										v-model="form.outlet_name" /></label
								><label
									>Type<select
										aria-label="Outlet type"
										v-model="form.outlet_type"
									>
										<option>Dealer</option>
										<option>Retailer</option>
										<option>System integrator</option>
										<option>Project</option>
									</select></label
								><label
									>Territory<select
										aria-label="Territory"
										required
										v-model="form.territory"
									>
										<option v-for="x in territories">{{ x.name }}</option>
									</select></label
								><label>Pincode<input v-model="form.pincode" /></label
								><label>GSTIN<input v-model="form.gstin" /></label
								><label class="full"
									>Address<textarea v-model="form.address"></textarea>
								</label>
							</div>
							<p class="info-note">
								New outlets may require HQ approval before recording sales.
							</p></template
						>
						<template v-if="modal === 'orders'"
							><div class="form-grid">
								<label
									>Required by<input
										required
										type="date"
										v-model="form.required_by"
										:min="boot.today" /></label
								><label>Your PO number<input v-model="form.po_number" /></label
								><label class="full"
									>Shipping address<select v-model="form.shipping_address">
										<option value="">Customer's default address</option>
										<option v-for="x in addresses">{{ x.name }}</option>
									</select></label
								>
							</div>
							<div class="table-wrap order-items">
								<table>
									<thead>
										<tr>
											<th>Product</th>
											<th>Your stock</th>
											<th>Rate / reel</th>
											<th>Order reels</th>
											<th>Amount</th>
										</tr>
									</thead>
									<tbody>
										<tr v-for="r in catalog">
											<td>
												<strong>{{ r.item_name }}</strong
												><small>{{ r.item_code }}</small>
											</td>
											<td>{{ r.stock }}</td>
											<td>{{ money(r.rate, r.currency) }}</td>
											<td>
												<input
													:aria-label="'Quantity ' + r.item_code"
													type="number"
													min="0"
													step="1"
													v-model.number="r.qty_reels"
												/>
											</td>
											<td>
												{{
													money(r.rate * (r.qty_reels || 0), r.currency)
												}}
											</td>
										</tr>
										<tr v-if="!catalog.length">
											<td colspan="5" class="empty-cell">
												No priced serialized products. Configure a selling
												price list and Item Prices in ERPNext.
											</td>
										</tr>
									</tbody>
								</table>
							</div>
							<div class="order-total">
								<span
									>{{ selectedRows.length }} products ·
									{{
										selectedRows.reduce((a, r) => a + (r.qty_reels || 0), 0)
									}}
									reels</span
								><strong
									>{{ money(orderTotal, catalog[0]?.currency)
									}}<small>Before ERPNext taxes</small></strong
								>
							</div>
							<label
								>Note to HQ<textarea
									v-model="form.note"
									placeholder="Delivery instructions or other details"
								></textarea>
							</label>
							<p class="info-note">
								HQ reviews this order and creates a draft ERPNext Sales Order.
								Final taxes and credit validation are applied there.
							</p></template
						>
						<template v-if="['sales', 'returns'].includes(modal)"
							><div class="form-grid">
								<label v-if="modal === 'sales'"
									>Buyer / outlet<select
										aria-label="Buyer / outlet"
										required
										v-model="form.outlet"
									>
										<option v-for="x in outlets" :value="x.name">
											{{ x.outlet_name }} · {{ x.territory }} ·
											{{ x.approval_status }}
										</option>
									</select></label
								><label v-if="modal === 'sales'"
									>Your bill number<input v-model="form.bill_no" /></label
								><label
									>Date<input
										required
										type="date"
										v-model="form.posting_date"
										:max="boot.today" /></label
								><label v-if="modal === 'returns'"
									>Reason<select aria-label="Reason" v-model="form.reason">
										<option>Damaged in transit</option>
										<option>Manufacturing defect</option>
										<option>Wrong item supplied</option>
										<option>Unsold / excess stock</option>
										<option>Damaged at godown</option>
									</select></label
								>
							</div>
							<div class="scan-box">
								<h3><ScanLine :size="19" />Scan or enter reel serials</h3>
								<div class="scan-input">
									<input
										aria-label="Reel serial number"
										v-model="scanText"
										placeholder="Scan a barcode or paste serial numbers"
										@keydown.enter.prevent="addScan"
									/><button
										type="button"
										class="button primary"
										:disabled="busy"
										@click="addScan"
									>
										Add
									</button>
								</div>
								<div class="actions">
									<button
										type="button"
										class="button"
										@click="cameraActive ? stopCamera() : startCamera()"
									>
										<Camera :size="15" />{{
											cameraActive ? "Stop camera" : "Use camera"
										}}</button
									><label class="button file-label"
										><Upload :size="15" />Import CSV / text<input
											type="file"
											accept=".csv,.txt"
											@change="uploadSerials"
									/></label>
								</div>
								<video
									v-if="cameraActive"
									ref="video"
									autoplay
									muted
									playsinline
									class="scanner-video"
								></video>
								<div v-for="(r, i) in scanned" class="scanned-row">
									<CheckCircle2 :size="17" />
									<div>
										<strong>{{ r.serial_no }}</strong
										><small>{{ r.item_code }} · {{ r.length_m }} m</small>
									</div>
									<button
										type="button"
										class="icon-button"
										:aria-label="'Remove ' + r.serial_no"
										@click="scanned.splice(i, 1)"
									>
										<X :size="16" />
									</button>
								</div>
								<p class="muted">
									{{ scanned.length }} reels ·
									{{ scanned.reduce((a, r) => a + r.length_m, 0) }} m
								</p>
							</div>
							<label v-if="modal === 'sales'"
								>Territory explanation (if applicable)<textarea
									v-model="form.explanation"
									placeholder="Explain sales outside your assigned territory"
								></textarea></label
							><template v-else
								><label
									>What happened?<textarea
										required
										v-model="form.description"
									></textarea></label
								><label
									>Damage photo<input
										type="file"
										accept="image/*"
										@change="uploadPhoto" /></label
								><span v-if="form.photo" class="badge green"
									>Private photo uploaded</span
								></template
							></template
						>
						<template v-if="modal === 'declarations'"
							><div class="form-grid">
								<label
									>Month<input
										required
										type="date"
										v-model="form.period"
										@change="run(previewDeclaration)" /></label
								><label
									>Counting method<select
										aria-label="Counting method"
										v-model="form.method"
									>
										<option>Scan</option>
										<option>Count</option>
									</select></label
								>
							</div>
							<p class="info-note">
								Expected stock = receipts − recorded sales − returns − damage.
								Complete the declaration before recording the next month's
								movements.
							</p>
							<label v-if="form.method === 'Scan'"
								>Serial numbers physically on hand<textarea
									class="serial-textarea"
									v-model="form.counted_serials"
									placeholder="One serial number per line. Missing reels are reconciled automatically."
								></textarea>
							</label>
							<div class="table-wrap">
								<table>
									<thead>
										<tr>
											<th>Product</th>
											<th>Expected</th>
											<th v-if="form.method === 'Count'">Counted</th>
											<th>Treat shortage as</th>
										</tr>
									</thead>
									<tbody>
										<tr v-for="r in form.items">
											<td>{{ r.item_code }}</td>
											<td>{{ r.expected }}</td>
											<td v-if="form.method === 'Count'">
												<input
													type="number"
													min="0"
													:max="r.expected"
													v-model.number="r.counted"
												/>
											</td>
											<td>
												<select v-model="r.treatment">
													<option>Sold, not scanned</option>
													<option>Damage</option>
												</select>
											</td>
										</tr>
									</tbody>
								</table>
							</div>
							<p v-if="form.method === 'Count'" class="info-note">
								Count-only shortages do not identify missing serials. A later scan
								declaration is needed before further serial sales.
							</p>
							<label>Notes<textarea v-model="form.notes"></textarea></label
						></template>
					</div>
					<footer>
						<button type="button" class="button" @click="closeModal">Cancel</button
						><button class="button primary" type="submit" :disabled="busy">
							{{
								busy
									? "Saving…"
									: modal === "orders"
										? "Submit for approval"
										: modal === "declarations"
											? "Submit declaration"
											: "Save " +
												(modal === "sales"
													? "sale"
													: modal === "returns"
														? "return"
														: "record")
							}}
						</button>
					</footer>
				</form>
			</section>
		</div>
		<div v-if="detail" class="overlay drawer-overlay" @click.self="detail = null">
			<section class="drawer" role="dialog" aria-modal="true" :aria-label="detail.name">
				<header>
					<div>
						<p class="eyebrow">{{ detail.doctype }}</p>
						<h2>
							{{
								detail.serial_no ||
								detail.partner_name ||
								detail.outlet_name ||
								detail.name
							}}
						</h2>
					</div>
					<button class="icon-button" aria-label="Close details" @click="detail = null">
						<X :size="20" />
					</button>
				</header>
				<div class="drawer-body">
					<div v-if="error" class="alert error" role="alert">{{ error }}</div>
					<div class="detail-grid">
						<template v-for="(value, key) in detail"
							><div
								v-if="
									value !== null &&
									value !== '' &&
									typeof value !== 'object' &&
									![
										'doctype',
										'owner',
										'modified_by',
										'creation',
										'modified',
										'idx',
										'name',
										'counted_serials',
										'period_key',
									].includes(key)
								"
							>
								<span>{{ label(key) }}</span
								><strong>{{ display(key, value) }}</strong>
							</div></template
						>
					</div>
					<div
						v-if="detail.items?.length && detail.doctype !== 'Partner Forecast'"
						class="table-wrap"
					>
						<table>
							<thead>
								<tr>
									<th>
										{{
											detail.doctype === "PartnerForecast"
												? "Product"
												: "Item / reel"
										}}
									</th>
									<th>Quantity / result</th>
								</tr>
							</thead>
							<tbody>
								<tr v-for="r in detail.items">
									<td>
										{{ r.item_code || r.serial_no
										}}<small v-if="r.serial_no">{{ r.serial_no }}</small>
									</td>
									<td>
										{{
											r.qty_reels ??
											r.suggested_qty ??
											r.difference ??
											r.length_m
										}}
										{{
											r.decision && r.decision !== "Pending"
												? r.decision
												: ""
										}}
									</td>
								</tr>
							</tbody>
						</table>
					</div>
					<div v-if="detail.movements?.length" class="timeline">
						<h3>Serial movement history</h3>
						<div v-for="m in detail.movements">
							<span class="live-dot"></span>
							<p>
								<strong>{{ m.movement }}</strong
								><small
									>{{ m.posting_date }} · {{ m.voucher_type }}
									{{ m.voucher_no }}</small
								>
							</p>
							<span>{{ m.qty_reels > 0 ? "+" : "" }}{{ m.qty_reels }}</span>
						</div>
					</div>
					<div v-if="detail.doctype === 'Partner Forecast'" class="table-wrap">
						<table>
							<thead>
								<tr>
									<th>Product</th>
									<th>Forecast</th>
									<th>On hand</th>
									<th>In transit</th>
									<th>Projected</th>
									<th>Safety</th>
									<th>Suggested</th>
								</tr>
							</thead>
							<tbody>
								<tr v-for="r in detail.items">
									<td>{{ r.item_code }}</td>
									<td>{{ r.forecast_qty }}</td>
									<td>{{ r.stock_qty }}</td>
									<td>{{ r.in_transit }}</td>
									<td>{{ r.projected_qty }}</td>
									<td>{{ r.safety_qty }}</td>
									<td>{{ r.suggested_qty }}</td>
								</tr>
							</tbody>
						</table>
						<p class="info-note">
							Suggested = forecast + safety − projected stock. Only completed months
							of recorded demand contribute to the forecast.
						</p>
					</div>
					<div class="detail-actions">
						<button
							v-if="
								detail.doctype === 'Partner Serial' &&
								detail.status === 'In transit'
							"
							class="button primary"
							:disabled="busy"
							@click="receive"
						>
							Acknowledge delivery receipt</button
						><button
							v-if="
								detail.doctype === 'Partner Serial' &&
								detail.status === 'In stock' &&
								detail.last_voucher === detail.name &&
								manager
							"
							class="button"
							:disabled="busy"
							@click="doAction('reverse_receipt')"
						>
							Undo receipt acknowledgement</button
						><button
							v-if="
								detail.doctype === 'Channel Outlet' &&
								manager &&
								detail.approval_status === 'Pending'
							"
							class="button primary"
							:disabled="busy"
							@click="doAction('approve')"
						>
							Approve outlet</button
						><template
							v-if="
								detail.doctype === 'Partner Order' &&
								manager &&
								detail.docstatus === 1 &&
								['Pending HQ approval', 'Credit approval required'].includes(
									detail.status,
								)
							"
							><label class="check-label"
								><input type="checkbox" v-model="form.credit_override" />Accounts
								credit override</label
							><button
								class="button primary"
								:disabled="busy"
								@click="
									doAction('approve', {
										credit_override: !!form.credit_override,
									})
								"
							>
								Approve & create Sales Order</button
							><label
								>Rejection reason<textarea v-model="form.note"></textarea></label
							><button
								class="button danger"
								:disabled="busy || !form.note"
								@click="doAction('reject', { reason: form.note })"
							>
								Reject order
							</button></template
						><template
							v-if="
								detail.doctype === 'Territory Flag' &&
								['Open', 'Explained'].includes(detail.status)
							"
							><label
								>{{ manager ? "Resolution note" : "Your explanation"
								}}<textarea v-model="form.note"></textarea></label
							><select v-if="manager" v-model="form.status">
								<option>Accepted</option>
								<option>Action taken</option></select
							><button
								class="button primary"
								:disabled="busy || !form.note"
								@click="
									manager
										? doAction('resolve', {
												resolution: form.note,
												status: form.status,
											})
										: doAction('explain', { explanation: form.note })
								"
							>
								{{ manager ? "Resolve flag" : "Send explanation" }}
							</button></template
						><template
							v-if="
								detail.doctype === 'Partner Return' &&
								manager &&
								detail.docstatus === 1
							"
							><label
								>Inspection / resolution note<textarea
									v-model="form.note"
								></textarea></label
							><button
								v-if="['Submitted', 'Received'].includes(detail.status)"
								class="button primary"
								:disabled="busy"
								@click="
									doAction('advance', {
										status:
											detail.status === 'Submitted'
												? 'Received'
												: 'Inspected',
										note: form.note,
									})
								"
							>
								{{
									detail.status === "Submitted"
										? "Mark received at HQ"
										: "Mark inspected"
								}}</button
							><template v-if="detail.status === 'Inspected'"
								><label v-for="r in detail.items"
									>{{ r.serial_no
									}}<select v-model="form.decisions[r.serial_no]">
										<option>Approved</option>
										<option>Rejected</option>
									</select></label
								><button
									class="button primary"
									:disabled="busy"
									@click="
										doAction('advance', {
											status: 'Decide',
											note: form.note,
											decisions: form.decisions,
										})
									"
								>
									Save per-reel decisions
								</button></template
							><template
								v-if="['Approved', 'Partly approved'].includes(detail.status)"
								><label
									>Submitted ERPNext credit note<input
										v-model="form.credit_note"
										placeholder="Sales Invoice return reference" /></label
								><button
									class="button"
									:disabled="busy || !form.credit_note"
									@click="
										doAction('link_credit_note', { invoice: form.credit_note })
									"
								>
									Link credit note
								</button></template
							></template
						><button
							v-if="detail.doctype === 'Partner Forecast'"
							class="button primary"
							@click="useSuggestion"
						>
							Create order from suggestion</button
						><a
							v-if="manager"
							class="button"
							:href="
								'/desk/' +
								detail.doctype.toLowerCase().replaceAll(' ', '-') +
								'/' +
								encodeURIComponent(detail.name)
							"
							>Open in ERPNext Desk<ArrowUpRight :size="16"
						/></a>
					</div>
				</div>
			</section>
		</div>
	</div>
</template>
