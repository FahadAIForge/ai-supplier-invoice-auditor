#!/usr/bin/env python3
"""Build AI Supplier Invoice Auditor workflow JSON (14 nodes) for the
2026-11-26 PKT daily LinkedIn showcase (Wed 25 Nov 21:00 PST post).

Replaces the dropped AI Stock Reorder Assistant (Fahad: too simple, same
concept). New pick: staff uploads a supplier invoice PDF on a form; Groq
extracts the line items; Code nodes check the maths and compare prices
against an agreed price list; an AI agent writes a plain-language audit;
the workflow returns an HTML audit report document. Nobody is messaged.

Trigger is a plain Webhook node (multipart form-data: restaurant_name +
invoice_pdf) with a Respond to Webhook node returning the HTML report.
A Form Trigger was tried first and does NOT work in n8n 2.47 for this:
(1) a Respond to Webhook node in a form-trigger workflow throws
"not supported"; (2) responseMode "lastNode" returns an empty response
(responseData "noData") - the workflow runs but the report never comes
back. No Gmail/Sheets nodes: the VM egress proxy blocks gmail/sheets
APIs. Digital PDFs only (Groq is text-only).
Demo business: Spice House restaurant, supplier City Foods Wholesale.
"""
import json, uuid

def uid():
    return str(uuid.uuid4())

N = {}
def node(name, ntype, version, x, y, params=None, creds=None, notes=None):
    d = {"id": uid(), "name": name, "type": ntype, "typeVersion": version,
         "position": [x, y]}
    if notes:
        d["notes"] = notes
    if creds:
        d["credentials"] = creds
    d["parameters"] = params or {}
    N[name] = d
    return d

GROQ_CREDS = {"groqApi": {"id": "7JX1ltl0qs1xrSEY", "name": "Groq account"}}

PRICE_LIST = {
    "tomatoes": 3.50, "onions": 1.20, "potatoes": 0.90,
    "chicken breast": 6.80, "basmati rice": 2.40, "cooking oil": 4.10,
    "fresh chillies": 2.90, "garlic": 3.10, "ginger": 4.60, "lemons": 1.80,
}

INVOICE_SCHEMA = {
    "type": "object",
    "properties": {
        "supplier": {"type": "string", "description": "Name of the supplier company"},
        "invoiceNumber": {"type": "string", "description": "Invoice number as written"},
        "invoiceDate": {"type": "string", "description": "Invoice date as written"},
        "dueDate": {"type": "string", "description": "Payment due date as written"},
        "lineItems": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "item": {"type": "string"},
                    "quantity": {"type": "number"},
                    "unit": {"type": "string"},
                    "unitPrice": {"type": "number"},
                    "lineTotal": {"type": "number"}
                },
                "required": ["item", "quantity", "unitPrice", "lineTotal"]
            }
        },
        "subtotal": {"type": "number"},
        "tax": {"type": "number"},
        "grandTotal": {"type": "number"}
    },
    "required": ["supplier", "invoiceNumber", "lineItems", "subtotal", "grandTotal"]
}

node("README Note", "n8n-nodes-base.stickyNote", 1, 0, 0, {
    "color": 4,
    "content": "## AI Supplier Invoice Auditor (demo: Spice House restaurant, supplier City Foods Wholesale)\nStaff uploads a supplier invoice PDF on a form - Groq extracts the line items, Code nodes check the maths and compare every price against the agreed price list, an AI agent writes a plain-language audit, and the workflow returns an HTML audit report document. No email/sheet step (no Google APIs on this VM). Digital PDFs only.",
    "height": 280, "width": 420})

node("Upload Invoice", "n8n-nodes-base.webhook", 2, 0, 320, {
    "httpMethod": "POST", "options": {}, "path": "invoice-audit",
    "responseMode": "responseNode"},
    notes="POST a PDF here (multipart): restaurant_name + invoice_pdf.")
N["Upload Invoice"]["webhookId"] = uid()

node("Extract PDF Text", "n8n-nodes-base.extractFromFile", 1.2, 260, 320, {
    "operation": "pdf",
    "binaryPropertyName": "invoice_pdf"})

