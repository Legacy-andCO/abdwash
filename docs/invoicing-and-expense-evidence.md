# Revenue invoicing and expense evidence

Trifecta creates an immutable revenue document only after a payment transaction succeeds. Cash
collection therefore changes the customer booking payment state to `paid` immediately; later staff
cash reconciliation is an internal control and cannot change the customer's receipt or payment
status.

## Business financial settings

Managers configure the supplier identity in **Mobile → Services & pricing → Settings**:

- legal and trading name;
- business address, emirate, and country;
- contact email and phone;
- VAT registration status, TRN, VAT rate, and whether catalogue prices include VAT.

VAT registration must not be enabled without a real Trifecta TRN. A VAT-registered configuration
renders `Tax Invoice`; otherwise the document is `Invoice / Payment Receipt` and does not fabricate
VAT registration or tax-invoice wording.

## Numbering and immutable snapshots

Invoice numbers use `TRI-YYYY-NNNNNN`. The `(business, year)` counter is row-locked in the same
database transaction as invoice issuance. The payment transaction is unique on the invoice table,
so an idempotent payment replay cannot issue a second document.

The invoice stores supplier, customer/billing, line item, discount, VAT, total, method, and payment
reference snapshots. Later catalogue, profile, vehicle, or business-setting edits do not rewrite an
issued document.

The payment email links to `/invoice?invoice=<invoice-id>#<booking-management-token>`. The token
remains in the URL fragment and is sent only in `X-Booking-Management-Token`; it is not persisted in
the notification outbox.

## Expense records and source evidence

The expense ledger stores gross, net, and user-entered VAT amounts, supplier/TRN/document metadata,
and an evidence status (`complete`, `missing_evidence`, or `not_required`). Recording VAT does not
assert that it is recoverable.

`GET /api/v1/staff/finance/expenses/{expense_id}/voucher` returns a printable **Internal Expense
Voucher**. It prominently says that it is not a Tax Invoice and does not replace the supplier's
original invoice or receipt. Supplier evidence is uploaded directly to the private
`expense-evidence` Supabase Storage bucket through a short-lived signed upload grant. The API
chooses the object path, validates the completed object's MIME type and size, then marks the ledger
evidence complete. The service-role key never reaches the mobile client. Accepted evidence is PDF,
JPEG, PNG, or WebP and should be retained with the ledger record according to the business's legal
record-retention policy.

The two-step API is:

1. `POST /api/v1/staff/finance/expenses/{expense_id}/evidence/upload` creates an idempotent pending
   record and returns a signed upload token.
2. Upload directly to the returned private bucket/path, then call
   `POST /api/v1/staff/finance/expenses/{expense_id}/evidence/{evidence_id}/complete` so the API
   verifies the stored object before accepting it.

## UAE and future eInvoicing boundary

The invoice snapshot carries the fields needed for human-readable UAE VAT documents when applicable.
The UAE Ministry of Finance states that PDFs, Word files, images, and emails are not structured
eInvoices. Trifecta does not describe its printable HTML/PDF output as an eInvoice. Future accredited
service-provider/structured exchange integration remains a separate phase.

Operational references:

- [FTA Tax Invoices guidance](https://tax.gov.ae/Datafolder/Files/Pdf/2023/Knowledge%20Center%20Page/VAT11%20-%20Tax%20invoices%20En.pdf)
- [VAT Executive Regulation, Article 59](https://tax.gov.ae/Datafolder/Files/Legislation/Executive%20Regulation%20of%20Federal%20Decree%20Law%20No%208%20of%202017%20-%20Publish%2017112022.pdf)
- [UAE Ministry of Finance eInvoicing programme](https://mof.gov.ae/en/about-us/initiatives/einvoicing/)
- [FTA Corporate Tax record-retention reminder](https://tax.gov.ae/en/media.centre/News/pr.28082025.aspx)
