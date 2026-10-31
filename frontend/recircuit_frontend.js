// ReCircuit storefront. Data now comes from the backend API (see api.js); rendering,
// filtering, search and sorting are unchanged from the original prototype.

let listings = [], // global (approved) listings from GET /api/components
	activeCategory = "All",
	me = null, // logged-in user or null
	cart = { items: [], count: 0, total: 0 },
	authMode = "login",
	afterAuth = null; // action to resume after the user logs in

const ROUTES = { "Sell for reuse": "sell", "Donate to students": "donate", "Send for recycling": "recycle" };

// ---------- helpers ----------
const $ = (id) => document.getElementById(id);

function normalize(c) {
	return {
		id: c.id, name: c.name, category: c.category, emoji: c.emoji, price: c.price,
		old: c.original_price, condition: c.condition, tag: c.tag, desc: c.description,
		quantity: c.quantity, image: (c.images || [])[0] || null,
	};
}

function allProducts() {
	return listings;
}

function escapeHtml(s) {
	return String(s).replace(/[&<>"']/g, (c) =>
		({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])
	);
}

function toast(msg) {
	const t = $("toast");
	t.textContent = msg;
	t.classList.add("show");
	clearTimeout(window.toastTimer);
	window.toastTimer = setTimeout(() => t.classList.remove("show"), 2600);
}

function setBusy(btn, busy, label) {
	btn.disabled = busy;
	if (label) btn.textContent = label;
}

// ---------- marketplace ----------
async function loadListings() {
	$("productGrid").innerHTML = '<div class="loading"><div class="spinner"></div>Loading components…</div>';
	try {
		listings = (await api("/api/components")).components.map(normalize);
		renderProducts();
	} catch (e) {
		$("resultCount").textContent = "—";
		$("productGrid").innerHTML = `<div class="empty">⚠️<h3>Couldn't load components</h3><p>${escapeHtml(e.message)}</p><button class="btn btn-light" onclick="loadListings()">Try again</button></div>`;
	}
}

function renderProducts() {
	const q = $("searchInput").value.toLowerCase(),
		sort = $("sortSelect").value,
		cond = $("conditionSelect").value;

	let arr = allProducts().filter(
		(p) =>
			(activeCategory === "All" || p.category === activeCategory) &&
			(p.name.toLowerCase().includes(q) ||
				p.category.toLowerCase().includes(q) ||
				p.desc.toLowerCase().includes(q)) &&
			(cond === "all" || p.condition === cond)
	);

	if (sort === "low") arr.sort((a, b) => a.price - b.price);
	if (sort === "high") arr.sort((a, b) => b.price - a.price);

	$("resultCount").textContent = arr.length + " component" + (arr.length === 1 ? "" : "s");

	const grid = $("productGrid");
	if (!arr.length) {
		grid.innerHTML =
			'<div class="empty">🔎<h3>No components found</h3><p>Try another search or category.</p><button class="btn btn-light" onclick="clearFilters()">Clear filters</button></div>';
		return;
	}

	grid.innerHTML = arr
		.map(
			(p) => `<article class="product">
        <div class="product-visual">
          ${p.image ? `<img src="${escapeHtml(p.image)}" alt="${escapeHtml(p.name)}" loading="lazy">` : `<span>${p.emoji || "🔧"}</span>`}
          <span class="tag">${escapeHtml(p.tag || "New listing")}</span>
          <button class="heart" title="Save item" onclick="toast('Saved to your wishlist (demo)')">♡</button>
        </div>
        <div class="product-body">
          <div class="product-type">${escapeHtml(p.category)}</div>
          <h3>${escapeHtml(p.name)}</h3>
          <div class="condition">${escapeHtml(p.condition + " condition")} · ${p.quantity} available</div>
          <div class="price-row">
            <div>
              <span class="price">${p.price ? "₹" + Number(p.price).toLocaleString("en-IN") : "Free"}</span>
              <small>${p.old > p.price ? `<s>₹${Number(p.old).toLocaleString("en-IN")}</s>` : ""}</small>
            </div>
            <button class="add" aria-label="Add ${escapeHtml(p.name)} to cart" onclick="addToCart(${p.id})">+</button>
          </div>
        </div>
      </article>`
		)
		.join("");
}

function filterCategory(cat, el) {
	activeCategory = cat;
	document.querySelectorAll(".category").forEach((x) => x.classList.remove("active"));
	if (el) el.classList.add("active");
	else if (cat === "All") document.querySelector(".category").classList.add("active");
	renderProducts();
	$("marketplace").scrollIntoView({ behavior: "smooth", block: "start" });
}

function clearFilters() {
	activeCategory = "All";
	$("searchInput").value = "";
	$("conditionSelect").value = "all";
	document.querySelectorAll(".category").forEach((x) => x.classList.remove("active"));
	document.querySelector(".category").classList.add("active");
	renderProducts();
}

// ---------- session / auth ----------
async function refreshSession() {
	try {
		me = (await api("/api/auth/me")).user;
	} catch {
		me = null;
	}
	renderAuthArea();
	await loadCart();
}

function renderAuthArea() {
	const box = $("authArea");
	if (!me) {
		box.innerHTML = '<button class="btn btn-light" onclick="openAuth(\'login\')">Log in</button>';
		return;
	}
	box.innerHTML = `<div class="user-menu" id="userMenu">
      <button class="btn btn-light" onclick="event.stopPropagation();$('userMenu').classList.toggle('open')">👤 ${escapeHtml(me.name.split(" ")[0])} ▾</button>
      <div class="menu">
        <button onclick="openMine()">📦 My submissions</button>
        <button onclick="openProfile()">⚙ Profile</button>
        <button onclick="logout()">↪ Log out</button>
      </div></div>`;
}
document.addEventListener("click", () => {
	const m = $("userMenu");
	if (m) m.classList.remove("open");
});

// Run `action` now if logged in, otherwise ask the user to log in first and resume after.
function requireLogin(message, action) {
	if (me) return action();
	openAuth("login", message, action);
}

function openAuth(mode = "login", message = "", resume = null) {
	afterAuth = resume;
	setAuthMode(mode);
	$("authMsg").textContent = message;
	$("authMsg").classList.toggle("hide", !message);
	$("authModal").classList.add("show");
}
function closeAuth() {
	$("authModal").classList.remove("show");
	afterAuth = null;
}
function setAuthMode(mode) {
	authMode = mode;
	const reg = mode === "register";
	$("authTitle").textContent = reg ? "Join ReCircuit" : "Welcome back";
	$("authBtn").textContent = reg ? "Create account" : "Log in";
	$("tabLogin").classList.toggle("active", !reg);
	$("tabRegister").classList.toggle("active", reg);
	document.querySelectorAll(".register-only").forEach((x) => x.classList.toggle("hide", !reg));
	$("authPassword").autocomplete = reg ? "new-password" : "current-password";
	$("authError").textContent = "";
}

$("authForm").addEventListener("submit", async (e) => {
	e.preventDefault();
	const btn = $("authBtn"), label = btn.textContent;
	$("authError").textContent = "";
	setBusy(btn, true, "Please wait…");
	try {
		const body = { email: $("authEmail").value.trim(), password: $("authPassword").value };
		if (authMode === "register")
			Object.assign(body, { name: $("authName").value, phone: $("authPhone").value, organization: $("authOrg").value });
		me = (await api(authMode === "register" ? "/api/auth/register" : "/api/auth/login", { method: "POST", body })).user;
		const resume = afterAuth;
		afterAuth = null;
		$("authModal").classList.remove("show");
		e.target.reset();
		renderAuthArea();
		await loadCart();
		toast(authMode === "register" ? "Welcome to ReCircuit, " + me.name.split(" ")[0] + "!" : "Logged in.");
		if (resume) resume();
	} catch (err) {
		$("authError").textContent = errorText(err);
	} finally {
		setBusy(btn, false, label);
	}
});

async function logout() {
	try {
		await api("/api/auth/logout", { method: "POST" });
	} catch {}
	me = null;
	cart = { items: [], count: 0, total: 0 };
	renderAuthArea();
	updateCartCount();
	toast("Logged out.");
}

// ---------- profile ----------
function openProfile() {
	$("profEmail").value = me.email;
	$("profName").value = me.name;
	$("profPhone").value = me.phone || "";
	$("profOrg").value = me.organization || "";
	$("profError").textContent = $("pwError").textContent = "";
	$("profileModal").classList.add("show");
}
function closeProfile() {
	$("profileModal").classList.remove("show");
}
$("profileForm").addEventListener("submit", async (e) => {
	e.preventDefault();
	$("profError").textContent = "";
	try {
		me = (await api("/api/profile", { method: "PUT", body: { name: $("profName").value, phone: $("profPhone").value, organization: $("profOrg").value } })).user;
		renderAuthArea();
		closeProfile();
		toast("Profile updated.");
	} catch (err) {
		$("profError").textContent = errorText(err);
	}
});
$("passwordForm").addEventListener("submit", async (e) => {
	e.preventDefault();
	$("pwError").textContent = "";
	try {
		await api("/api/profile/password", { method: "PUT", body: { current_password: $("pwCurrent").value, new_password: $("pwNew").value } });
		e.target.reset();
		toast("Password updated.");
	} catch (err) {
		$("pwError").textContent = errorText(err);
	}
});

// ---------- my submissions ----------
async function openMine() {
	$("mineModal").classList.add("show");
	$("mineList").innerHTML = '<div class="loading"><div class="spinner"></div>Loading…</div>';
	try {
		const items = (await api("/api/my/components")).components;
		if (!items.length) {
			$("mineList").innerHTML = '<div class="empty">You haven\'t submitted anything yet.<p>Use “List a component” to share your spare parts.</p></div>';
			return;
		}
		$("mineList").innerHTML = items
			.map((c) => {
				const label = c.route === "recycle" && c.status === "approved" ? "Accepted for recycling" : c.status;
				const cls = c.route === "recycle" && c.status === "approved" ? "recycle" : c.status;
				return `<div class="sub-item">
          <div style="font-size:26px">${c.images[0] ? `<img src="${escapeHtml(c.images[0])}" alt="" width="44" height="44" style="object-fit:cover;border-radius:8px">` : c.emoji}</div>
          <div class="grow">
            <b>${escapeHtml(c.name)}</b> <span class="badge ${cls}">${escapeHtml(label[0].toUpperCase() + label.slice(1))}</span>
            <div><small>${escapeHtml(c.category)} · ${escapeHtml(c.condition)} · qty ${c.quantity} · ${c.price ? "₹" + c.price : "free"} · submitted ${fmtDate(c.submitted_at)}</small></div>
            ${c.review_note ? `<div class="sub-note"><b>Admin feedback:</b> ${escapeHtml(c.review_note)}</div>` : ""}
          </div>
          ${c.status !== "approved" ? `<button class="btn btn-outline" onclick="withdraw(${c.id})">Withdraw</button>` : ""}
        </div>`;
			})
			.join("");
	} catch (err) {
		$("mineList").innerHTML = `<div class="empty">⚠️ ${escapeHtml(err.message)}</div>`;
	}
}
function closeMine() {
	$("mineModal").classList.remove("show");
}
async function withdraw(id) {
	if (!confirm("Withdraw this submission?")) return;
	try {
		await api("/api/my/components/" + id, { method: "DELETE" });
		toast("Submission withdrawn.");
		openMine();
	} catch (err) {
		toast(err.message);
	}
}

// ---------- cart (server-side, per user) ----------
async function loadCart() {
	if (!me) {
		cart = { items: [], count: 0, total: 0 };
	} else {
		try {
			cart = await api("/api/cart");
		} catch {}
	}
	updateCartCount();
}

function updateCartCount() {
	$("cartCount").textContent = cart.count;
}

function addToCart(id) {
	const p = allProducts().find((x) => x.id === id);
	if (!p) return;
	requireLogin("Log in to add items to your cart.", async () => {
		try {
			cart = await api("/api/cart/items", { method: "POST", body: { component_id: id, quantity: 1 } });
			updateCartCount();
			toast(p.name + " added to cart");
		} catch (err) {
			toast(err.message);
			if (err.status === 404) loadListings();
		}
	});
}

function showCart() {
	requireLogin("Log in to view your cart.", async () => {
		await loadCart();
		$("cartModal").classList.add("show");
		renderCart();
	});
}

function renderCart() {
	const box = $("cartItems"), foot = $("cartFooter");
	if (!cart.items.length) {
		box.innerHTML = '<div class="empty">Your cart is empty.<p>Browse components and add something for your next project.</p></div>';
		foot.innerHTML = "";
		return;
	}
	box.innerHTML = cart.items
		.map(({ component: p, quantity: qty }) => `
      <div style="display:flex;align-items:center;gap:12px;padding:12px 0;border-bottom:1px solid #e7eee9">
        <div style="font-size:28px">${p.images[0] ? `<img src="${escapeHtml(p.images[0])}" alt="" width="40" height="40" style="object-fit:cover;border-radius:8px">` : p.emoji}</div>
        <div style="flex:1">
          <b>${escapeHtml(p.name)}</b>
          <div style="font-size:12px;color:#66766f">₹${p.price} × ${qty}</div>
        </div>
        <button class="btn btn-outline" onclick="changeQty(${p.id},-1)">−</button>
        <button class="btn btn-outline" onclick="changeQty(${p.id},1)">+</button>
      </div>`)
		.join("");
	foot.innerHTML = `
    <div style="display:flex;justify-content:space-between;padding:18px 0;font-size:18px;font-weight:800">
      Estimated total <span>₹${cart.total.toLocaleString("en-IN")}</span>
    </div>
    <div class="notice">Demo checkout only. A real order requires payment integration.</div>
    <button class="btn btn-primary" style="width:100%;margin-top:14px" onclick="checkoutDemo()">Continue (demo)</button>`;
}

async function changeQty(id, n) {
	const line = cart.items.find((l) => l.component.id === id);
	if (!line) return;
	try {
		cart = await api("/api/cart/items/" + id, { method: "PATCH", body: { quantity: Math.max(line.quantity + n, 0) } });
		updateCartCount();
		renderCart();
	} catch (err) {
		toast(err.message);
	}
}

function closeCart() {
	$("cartModal").classList.remove("show");
}

function checkoutDemo() {
	closeCart();
	toast("Demo only — payment/ordering is not part of this prototype.");
}

// ---------- listing submission ----------
function openModal() {
	requireLogin("Log in or sign up to list a component.", () => {
		$("sellError").textContent = "";
		$("sellModal").classList.add("show");
	});
}

function closeModal() {
	$("sellModal").classList.remove("show");
}

$("sellForm").addEventListener("submit", async (e) => {
	e.preventDefault();
	const btn = $("sellBtn"), label = btn.textContent;
	$("sellError").textContent = "";

	const fd = new FormData();
	fd.append("name", $("sellName").value.trim());
	fd.append("category", $("sellCategory").value);
	fd.append("condition", $("sellCondition").value);
	fd.append("quantity", $("sellQty").value);
	fd.append("price", $("sellPrice").value);
	fd.append("route", ROUTES[$("sellRoute").value] || "sell");
	fd.append("description", $("sellNotes").value.trim());
	for (const f of $("sellImages").files) fd.append("images", f);

	setBusy(btn, true, "Submitting…");
	try {
		const c = (await api("/api/components", { method: "POST", form: fd })).component;
		closeModal();
		e.target.reset();
		toast(c.route === "recycle"
			? "Recycling request submitted for review."
			: "Submitted! It will appear in the marketplace once an admin approves it.");
	} catch (err) {
		if (err.status === 401) {
			me = null; renderAuthArea();
			closeModal();
			openAuth("login", "Your session expired. Please log in again.");
		} else $("sellError").textContent = errorText(err);
	} finally {
		setBusy(btn, false, label);
	}
});

// ---------- boot ----------
loadListings();
refreshSession();