node("Extract Invoice Data", "@n8n/n8n-nodes-langchain.informationExtractor", 1.2, 520, 320, {
    "text": "={{ $json.text }}",
    "schemaType": "manual",
    "inputSchema": json.dumps(INVOICE_SCHEMA),
    "options": {"systemPromptTemplate": "You are an invoice data extractor for a small restaurant. Read the supplier invoice text and extract the supplier name, invoice number, invoice date, due date, every line item (item name, quantity, unit, unit price, line total), subtotal, tax and grand total. Copy numbers exactly as written - never calculate or round them yourself."}})

node("Parse Invoice JSON", "n8n-nodes-base.code", 2, 780, 320, {
    "jsCode": """const raw = $json;
let inv = {};
if (raw.lineItems && Array.isArray(raw.lineItems)) {
  inv = raw;
} else if (raw.output) {
  if (typeof raw.output === 'object') {
    inv = raw.output;
  } else {
    const s = raw.output.toString().trim().replace(/^```(?:json)?\\s*/i, '').replace(/\\s*```$/, '').trim();
    try { inv = JSON.parse(s); } catch (e) { inv = {}; }
  }
}
const up = $('Upload Invoice').first().json;
const shop = ((up.body && up.body.restaurant_name) || 'Spice House').toString();
const num = (v) => { const n = parseFloat(String(v === undefined || v === null ? '' : v).replace(/[^0-9.\\-]/g, '')); return isNaN(n) ? 0 : n; };
const items = (inv.lineItems || []).map(li => ({
  item: (li.item || '').toString(),
  quantity: num(li.quantity),
  unit: (li.unit || '').toString(),
  unitPrice: num(li.unitPrice),
  lineTotal: num(li.lineTotal)
}));
return [{ json: {
  shop,
  supplier: (inv.supplier || '').toString(),
  invoiceNumber: (inv.invoiceNumber || '').toString(),
  invoiceDate: (inv.invoiceDate || '').toString(),
  dueDate: (inv.dueDate || '').toString(),
  lineItems: items,
  subtotal: num(inv.subtotal),
  tax: num(inv.tax),
  grandTotal: num(inv.grandTotal)
} }];"""})

node("Check Maths", "n8n-nodes-base.code", 2, 1040, 320, {
    "jsCode": """const v = $('Parse Invoice JSON').first().json;
const round2 = (n) => Math.round(n * 100) / 100;
const mathErrors = [];
let computedSubtotal = 0;
const lines = v.lineItems.map(li => {
  const expected = round2(li.quantity * li.unitPrice);
  computedSubtotal = round2(computedSubtotal + expected);
  const diff = round2(expected - li.lineTotal);
  if (Math.abs(diff) > 0.01) {
    mathErrors.push({ item: li.item, expected, stated: li.lineTotal, difference: diff });
  }
  return { item: li.item, quantity: li.quantity, unit: li.unit, unitPrice: li.unitPrice, lineTotal: li.lineTotal, expectedLineTotal: expected, lineOk: Math.abs(diff) <= 0.01 };
});
computedSubtotal = round2(computedSubtotal);
const subDiff = round2(computedSubtotal - v.subtotal);
if (Math.abs(subDiff) > 0.01) {
  mathErrors.push({ item: 'SUBTOTAL', expected: computedSubtotal, stated: v.subtotal, difference: subDiff });
}
const expectedGrand = round2(v.subtotal + v.tax);
const grandDiff = round2(expectedGrand - v.grandTotal);
if (Math.abs(grandDiff) > 0.01) {
  mathErrors.push({ item: 'GRAND TOTAL', expected: expectedGrand, stated: v.grandTotal, difference: grandDiff });
}
return [{ json: { shop: v.shop, supplier: v.supplier, invoiceNumber: v.invoiceNumber, invoiceDate: v.invoiceDate, dueDate: v.dueDate, lineItems: lines, subtotal: v.subtotal, tax: v.tax, grandTotal: v.grandTotal, computedSubtotal, mathErrors, mathOk: mathErrors.length === 0 } }];"""})

node("Agreed Price List", "n8n-nodes-base.set", 3.5, 1300, 320, {
    "mode": "manual",
    "assignments": {"assignments": [
        {"id": uid(), "name": "priceList", "type": "object",
         "value": json.dumps(PRICE_LIST)}]},
    "include": "all",
    "options": {}},
    notes="Agreed rates with City Foods Wholesale (per kg / per litre).")

