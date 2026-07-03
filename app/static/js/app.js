const defaultDraft = {
  letterhead: {
    company_name: "",
    tagline: "",
    address: "",
    gstin: "",
    mobile: "",
    logo_asset_id: null,
  },
  meta: {
    ref_number: "",
    date: "",
    currency: "INR",
    party_name: "",
    party_address: "",
    attention: "",
    subject: "Quotation",
    intro: "We thank you for the opportunity to submit our quotation.",
  },
  line_items: [
    { description: "", qty: "1", rate: "0", amount: "0", auto: true },
  ],
  terms: {
    payment_terms: "",
    delivery: "",
    warranty: "",
    validity_days: 30,
    tax_note: "GST and transportation extra as applicable.",
  },
  signature: {
    name: "",
    designation: "",
    phone: "",
    signature_asset_id: null,
  },
};

const state = {
  entries: [],
  filters: { q: "", type: "", status: "" },
  draft: structuredClone(defaultDraft),
  assets: { logo: null, signature: null },
  debounceTimer: null,
};

const toast = document.createElement("div");
toast.className = "status-toast";
document.body.appendChild(toast);

const el = {
  tabButtons: [...document.querySelectorAll(".tab-button")],
  tabPanels: {
    registry: document.getElementById("registryPanel"),
    quotation: document.getElementById("quotationPanel"),
  },
  installBtn: document.getElementById("installBtn"),
  syncBanner: document.getElementById("syncBanner"),
  searchInput: document.getElementById("searchInput"),
  typeFilter: document.getElementById("typeFilter"),
  statusFilter: document.getElementById("statusFilter"),
  newEntryBtn: document.getElementById("newEntryBtn"),
  entriesTableBody: document.getElementById("entriesTableBody"),
  entryDialog: document.getElementById("entryDialog"),
  entryDialogTitle: document.getElementById("entryDialogTitle"),
  closeEntryDialogBtn: document.getElementById("closeEntryDialogBtn"),
  cancelEntryBtn: document.getElementById("cancelEntryBtn"),
  entryForm: document.getElementById("entryForm"),
  quotationForm: document.getElementById("quotationForm"),
  lineItems: document.getElementById("lineItems"),
  lineItemTemplate: document.getElementById("lineItemTemplate"),
  addLineItemBtn: document.getElementById("addLineItemBtn"),
  printQuotationBtn: document.getElementById("printQuotationBtn"),
  resetQuotationBtn: document.getElementById("resetQuotationBtn"),
  saveToRegistryBtn: document.getElementById("saveToRegistryBtn"),
  logoUpload: document.getElementById("logoUpload"),
  signatureUpload: document.getElementById("signatureUpload"),
  logoPreview: document.getElementById("logoPreview"),
  signaturePreview: document.getElementById("signaturePreview"),
  removeLogoBtn: document.getElementById("removeLogoBtn"),
  removeSignatureBtn: document.getElementById("removeSignatureBtn"),
};

const Api = {
  async request(path, options = {}) {
    const response = await fetch(path, {
      headers: options.body instanceof FormData ? {} : { "Content-Type": "application/json" },
      ...options,
    });
    if (!response.ok) {
      const text = await response.text();
      throw new Error(text || `Request failed: ${response.status}`);
    }
    const contentType = response.headers.get("content-type") || "";
    return contentType.includes("application/json") ? response.json() : response.text();
  },
  listEntries(params) {
    return this.request(`/api/entries?${new URLSearchParams(params)}`);
  },
  stats() {
    return this.request("/api/entries/stats");
  },
  saveEntry(entry) {
    return this.request(entry._id ? `/api/entries/${entry._id}` : "/api/entries", {
      method: entry._id ? "PUT" : "POST",
      body: JSON.stringify(entry),
    });
  },
  deleteEntry(id) {
    return this.request(`/api/entries/${id}`, { method: "DELETE" });
  },
  draft() {
    return this.request("/api/quotations/draft");
  },
  saveDraft(draft) {
    return this.request("/api/quotations/draft", { method: "PUT", body: JSON.stringify(draft) });
  },
  saveDraftToRegistry(draft) {
    return this.request("/api/quotations/save-to-registry", { method: "POST", body: JSON.stringify(draft) });
  },
  uploadAsset(file, kind) {
    const formData = new FormData();
    formData.append("kind", kind);
    formData.append("file", file);
    return this.request("/api/assets", { method: "POST", body: formData });
  },
  deleteAsset(id) {
    return this.request(`/api/assets/${id}`, { method: "DELETE" });
  },
  followupIcs(id) {
    return this.request(`/api/entries/${id}/followup-ics`, { method: "POST" });
  },
};

