# Trifecta financial pass 1

Alembic revision `a19772ea5f12` was applied and financially reconciled on the existing `trifecta-staging` project on 18 November 2026. For all four improvement passes, use project `mgfzfgvlrxwyyftwukwf` exclusively for database development, migrations and tests. The local PostgreSQL results below predate that staging-only instruction.

## Findings and financial rules

| Prior behaviour | Correction |
|---|---|
| The finance overview counted unpaid future bookings. Two reports derived debt by subtracting collections from booked sales. | The overview, both reports, job detail and outstanding list share a booking-level ledger calculation. A receivable appears only when the booking and job are completed and the result is positive. |
| Recording cash paid the entire booking, issued its invoice and triggered loyalty processing. | A collection creates a pending transaction with its collector, server timestamp, amount and retry key. Verification settles debt. Full settlement issues the booking invoice and runs the existing customer notification and loyalty workflow. |
| A handover consumed entire receipt links even when the employee handed in less cash. A refund anywhere on the booking could hide every cash receipt on it. | Each active handover link records the exact cash allocated. A void releases its allocations and retains the historical rows. A customer refund alone is insufficient evidence that an employee physically paid it out. |
| A payment method on the booking could describe only one tender. | Individual cash and card transactions carry their own amounts and statuses. The settled header can identify a mixed payment. |
| The collection sheet put web sizing and scrolling rules on the scroll content. | The viewport bounds the scroll container. Content accommodates the keyboard, safe areas, English and RTL Arabic. Card reference and a receipt screenshot are optional. |

**Customer balance.** All calculations use integer minor units. Start with the payment charge, add successful debit adjustments and subtract successful credit adjustments. Subtract successful receipts, including deposits, and add successful refunds, reversals and voids. Floor each completed booking’s balance at zero before summing. A pending submission reserves its amount against further collection. Rejection releases that reservation. Neither decision about cash custody nor the handover amount changes the customer balance.

**Physical cash.** A cash receipt increases its collector’s custody by the amount retained after change. Subtract the amounts allocated to active handovers. Card, gateway and transfer receipts contribute zero. A rejection leaves reported physical custody in place until the cash is accounted for. This pass supplies no employee cash-disbursement or cash-write-off workflow.

**Review.** Managers and admins open Reports → Finance → Payments → Payment history. Pending submissions appear first. Review shows the booking, customer, collector, amount, method, optional reference and image, timestamps and outcome. Confirmation or rejection uses the existing privileged MFA dependency. Rejection requires a reason. Review records the reviewer and server time. Repeated matching decisions can replay successfully. Conflicting decisions return a conflict.

**Evidence.** The API validates and size-limits optional JPEG evidence, stores it on the existing payment transaction and returns it through a tenant-scoped manager endpoint. The client asks for a receipt with card details hidden. The upload and reference fields are intended for transaction evidence. No provider API was added.

## Migration and files

Alembic revision `a19772ea5f12` extends `payment_transactions` and `cash_reconciliation_payments`. Its upgrade seeds a receipt for historical paid headers missing a successful receipt, allocates historical declared cash across linked receipts in collection order, and preserves the original reconciliation totals and timestamps. The old one-active-link index gives way to amount-based allocations, serialized writes and database triggers. Downgrade checks for financial facts the old schema cannot preserve.

| Area | Changed files |
|---|---|
| Migration and models | `backend/migrations/versions/a19772ea5f12_payment_reviews_and_cash_allocations.py`, `backend/app/models/entities.py` |
| API and contracts | `backend/app/api/staff.py`, `backend/app/schemas/finance.py`, `backend/app/schemas/staff.py` |
| Services | `backend/app/services/payment_balances.py`, `finance.py`, `staff_operations.py`, `workforce.py`, `invoices.py` |
| Mobile | `apps/mobile/src/components/CashTenderModal.tsx`, `components/PaymentReviewList.tsx`, `screens/FinanceScreen.tsx`, `screens/JobsScreen.tsx`, `lib.ts`, `cash/cashTender.ts`, `finance/financeState.ts`, `staff-translations.ts` |
| Regression tests | Backend booking archive, finance, loyalty/cash, PostgreSQL integration, security PostgreSQL and staff-calendar PostgreSQL tests. Mobile finance state and functional UI contract tests. |

## Verification

| Environment | Result |
|---|---|
| Disposable PostgreSQL 17.11, FastAPI, Alembic and security suite | 492 passed, including migration round trip, restricted runtime role, authorization and MFA. Two dependency deprecation warnings. |
| Mobile and customer web | 194 mobile and 230 web tests passed. Workspace TypeScript checks passed. Backend strict mypy passed across 105 source files. |
| Collection sheet | Chrome rendered the React Native Web component at 320×568, 390×844, 430×932 and 740×360. Both languages accepted amounts and enabled submission. Controls remained within the viewport horizontally. The capture harness supplied fixture data and stubbed the system photo picker. |
| Hosted trifecta-staging | All 44 pre-migration payment headers matched the encrypted backup field by field. The migration added one AED 50.00 receipt for a historical paid header. Both database guards were enabled. The authenticated FastAPI workflow ran against hosted PostgreSQL with real staging Auth and manager TOTP. |

PostgreSQL tests covered unpaid completed jobs, scheduled exclusions, partial and full verification, rejection, pending reservations, mixed methods, unreferenced cards, referenced cards, JPEG round-trip, retries, concurrent confirmations and competing confirm/reject decisions. The adjustment fixture combined a 50.00 charge, 20.00 deposit, 3.00 refund, 5.00 credit and 1.00 debit. All three reporting endpoints returned 29.00 outstanding and 17.00 collected. The restricted-role test collected 50.00 cash, confirmed it, handed over 20.00 and read 30.00 remaining from the API.

[English cash, 320×568](en-320x568.png) · [Arabic card, 390×844](ar-390x844.png) · [English card, 430×932](en-430x932.png) · [Arabic landscape, 740×360](ar-740x360.png)

## Hosted reconciliation

Before migration, a read-only repeatable-read transaction captured payments, payment transactions, cash reconciliations, receipt allocations and revenue invoices. The backup was encrypted with Windows DPAPI CurrentUser and decrypt-checked. The migration acquired write-conflicting locks and checked the starting revision and SHA-256 digest of each table against the backup. The encrypted file is at `%LOCALAPPDATA%\Trifecta\StagingBackups\mgfzfgvlrxwyyftwukwf\pre-a19772ea5f12.json.dpapi`. Its SHA-256 is `FCC73994B00DEF3452A80B82EFD0D3BF1DE9F7DB0A697813A82553A64A247E2A`. Recovery requires the same Windows user's DPAPI keys.

The retained synthetic job settled AED 50.00 using AED 20.00 cash and AED 30.00 card. A separate rejected AED 1.00 report remained in the audit history. Duplicate requests and concurrent confirmations produced one invoice. Handovers of AED 7.50 and AED 12.50 reduced custody to zero. The finance overview and both reporting endpoints agreed on AED 12.00 owed during a temporary refund, deposit and adjustment test and returned to zero after rollback. [Staging verification results](staging-verification.json)

Physical-device keyboard, safe-area and system image-picker behaviour still need device verification.