node("Check Prices", "n8n-nodes-base.code", 2, 1560, 320, {
    "jsCode": """const m = $('Check Maths').first().json;
const priceList = $json.priceList || {};
const norm = (s) => (s || '').toString().toLowerCase().trim();
const seen = {};
const priceFlags = [];
let totalOvercharge = 0;
const mathErrors = m.mathErrors || [];
const lines = (m.lineItems || []).map(li => {
  const key = norm(li.item);
  const agreed = priceList[key];
  let flag = null;
  if (seen[key]) {
    totalOvercharge = Math.round((totalOvercharge + li.lineTotal) * 100) / 100;
    flag = { type: 'duplicate', item: li.item, note: 'Billed twice - this item appears ' + (seen[key] + 1) + ' times on the invoice', amount: li.lineTotal };
    priceFlags.push(flag);
  }
  seen[key] = (seen[key] || 0) + 1;
  if (agreed === undefined || agreed === null) {
    flag = { type: 'no-rate', item: li.item, note: 'No agreed rate on file - this price cannot be verified', amount: 0 };
    priceFlags.push(flag);
  } else if (li.unitPrice > agreed) {
    const over = Math.round((li.unitPrice - agreed) * li.quantity * 100) / 100;
    totalOvercharge = Math.round((totalOvercharge + over) * 100) / 100;
    flag = { type: 'overcharge', item: li.item, agreed, billed: li.unitPrice, quantity: li.quantity, amount: over };
    priceFlags.push(flag);
  }
  return { item: li.item, quantity: li.quantity, unit: li.unit, unitPrice: li.unitPrice, lineTotal: li.lineTotal, expectedLineTotal: li.expectedLineTotal, lineOk: li.lineOk, agreed: (agreed !== undefined && agreed !== null) ? agreed : null, flag: flag ? flag.type : null };
});
const hasIssues = mathErrors.length > 0 || priceFlags.length > 0;
let verdict = 'CLEAN';
if (mathErrors.length > 0) verdict = 'MATH ERROR';
else if (totalOvercharge > 0) verdict = 'OVERCHARGED';
else if (priceFlags.length > 0) verdict = 'FLAGGED';
return [{ json: { shop: m.shop, supplier: m.supplier, invoiceNumber: m.invoiceNumber, invoiceDate: m.invoiceDate, dueDate: m.dueDate, lineItems: lines, subtotal: m.subtotal, tax: m.tax, grandTotal: m.grandTotal, computedSubtotal: m.computedSubtotal, mathErrors: mathErrors, mathOk: m.mathOk, priceFlags, totalOvercharge, hasIssues, verdict } }];"""})

node("Route Audit", "n8n-nodes-base.if", 2.2, 1820, 320, {
    "conditions": {
        "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose", "version": 2},
        "conditions": [{"id": uid(), "leftValue": "={{ $json.hasIssues }}",
            "rightValue": True, "operator": {"type": "boolean", "operation": "equals"}}],
        "combinator": "and"},
    "looseTypeValidation": False,
    "options": {}})

node("Audit Summary", "@n8n/n8n-nodes-langchain.agent", 3.1, 2080, 160, {
    "promptType": "define",
    "text": "={{ '<context>Spice House is a small restaurant. City Foods Wholesale sent invoice ' + $json.invoiceNumber + ' dated ' + $json.invoiceDate + '.</context><task>Write a plain-language audit summary for the restaurant owner.</task><input>Supplier: ' + $json.supplier + '. Invoice total: $' + $json.grandTotal + '. Verdict: ' + $json.verdict + '. Total overcharge found: $' + $json.totalOvercharge + '. Maths errors: ' + JSON.stringify($json.mathErrors) + '. Price flags: ' + JSON.stringify($json.priceFlags) + '.</input><format>3-5 short bullet lines, plain English, no jargon. Say what was overcharged and by how much, what to dispute with the supplier, and what to check next time.</format><rules>Use ONLY the numbers in the input. Never invent an item, a price, or a date. Under 120 words. Return only the summary text, no JSON, no markdown headings.</rules>' }}",
    "options": {"systemMessage": "You are an invoice auditor for a small restaurant. The owner wants a plain-language summary of what is wrong with a supplier invoice. Write 3-5 short bullet lines: what was overcharged and by how much, what to dispute with the supplier, and what to check next time. Use ONLY the facts and numbers given - never invent an item, a price, or a date. Under 120 words. Return only the summary text, no JSON, no markdown headings."}})