function showToast(message) {
  toast.textContent = message;
  toast.classList.add("is-visible");
  clearTimeout(showToast.timer);
  showToast.timer = setTimeout(() => toast.classList.remove("is-visible"), 2200);
}

function debounce(fn, delay = 450) {
  return (...args) => {
    clearTimeout(state.debounceTimer);
    state.debounceTimer = setTimeout(() => fn(...args), delay);
  };
}

function formatCurrency(value, currency = "INR") {
  const numeric = Number(value || 0);
  return `${currency} ${numeric.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function setActiveTab(tab) {
  el.tabButtons.forEach((button) => button.classList.toggle("is-active", button.dataset.tab === tab));
  Object.entries(el.tabPanels).forEach(([name, panel]) => panel.classList.toggle("is-active", name === tab));
}

function computeLineAmount(item) {
  const qty = Number(item.qty || 0);
  const rate = Number(item.rate || 0);
  return (qty * rate).toFixed(2);
}

function totalAmount() {
  return state.draft.line_items.reduce((sum, item) => sum + Number(item.amount || 0), 0);
}

function entryStamp(status) {
  return `stamp stamp-${status.toLowerCase()}`;
}

function isUrgent(entry) {
  if (!entry.deadline || entry.status === "Won" || entry.status === "Lost") return false;
  const today = new Date();
  const deadline = new Date(entry.deadline);
  const diff = Math.ceil((deadline - today) / 86400000);
  return diff <= 3;
}

function textOrDash(value) {
  return value && String(value).trim() ? value : "-";
}

function downloadIcs(text, filename) {
  const blob = new Blob([text], { type: "text/calendar;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

async function loadEntries() {
  const data = await Api.listEntries(state.filters);
  state.entries = data;
  renderEntries();
}

async function loadStats() {
  const stats = await Api.stats();
  document.getElementById("statTotal").textContent = stats.total;
  document.getElementById("statAwaiting").textContent = stats.awaiting_result;
  document.getElementById("statUrgent").textContent = stats.due_for_follow_up;
  document.getElementById("statWon").textContent = stats.won;
  document.getElementById("statRate").textContent = `${stats.win_rate}%`;
  document.getElementById("statValue").textContent = formatCurrency(stats.total_quoted_value, "INR");
}

function renderEntries() {
  if (!state.entries.length) {
    el.entriesTableBody.innerHTML = `<tr><td colspan="8" class="empty-cell">No matching records.</td></tr>`;
    return;
  }
  el.entriesTableBody.innerHTML = state.entries.map((entry) => {
    const email = (entry.contact_person || "").match(/[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/i)?.[0];
    const mailLink = email ? `<a class="entry-action" href="mailto:${email}?subject=${encodeURIComponent(entry.ref_number || entry.title)}">Email</a>` : "";
    const urgent = isUrgent(entry) ? `<span class="stamp stamp-urgent">Urgent</span>` : "";
    return `
      <tr>
        <td><strong>${textOrDash(entry.title)}</strong><br><small>${textOrDash(entry.notes)}</small></td>
        <td>${textOrDash(entry.ref_number)}</td>
        <td>${textOrDash(entry.department)}</td>
        <td>${textOrDash(entry.type)}</td>
        <td><span class="${entryStamp(entry.status)}">${entry.status}</span> ${urgent}</td>
        <td>${textOrDash(entry.deadline)}</td>
        <td>${formatCurrency(entry.amount, entry.currency || "INR")}</td>
        <td>
          <div class="entry-actions">
            <button class="entry-action" type="button" data-action="edit" data-id="${entry._id}">Edit</button>
            <button class="entry-action" type="button" data-action="ics" data-id="${entry._id}">ICS</button>
            ${mailLink}
            <button class="entry-action danger" type="button" data-action="delete" data-id="${entry._id}">Delete</button>
          </div>
        </td>
      </tr>
    `;
  }).join("");
}

function renderLineItems() {
  el.lineItems.innerHTML = "";
  state.draft.line_items.forEach((item, index) => {
    const node = el.lineItemTemplate.content.firstElementChild.cloneNode(true);
    node.dataset.index = index;
    node.querySelector(".line-item-description-input").value = item.description;
    node.querySelector(".line-item-qty").value = item.qty;
    node.querySelector(".line-item-rate").value = item.rate;
    node.querySelector(".line-item-amount").value = item.amount;
    el.lineItems.appendChild(node);
  });
}

function syncDraftToForm() {
  const form = el.quotationForm;
  form.querySelectorAll("[name]").forEach((input) => {
    const [group, key] = input.name.split(".");
    const value = state.draft[group]?.[key];
    input.value = value ?? "";
  });
  renderLineItems();
  syncAssetPreview("logo");
  syncAssetPreview("signature");
  renderPreview();
}

function syncAssetPreview(kind) {
  const preview = kind === "logo" ? el.logoPreview : el.signaturePreview;
  const asset = state.assets[kind];
  if (asset?.data_url) {
    preview.src = asset.data_url;
    preview.hidden = false;
  } else {
    preview.hidden = true;
    preview.removeAttribute("src");
  }
}

function renderPreview() {
  const { letterhead, meta, terms, signature } = state.draft;
  document.getElementById("previewGstin").textContent = `GSTIN: ${textOrDash(letterhead.gstin)}`;
  document.getElementById("previewMobile").textContent = `Mobile: ${textOrDash(letterhead.mobile)}`;
  document.getElementById("previewCompanyName").textContent = textOrDash(letterhead.company_name);
  document.getElementById("previewTagline").textContent = letterhead.tagline ? letterhead.tagline : "";
  document.getElementById("previewAddress").textContent = textOrDash(letterhead.address);
  document.getElementById("previewRef").textContent = `Ref: ${textOrDash(meta.ref_number)}`;
  document.getElementById("previewDate").textContent = `Date: ${textOrDash(meta.date)}`;
  document.getElementById("previewPartyName").textContent = textOrDash(meta.party_name);
  document.getElementById("previewPartyAddress").textContent = textOrDash(meta.party_address);
  document.getElementById("previewAttention").textContent = `Attention: ${textOrDash(meta.attention)}`;
  document.getElementById("previewSubject").textContent = textOrDash(meta.subject);
  document.getElementById("previewIntro").textContent = textOrDash(meta.intro);
  document.getElementById("previewPaymentTerms").textContent = textOrDash(terms.payment_terms);
  document.getElementById("previewDelivery").textContent = textOrDash(terms.delivery);
  document.getElementById("previewWarranty").textContent = textOrDash(terms.warranty);
  document.getElementById("previewValidity").textContent = `${terms.validity_days || 0} days`;
  document.getElementById("previewTaxNote").textContent = textOrDash(terms.tax_note);
  document.getElementById("previewSignatureName").textContent = textOrDash(signature.name);
  document.getElementById("previewSignatureDesignation").textContent = textOrDash(signature.designation);
  document.getElementById("previewSignaturePhone").textContent = textOrDash(signature.phone);
  document.getElementById("previewTotal").textContent = formatCurrency(totalAmount(), meta.currency || "INR");

  const logo = document.getElementById("previewLogo");
  if (state.assets.logo?.data_url) {
    logo.src = state.assets.logo.data_url;
    logo.hidden = false;
    logo.style.display = "";
  } else {
    logo.hidden = true;
    logo.style.display = "none";
    logo.removeAttribute("src");
  }

  const signatureImage = document.getElementById("previewSignature");
  if (state.assets.signature?.data_url) {
    signatureImage.src = state.assets.signature.data_url;
    signatureImage.hidden = false;
    signatureImage.style.display = "";
  } else {
    signatureImage.hidden = true;
    signatureImage.style.display = "none";
    signatureImage.removeAttribute("src");
  }

  document.getElementById("previewItems").innerHTML = state.draft.line_items.map((item, index) => `
    <tr>
      <td>${index + 1}</td>
      <td>${textOrDash(item.description)}</td>
      <td>${textOrDash(item.qty)}</td>
      <td>${formatCurrency(item.rate, meta.currency || "INR")}</td>
      <td>${formatCurrency(item.amount, meta.currency || "INR")}</td>
    </tr>
  `).join("");
}

const saveDraftDebounced = debounce(async () => {
  try {
    await Api.saveDraft(state.draft);
  } catch {
    showToast("Draft save failed.");
  }
}, 500);

function updateDraftFromFormField(input) {
  const [group, key] = input.name.split(".");
  if (!state.draft[group]) return;
  state.draft[group][key] = input.type === "number" ? Number(input.value || 0) : input.value;
  renderPreview();
  saveDraftDebounced();
}

function addLineItem(item = { description: "", qty: "1", rate: "0", amount: "0", auto: true }) {
  state.draft.line_items.push(item);
  renderLineItems();
  renderPreview();
  saveDraftDebounced();
}

function openEntryDialog(entry = null) {
  el.entryDialogTitle.textContent = entry ? "Edit Entry" : "New Entry";
  document.getElementById("entryId").value = entry?._id || "";
  document.getElementById("entryTitle").value = entry?.title || "";
  document.getElementById("entryRefNumber").value = entry?.ref_number || "";
  document.getElementById("entryDepartment").value = entry?.department || "";
  document.getElementById("entryType").value = entry?.type || "Government Tender";
  document.getElementById("entryStatus").value = entry?.status || "Pending";
  document.getElementById("entryDateApplied").value = entry?.date_applied || "";
  document.getElementById("entryDeadline").value = entry?.deadline || "";
  document.getElementById("entryAmount").value = entry?.amount || "";
  document.getElementById("entryCurrency").value = entry?.currency || "INR";
  document.getElementById("entryContactPerson").value = entry?.contact_person || "";
  document.getElementById("entryNotes").value = entry?.notes || "";
  document.getElementById("entryCadence").value = entry?.follow_up_cadence || "none";
  document.getElementById("entryLastFollowUp").value = entry?.last_follow_up || "";
  el.entryDialog.showModal();
}

function closeEntryDialog() {
  el.entryDialog.close();
}

function entryFormPayload() {
  return {
    _id: document.getElementById("entryId").value || undefined,
    title: document.getElementById("entryTitle").value,
    ref_number: document.getElementById("entryRefNumber").value,
    department: document.getElementById("entryDepartment").value,
    type: document.getElementById("entryType").value,
    status: document.getElementById("entryStatus").value,
    date_applied: document.getElementById("entryDateApplied").value || null,
    deadline: document.getElementById("entryDeadline").value || null,
    amount: Number(document.getElementById("entryAmount").value || 0),
    currency: document.getElementById("entryCurrency").value || "INR",
    contact_person: document.getElementById("entryContactPerson").value,
    notes: document.getElementById("entryNotes").value,
    follow_up_cadence: document.getElementById("entryCadence").value,
    last_follow_up: document.getElementById("entryLastFollowUp").value || null,
  };
}

async function handleAssetUpload(kind, file) {
  if (!file) return;
  const result = await Api.uploadAsset(file, kind);
  state.assets[kind] = { _id: result.asset_id, data_url: result.data_url };
  if (kind === "logo") {
    state.draft.letterhead.logo_asset_id = result.asset_id;
  } else {
    state.draft.signature.signature_asset_id = result.asset_id;
  }
  syncAssetPreview(kind);
  renderPreview();
  await Api.saveDraft(state.draft);
  showToast(`${kind === "logo" ? "Logo" : "Signature"} uploaded.`);
}

async function handleAssetRemoval(kind) {
  const asset = state.assets[kind];
  if (asset?._id) {
    await Api.deleteAsset(asset._id);
  }
  state.assets[kind] = null;
  if (kind === "logo") {
    state.draft.letterhead.logo_asset_id = null;
  } else {
    state.draft.signature.signature_asset_id = null;
  }
  syncAssetPreview(kind);
  renderPreview();
  await Api.saveDraft(state.draft);
}

async function bootstrapDraft() {
  const draft = await Api.draft();
  state.draft = {
    ...structuredClone(defaultDraft),
    ...draft,
    letterhead: { ...defaultDraft.letterhead, ...(draft.letterhead || {}) },
    meta: { ...defaultDraft.meta, ...(draft.meta || {}) },
    terms: { ...defaultDraft.terms, ...(draft.terms || {}) },
    signature: { ...defaultDraft.signature, ...(draft.signature || {}) },
    line_items: draft.line_items?.length ? draft.line_items : structuredClone(defaultDraft.line_items),
  };
  syncDraftToForm();
}

function wireTabs() {
  el.tabButtons.forEach((button) => {
    button.addEventListener("click", () => setActiveTab(button.dataset.tab));
  });
}

function wireRegistry() {
  const refresh = debounce(async () => {
    state.filters.q = el.searchInput.value;
    state.filters.type = el.typeFilter.value;
    state.filters.status = el.statusFilter.value;
    await loadEntries();
  }, 250);

  el.searchInput.addEventListener("input", refresh);
  el.typeFilter.addEventListener("change", refresh);
  el.statusFilter.addEventListener("change", refresh);
  el.newEntryBtn.addEventListener("click", () => openEntryDialog());
  el.closeEntryDialogBtn.addEventListener("click", closeEntryDialog);
  el.cancelEntryBtn.addEventListener("click", closeEntryDialog);

  el.entryForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    await Api.saveEntry(entryFormPayload());
    closeEntryDialog();
    await Promise.all([loadEntries(), loadStats()]);
    showToast("Entry saved.");
  });

  el.entriesTableBody.addEventListener("click", async (event) => {
    const target = event.target.closest("[data-action]");
    if (!target) return;
    const entry = state.entries.find((item) => item._id === target.dataset.id);
    if (!entry) return;
    if (target.dataset.action === "edit") {
      openEntryDialog(entry);
      return;
    }
    if (target.dataset.action === "delete") {
      if (!window.confirm(`Delete "${entry.title}"?`)) return;
      await Api.deleteEntry(entry._id);
      await Promise.all([loadEntries(), loadStats()]);
      showToast("Entry deleted.");
      return;
    }
    if (target.dataset.action === "ics") {
      const ics = await Api.followupIcs(entry._id);
      downloadIcs(ics, `${(entry.ref_number || "followup").replaceAll("/", "-")}.ics`);
    }
  });
}

function wireQuotationForm() {
  el.quotationForm.addEventListener("input", (event) => {
    const target = event.target;
    if (!(target instanceof HTMLElement)) return;
    if (target.matches("[name]")) {
      updateDraftFromFormField(target);
      return;
    }
    const lineItem = target.closest(".line-item-card");
    if (!lineItem) return;
    const index = Number(lineItem.dataset.index);
    const item = state.draft.line_items[index];
    if (!item) return;
    item.description = lineItem.querySelector(".line-item-description-input").value;
    item.qty = lineItem.querySelector(".line-item-qty").value;
    item.rate = lineItem.querySelector(".line-item-rate").value;
    const amountInput = lineItem.querySelector(".line-item-amount");
    if (target === amountInput) {
      item.auto = false;
      item.amount = amountInput.value;
    } else {
      if (item.auto !== false) {
        item.amount = computeLineAmount(item);
        amountInput.value = item.amount;
      }
    }
    renderPreview();
    saveDraftDebounced();
  });

  el.lineItems.addEventListener("click", (event) => {
    const button = event.target.closest(".line-item-remove");
    if (!button) return;
    const card = button.closest(".line-item-card");
    const index = Number(card.dataset.index);
    state.draft.line_items.splice(index, 1);
    if (!state.draft.line_items.length) addLineItem();
    renderLineItems();
    renderPreview();
    saveDraftDebounced();
  });

  el.addLineItemBtn.addEventListener("click", () => addLineItem());
  el.printQuotationBtn.addEventListener("click", () => window.print());
  el.resetQuotationBtn.addEventListener("click", async () => {
    state.draft = structuredClone(defaultDraft);
    state.assets = { logo: null, signature: null };
    syncDraftToForm();
    await Api.saveDraft(state.draft);
    showToast("Quotation draft reset.");
  });
  el.saveToRegistryBtn.addEventListener("click", async () => {
    await Api.saveDraftToRegistry(state.draft);
    await Promise.all([loadEntries(), loadStats()]);
    setActiveTab("registry");
    showToast("Quotation saved to registry.");
  });
  el.logoUpload.addEventListener("change", async (event) => handleAssetUpload("logo", event.target.files?.[0]));
  el.signatureUpload.addEventListener("change", async (event) => handleAssetUpload("signature", event.target.files?.[0]));
  el.removeLogoBtn.addEventListener("click", async () => handleAssetRemoval("logo"));
  el.removeSignatureBtn.addEventListener("click", async () => handleAssetRemoval("signature"));
}

function wirePwaInstall() {
  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("/sw.js").catch(() => {});
  }

  let deferredPrompt = null;
  window.addEventListener("beforeinstallprompt", (event) => {
    event.preventDefault();
    deferredPrompt = event;
    el.installBtn.hidden = false;
  });
  el.installBtn.addEventListener("click", async () => {
    if (!deferredPrompt) return;
    deferredPrompt.prompt();
    deferredPrompt = null;
    el.installBtn.hidden = true;
  });

  const syncNetworkState = () => {
    el.syncBanner.hidden = navigator.onLine;
  };
  window.addEventListener("online", syncNetworkState);
  window.addEventListener("offline", syncNetworkState);
  syncNetworkState();
}

async function init() {
  wireTabs();
  wireRegistry();
  wireQuotationForm();
  wirePwaInstall();
  await Promise.all([loadEntries(), loadStats(), bootstrapDraft()]);
}

init().catch((error) => {
  console.error(error);
  showToast("App bootstrap failed. Check API and MongoDB.");
});
