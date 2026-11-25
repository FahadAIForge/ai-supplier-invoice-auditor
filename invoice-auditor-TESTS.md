# AI Supplier Invoice Auditor — tests (run after import + activation)

Workflow: AI Supplier Invoice Auditor
- Workflow ID: 4GMvyeeIodEgf8ih (n8n 2.47.7, activeVersionId e92d141c-5a6d-4bc1-99b7-b03846bfe8ae)
- Editor: https://chuck-jumbo-compress.ngrok-free.dev/workflow/4GMvyeeIodEgf8ih
- Webhook: POST https://chuck-jumbo-compress.ngrok-free.dev/webhook/invoice-audit
  (multipart/form-data: restaurant_name + invoice_pdf; returns an HTML audit report)
- 14 nodes: README Note → Webhook (Upload Invoice) → Extract PDF Text →
  Extract Invoice Data (Information Extractor + Groq) → Parse Invoice JSON →
  Check Maths → Agreed Price List (Set) → Check Prices → Route Audit (IF) →
  Audit Summary (AI Agent) / Clean Summary (Set) → Build HTML Report →
  Respond — Audit Report. Groq Chat Model (openai/gpt-oss-120b, maxTokens 8000).
- Demo: Spice House restaurant, supplier City Foods Wholesale. Tax 5% on all tests.
- Limit: digital PDFs only — scanned/photo invoices do not work (Groq is text-only).

Agreed price list (static JSON in Agreed Price List node, $/kg unless noted):
tomatoes $3.50, onions $1.20, potatoes $0.90, chicken breast $6.80,
basmati rice $2.40, cooking oil $4.10/litre, fresh chillies $2.90,
garlic $3.10, ginger $4.60, lemons $1.80.

## Live tests (5, run 2026-11-25 ~09:25 PST, all HTTP 200, all success)

- A test-a-clean.pdf, INV-2501, 23 Nov 2026 → CLEAN, $0.00 overcharge.
  Tomatoes 40kg×$3.50=$140, Onions 25kg×$1.20=$30, Basmati Rice 20kg×$2.40=$48.
  Subtotal $218.00, tax $10.90, grand $228.90. Execution 132.
- B test-b-overcharged.pdf, INV-2502, 24 Nov 2026 (Tuesday) → OVERCHARGED $42.00.
  Tomatoes 60kg×$4.20=$252 (agreed $3.50) — $42.00 overcharge. Onions 20kg×$1.20=$24,
  Potatoes 30kg×$0.90=$27. Subtotal $303.00, tax $15.15, grand $318.15. Execution 133.
- C test-c-math-error.pdf, INV-2503, 24 Nov 2026 → MATH ERROR.
  Chicken Breast 10kg×$6.80 stated $86.00 (should be $68.00, difference $18.00);
  subtotal also wrong by $18.00. Garlic 5kg×$3.10=$15.50, Lemons 10kg×$1.80=$18.00.
  Subtotal $119.50, tax $5.98, grand $125.48. Execution 134.
- D test-d-no-rate.pdf, INV-2504, 25 Nov 2026 → FLAGGED, $0.00 overcharge.
  Saffron 0.5kg×$180.00=$90.00 — no agreed rate on file. Tomatoes 30kg×$3.50=$105,
  Ginger 8kg×$4.60=$36.80. Subtotal $231.80, tax $11.59, grand $243.39. Execution 135.
- E test-e-duplicate.pdf, INV-2505, 25 Nov 2026 → OVERCHARGED $87.50.
  Tomatoes 25kg billed twice (two identical $87.50 lines). Cooking Oil 10 litre×$4.10=$41.
  Subtotal $216.00, tax $10.80, grand $226.80. Execution 136.

Verdict priority: math errors → MATH ERROR; else overcharge > 0 → OVERCHARGED;
else unknown rates → FLAGGED; else CLEAN. 5/5 verdicts correct on the first
passing run (after the two fixes below).

## Build problems found and fixed (do not repeat)

1. Respond to Webhook is NOT supported in form-trigger workflows (n8n 2.47.7):
   `validateResponseModeConfiguration` throws when a Respond node is connected
   and Form Trigger typeVersion > 2.1. Trigger switched to a plain Webhook node
   (path "invoice-audit", responseMode "responseNode") + Respond to Webhook
   (respondWith text, responseBody `={{ $json.html }}`, Content-Type text/html).
2. Form Trigger responseMode "lastNode" returns an EMPTY response
   (responseData "noData") — the workflow runs but the report never comes back.
   Execution 126 succeeded with a 0-byte response. That is why the webhook
   switch was needed, not just a workaround.
3. Form Trigger v2.6 custom path lives in `options.path`, not top-level `path`.
4. Startup activation does NOT recreate `webhook_entity` rows for this workflow.
   Manually inserted: (workflowId, 'invoice-audit', 'POST', 'Upload Invoice').
   Re-check the row before the 21:00 run; re-insert if missing.
5. Extract from File (PDF) outputs the text in the `text` field, NOT `data`.
   Information Extractor text parameter must be `={{ $json.text}}`.
6. The Information Extractor returns the structured data as an OBJECT under
   `output` (not a JSON string). Parse Invoice JSON must handle
   `typeof raw.output === 'object'` directly — `.toString()` gives
   "[object Object]" and JSON.parse fails silently to an empty invoice
   (all 5 tests then return CLEAN $0.00 with an empty table — executions 127-131).
7. The Set node ("Agreed Price List", v3.5) does NOT pass through upstream
   fields — Check Prices must read the maths result via
   `$('Check Maths').first().json`, not `$json.mathErrors`
   (execution 125: "Cannot read properties of undefined (reading 'length')"
   at Check Prices line 28).

DB backup: ~/workspace/n8n-stack/database.sqlite.bak-2026-11-25-invoice-auditor