node("Clean Summary", "n8n-nodes-base.set", 3.5, 2080, 480, {
    "mode": "manual",
    "assignments": {"assignments": [
        {"id": uid(), "name": "output", "type": "string",
         "value": "No issues found. Every line total matches quantity x unit price, the subtotal and grand total add up, and every item was billed at the agreed rate. Nothing to dispute on this invoice."}]},
    "include": "all",
    "options": {}})

node("Build HTML Report", "n8n-nodes-base.code", 2, 2340, 320, {
    "jsCode": """const v = $('Check Prices').first().json;
const summary = ($json.output || '').toString();
const esc = (s) => String(s === undefined || s === null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
const money = (n) => '$' + Number(n || 0).toFixed(2);
const banner = {
  'CLEAN': ['CLEAN - nothing to dispute', '#15803d', '#dcfce7'],
  'OVERCHARGED': ['OVERCHARGED - ' + money(v.totalOvercharge), '#b91c1c', '#fee2e2'],
  'MATH ERROR': ['MATH ERROR - totals do not add up', '#b45309', '#fef3c7'],
  'FLAGGED': ['FLAGGED - needs a human check', '#6b21a8', '#f3e8ff']
}[v.verdict] || ['AUDITED', '#334155', '#e2e8f0'];
const rows = (v.lineItems || []).map(li => {
  const flag = li.flag === 'overcharge' ? 'OVERCHARGED' : li.flag === 'duplicate' ? 'BILLED TWICE' : li.flag === 'no-rate' ? 'NO AGREED RATE' : (!li.lineOk ? 'MATH ERROR' : '');
  return '<tr><td>' + esc(li.item) + '</td><td>' + li.quantity + ' ' + esc(li.unit) + '</td><td>' + money(li.unitPrice) + '</td><td>' + money(li.lineTotal) + '</td><td>' + (li.agreed !== null && li.agreed !== undefined ? money(li.agreed) : '-') + '</td><td>' + flag + '</td></tr>';
}).join('');
const flags = (v.priceFlags || []).concat((v.mathErrors || []).map(e => ({ type: 'math', item: e.item, note: 'Expected ' + money(e.expected) + ', stated ' + money(e.stated) + ' (difference ' + money(e.difference) + ')', amount: e.difference })));
const flagList = flags.length ? flags.map(f => '<li><b>' + esc(f.item) + ':</b> ' + esc(f.note || (f.type + ' - ' + money(f.amount))) + '</li>').join('') : '<li>None - every line checked out.</li>';
const html = '<!DOCTYPE html><html><head><meta charset="utf-8"><title>Invoice Audit - ' + esc(v.invoiceNumber) + '</title><style>body{font-family:Arial,sans-serif;background:#f1f5f9;margin:0;padding:24px;color:#0f172a}.card{max-width:760px;margin:0 auto;background:#fff;border-radius:12px;padding:28px;box-shadow:0 2px 12px rgba(0,0,0,.08)}h1{margin:0 0 4px;font-size:22px}.sub{color:#64748b;margin:0 0 16px}.banner{border-radius:8px;padding:12px 16px;font-weight:700;font-size:17px;color:' + banner[1] + ';background:' + banner[2] + ';margin-bottom:16px}table{width:100%;border-collapse:collapse;margin:12px 0}th,td{border-bottom:1px solid #e2e8f0;padding:8px 6px;text-align:left;font-size:14px}th{color:#64748b;font-size:12px;text-transform:uppercase}.totals{text-align:right;font-size:15px;line-height:1.7}.totals b{font-size:17px}h2{font-size:16px;margin:20px 0 6px}ul{margin:6px 0;padding-left:20px;line-height:1.6}.foot{color:#94a3b8;font-size:12px;margin-top:20px}</style></head><body><div class="card"><h1>Supplier Invoice Audit</h1><p class="sub">' + esc(v.shop) + ' &middot; Supplier: ' + esc(v.supplier) + ' &middot; Invoice ' + esc(v.invoiceNumber) + ' &middot; ' + esc(v.invoiceDate) + ' &middot; Due ' + esc(v.dueDate) + '</p><div class="banner">' + banner[0] + '</div><table><tr><th>Item</th><th>Qty</th><th>Unit price</th><th>Line total</th><th>Agreed rate</th><th>Flag</th></tr>' + rows + '</table><div class="totals">Subtotal: ' + money(v.subtotal) + '<br>Tax: ' + money(v.tax) + '<br><b>Grand total: ' + money(v.grandTotal) + '</b><br>Total overcharge found: <b>' + money(v.totalOvercharge) + '</b></div><h2>Findings</h2><p>' + esc(summary).replace(/\\n/g, '<br>') + '</p><h2>What to check</h2><ul>' + flagList + '</ul><p class="foot">Audit by AI Supplier Invoice Auditor - digital PDF invoices only.</p></div></body></html>';
return [{ json: { html, verdict: v.verdict, invoiceNumber: v.invoiceNumber, totalOvercharge: v.totalOvercharge } }];"""})

node("Respond — Audit Report", "n8n-nodes-base.respondToWebhook", 1.1, 2600, 320, {
    "respondWith": "text",
    "responseBody": "={{ $json.html }}",
    "options": {"responseHeaders": {"entries": [
        {"name": "Content-Type", "value": "text/html; charset=utf-8"}]}}})

node("Groq Chat Model", "@n8n/n8n-nodes-langchain.lmChatGroq", 1, 1300, 80, {
    "model": "openai/gpt-oss-120b",
    "options": {"temperature": 0.3, "maxTokensToSample": 8000}}, creds=GROQ_CREDS)

order = ["README Note", "Upload Invoice", "Extract PDF Text",
         "Extract Invoice Data", "Parse Invoice JSON", "Check Maths",
         "Agreed Price List", "Check Prices", "Route Audit", "Audit Summary",
         "Clean Summary", "Build HTML Report", "Respond — Audit Report",
         "Groq Chat Model"]

connections = {
    "Upload Invoice": {"main": [[{"index": 0, "node": "Extract PDF Text", "type": "main"}]]},
    "Extract PDF Text": {"main": [[{"index": 0, "node": "Extract Invoice Data", "type": "main"}]]},
    "Extract Invoice Data": {"main": [[{"index": 0, "node": "Parse Invoice JSON", "type": "main"}]]},
    "Parse Invoice JSON": {"main": [[{"index": 0, "node": "Check Maths", "type": "main"}]]},
    "Check Maths": {"main": [[{"index": 0, "node": "Agreed Price List", "type": "main"}]]},
    "Agreed Price List": {"main": [[{"index": 0, "node": "Check Prices", "type": "main"}]]},
    "Check Prices": {"main": [[{"index": 0, "node": "Route Audit", "type": "main"}]]},
    "Route Audit": {"main": [
        [{"index": 0, "node": "Audit Summary", "type": "main"}],
        [{"index": 0, "node": "Clean Summary", "type": "main"}]]},
    "Audit Summary": {"main": [[{"index": 0, "node": "Build HTML Report", "type": "main"}]]},
    "Clean Summary": {"main": [[{"index": 0, "node": "Build HTML Report", "type": "main"}]]},
    "Build HTML Report": {"main": [[{"index": 0, "node": "Respond — Audit Report", "type": "main"}]]},
    "Groq Chat Model": {"ai_languageModel": [[
        {"index": 0, "node": "Extract Invoice Data", "type": "ai_languageModel"},
        {"index": 0, "node": "Audit Summary", "type": "ai_languageModel"}]]},
}

wf = {"active": False, "connections": connections,
      "name": "AI Supplier Invoice Auditor",
      "nodes": [N[n] for n in order],
      "pinData": {}, "settings": {"executionOrder": "v1"}}

out = "/home/hatch/workspace/linkedin/staged/2026-11-25-invoice-auditor/invoice-auditor.json"
with open(out, "w") as f:
    json.dump(wf, f, indent=2, ensure_ascii=False)
print("wrote", out, "nodes:", len(wf["nodes"]))
