# Endpoint inventory

Generated from Python AST; boundary labels require service-level ownership checks. NOT TESTED means no endpoint-specific runtime claim.

| Method | Path | Authentication boundary | Source | Dynamic result |
|---|---|---|---|---|
| GET | `/api/v1/staff/calendar-bookings/catalogue` | STAFF | `backend/app/api/calendar_bookings.py:32` | PASS: anonymous denied; authorized/object cases NOT TESTED individually |
| GET | `/api/v1/staff/calendar-bookings/availability` | STAFF | `backend/app/api/calendar_bookings.py:43` | PASS: anonymous denied; authorized/object cases NOT TESTED individually |
| POST | `/api/v1/staff/calendar-bookings` | STAFF | `backend/app/api/calendar_bookings.py:61` | PASS: anonymous denied; authorized/object cases NOT TESTED individually |
| POST | `/api/v1/public/complaints` | PUBLIC | `backend/app/api/complaints.py:34` | NOT TESTED individually (see test inventory) |
| GET | `/api/v1/staff/complaints` | MANAGER/ADMIN | `backend/app/api/complaints.py:65` | PASS: anonymous denied; authorized/object cases NOT TESTED individually |
| GET | `/api/v1/staff/complaints/{reference}` | MANAGER/ADMIN | `backend/app/api/complaints.py:84` | PASS: anonymous denied; authorized/object cases NOT TESTED individually |
| POST | `/api/v1/staff/complaints/{reference}/evidence/{index}/download` | MANAGER/ADMIN | `backend/app/api/complaints.py:111` | PASS: anonymous denied; authorized/object cases NOT TESTED individually |
| GET | `/api/v1/customer/context` | CUSTOMER JWT | `backend/app/api/customer.py:87` | PASS: anonymous denied; authorized/object cases NOT TESTED individually |
| GET | `/api/v1/customer/profile` | CUSTOMER JWT | `backend/app/api/customer.py:92` | PASS: anonymous denied; authorized/object cases NOT TESTED individually |
| PATCH | `/api/v1/customer/profile` | CUSTOMER JWT | `backend/app/api/customer.py:97` | PASS: anonymous denied; authorized/object cases NOT TESTED individually |
| GET | `/api/v1/customer/addresses` | CUSTOMER JWT | `backend/app/api/customer.py:108` | PASS: anonymous denied; authorized/object cases NOT TESTED individually |
| POST | `/api/v1/customer/addresses` | CUSTOMER JWT | `backend/app/api/customer.py:113` | PASS: anonymous denied; authorized/object cases NOT TESTED individually |
| PATCH | `/api/v1/customer/addresses/{address_id}` | CUSTOMER JWT | `backend/app/api/customer.py:124` | PASS: anonymous denied; authorized/object cases NOT TESTED individually |
| DELETE | `/api/v1/customer/addresses/{address_id}` | CUSTOMER JWT | `backend/app/api/customer.py:138` | PASS: anonymous denied; authorized/object cases NOT TESTED individually |
| GET | `/api/v1/customer/vehicles` | CUSTOMER JWT | `backend/app/api/customer.py:149` | PASS: anonymous denied; authorized/object cases NOT TESTED individually |
| POST | `/api/v1/customer/vehicles` | CUSTOMER JWT | `backend/app/api/customer.py:154` | PASS: anonymous denied; authorized/object cases NOT TESTED individually |
| PATCH | `/api/v1/customer/vehicles/{vehicle_id}` | CUSTOMER JWT | `backend/app/api/customer.py:165` | PASS: anonymous denied; authorized/object cases NOT TESTED individually |
| DELETE | `/api/v1/customer/vehicles/{vehicle_id}` | CUSTOMER JWT | `backend/app/api/customer.py:179` | PASS: anonymous denied; authorized/object cases NOT TESTED individually |
| GET | `/api/v1/customer/reviews/eligibility` | CUSTOMER JWT | `backend/app/api/customer.py:190` | PASS: anonymous denied; authorized/object cases NOT TESTED individually |
| GET | `/api/v1/customer/bookings/{booking_id}/review` | CUSTOMER JWT | `backend/app/api/customer.py:197` | PASS: anonymous denied; authorized/object cases NOT TESTED individually |
| POST | `/api/v1/customer/reviews` | CUSTOMER JWT | `backend/app/api/customer.py:216` | PASS: anonymous denied; authorized/object cases NOT TESTED individually |
| POST | `/api/v1/customer/review-prompt/open` | CUSTOMER JWT | `backend/app/api/customer.py:230` | PASS: anonymous denied; authorized/object cases NOT TESTED individually |
| DELETE | `/api/v1/customer/account` | CUSTOMER JWT | `backend/app/api/customer.py:238` | PASS: anonymous denied; authorized/object cases NOT TESTED individually |
| GET | `/api/v1/customer/bookings` | CUSTOMER JWT | `backend/app/api/customer.py:252` | PASS: anonymous denied; authorized/object cases NOT TESTED individually |
| GET | `/api/v1/customer/bookings/{booking_id}` | CUSTOMER JWT | `backend/app/api/customer.py:257` | PASS: anonymous denied; authorized/object cases NOT TESTED individually |
| GET | `/api/v1/customer/bookings/{booking_id}/invoices/{invoice_id}` | CUSTOMER JWT | `backend/app/api/customer.py:267` | PASS: anonymous denied; authorized/object cases NOT TESTED individually |
| POST | `/api/v1/customer/bookings/{booking_id}/cancellation-requests` | CUSTOMER JWT | `backend/app/api/customer.py:282` | PASS: anonymous denied; authorized/object cases NOT TESTED individually |
| POST | `/api/v1/customer/bookings/{booking_id}/reschedule` | CUSTOMER JWT | `backend/app/api/customer.py:326` | PASS: anonymous denied; authorized/object cases NOT TESTED individually |
| POST | `/api/v1/internal/notifications/dispatch` | DISPATCH SECRET | `backend/app/api/internal.py:17` | NOT TESTED individually (see test inventory) |
| GET | `/api/v1/public/catalogue` | PUBLIC | `backend/app/api/public.py:65` | NOT TESTED individually (see test inventory) |
| POST | `/api/v1/public/coupons/validate` | PUBLIC | `backend/app/api/public.py:70` | NOT TESTED individually (see test inventory) |
| GET | `/api/v1/public/reviews/summary` | PUBLIC | `backend/app/api/public.py:77` | NOT TESTED individually (see test inventory) |
| GET | `/api/v1/public/reviews` | PUBLIC | `backend/app/api/public.py:82` | NOT TESTED individually (see test inventory) |
| GET | `/api/v1/public/reviews/guest/eligibility` | PUBLIC + BOOKING CAPABILITY | `backend/app/api/public.py:91` | NOT TESTED individually (see test inventory) |
| POST | `/api/v1/public/reviews/guest/verify` | PUBLIC | `backend/app/api/public.py:105` | NOT TESTED individually (see test inventory) |
| POST | `/api/v1/public/reviews/guest/submit` | PUBLIC + BOOKING CAPABILITY | `backend/app/api/public.py:130` | NOT TESTED individually (see test inventory) |
| GET | `/api/v1/public/availability` | PUBLIC | `backend/app/api/public.py:186` | NOT TESTED individually (see test inventory) |
| POST | `/api/v1/public/holds` | PUBLIC | `backend/app/api/public.py:203` | NOT TESTED individually (see test inventory) |
| POST | `/api/v1/public/bookings` | OPTIONAL JWT | `backend/app/api/public.py:209` | NOT TESTED individually (see test inventory) |
| GET | `/api/v1/public/bookings/manage` | PUBLIC + BOOKING CAPABILITY | `backend/app/api/public.py:266` | NOT TESTED individually (see test inventory) |
| GET | `/api/v1/public/bookings/manage/invoices/{invoice_id}` | PUBLIC + BOOKING CAPABILITY | `backend/app/api/public.py:280` | NOT TESTED individually (see test inventory) |
| POST | `/api/v1/public/bookings/manage/cancellation-requests` | PUBLIC + BOOKING CAPABILITY | `backend/app/api/public.py:296` | NOT TESTED individually (see test inventory) |
| GET | `/api/v1/staff/coupons` | MANAGER/ADMIN | `backend/app/api/staff.py:294` | PASS: anonymous denied; authorized/object cases NOT TESTED individually |
| POST | `/api/v1/staff/coupons` | MANAGER/ADMIN | `backend/app/api/staff.py:299` | PASS: anonymous denied; authorized/object cases NOT TESTED individually |
| PATCH | `/api/v1/staff/coupons/{coupon_id}` | MANAGER/ADMIN | `backend/app/api/staff.py:307` | PASS: anonymous denied; authorized/object cases NOT TESTED individually |
| PATCH | `/api/v1/staff/reviews/{review_id}` | MANAGER/ADMIN | `backend/app/api/staff.py:318` | PASS: anonymous denied; authorized/object cases NOT TESTED individually |
| GET | `/api/v1/staff/catalogue` | STAFF | `backend/app/api/staff.py:333` | PASS: anonymous denied; authorized/object cases NOT TESTED individually |
| POST | `/api/v1/staff/catalogue/services` | MANAGER/ADMIN | `backend/app/api/staff.py:338` | PASS: anonymous denied; authorized/object cases NOT TESTED individually |
| PATCH | `/api/v1/staff/catalogue/services/{service_id}` | MANAGER/ADMIN | `backend/app/api/staff.py:348` | PASS: anonymous denied; authorized/object cases NOT TESTED individually |
| POST | `/api/v1/staff/catalogue/services/{service_id}/addons` | MANAGER/ADMIN | `backend/app/api/staff.py:361` | PASS: anonymous denied; authorized/object cases NOT TESTED individually |
| PATCH | `/api/v1/staff/catalogue/addons/{addon_id}` | MANAGER/ADMIN | `backend/app/api/staff.py:374` | PASS: anonymous denied; authorized/object cases NOT TESTED individually |
| GET | `/api/v1/staff/business-settings` | STAFF | `backend/app/api/staff.py:387` | PASS: anonymous denied; authorized/object cases NOT TESTED individually |
| PATCH | `/api/v1/staff/business-settings` | MANAGER/ADMIN | `backend/app/api/staff.py:394` | PASS: anonymous denied; authorized/object cases NOT TESTED individually |
| GET | `/api/v1/staff/context` | STAFF | `backend/app/api/staff.py:426` | PASS: anonymous denied; authorized/object cases NOT TESTED individually |
| GET | `/api/v1/staff/sync-state` | STAFF | `backend/app/api/staff.py:443` | PASS: anonymous denied; authorized/object cases NOT TESTED individually |
| GET | `/api/v1/staff/profile` | STAFF | `backend/app/api/staff.py:457` | PASS: anonymous denied; authorized/object cases NOT TESTED individually |
| PATCH | `/api/v1/staff/profile` | STAFF | `backend/app/api/staff.py:462` | PASS: anonymous denied; authorized/object cases NOT TESTED individually |
| GET | `/api/v1/staff/users` | MANAGER/ADMIN | `backend/app/api/staff.py:477` | PASS: anonymous denied; authorized/object cases NOT TESTED individually |
| POST | `/api/v1/staff/users` | MANAGER/ADMIN | `backend/app/api/staff.py:482` | PASS: anonymous denied; authorized/object cases NOT TESTED individually |
| PATCH | `/api/v1/staff/users/{staff_id}` | MANAGER/ADMIN | `backend/app/api/staff.py:492` | PASS: anonymous denied; authorized/object cases NOT TESTED individually |
| POST | `/api/v1/staff/users/{staff_id}/temporary-password` | MANAGER/ADMIN | `backend/app/api/staff.py:505` | PASS: anonymous denied; authorized/object cases NOT TESTED individually |
| POST | `/api/v1/staff/users/{staff_id}/password` | MANAGER/ADMIN | `backend/app/api/staff.py:518` | PASS: anonymous denied; authorized/object cases NOT TESTED individually |
| GET | `/api/v1/staff/teams` | STAFF | `backend/app/api/staff.py:536` | PASS: anonymous denied; authorized/object cases NOT TESTED individually |
| POST | `/api/v1/staff/teams` | MANAGER/ADMIN | `backend/app/api/staff.py:541` | PASS: anonymous denied; authorized/object cases NOT TESTED individually |
| GET | `/api/v1/staff/teams/{team_id}` | STAFF | `backend/app/api/staff.py:551` | PASS: anonymous denied; authorized/object cases NOT TESTED individually |
| PATCH | `/api/v1/staff/teams/{team_id}` | MANAGER/ADMIN | `backend/app/api/staff.py:556` | PASS: anonymous denied; authorized/object cases NOT TESTED individually |
| PUT | `/api/v1/staff/teams/{team_id}/members` | MANAGER/ADMIN | `backend/app/api/staff.py:569` | PASS: anonymous denied; authorized/object cases NOT TESTED individually |
| GET | `/api/v1/staff/attendance` | STAFF | `backend/app/api/staff.py:582` | PASS: anonymous denied; authorized/object cases NOT TESTED individually |
| GET | `/api/v1/staff/attendance/overview` | STAFF | `backend/app/api/staff.py:603` | PASS: anonymous denied; authorized/object cases NOT TESTED individually |
| POST | `/api/v1/staff/attendance/clock-in` | STAFF | `backend/app/api/staff.py:613` | PASS: anonymous denied; authorized/object cases NOT TESTED individually |
| POST | `/api/v1/staff/attendance/clock-out` | STAFF | `backend/app/api/staff.py:623` | PASS: anonymous denied; authorized/object cases NOT TESTED individually |
| GET | `/api/v1/staff/shifts` | STAFF | `backend/app/api/staff.py:633` | PASS: anonymous denied; authorized/object cases NOT TESTED individually |
| POST | `/api/v1/staff/shifts` | MANAGER/ADMIN | `backend/app/api/staff.py:638` | PASS: anonymous denied; authorized/object cases NOT TESTED individually |
| GET | `/api/v1/staff/shift-assignments` | STAFF | `backend/app/api/staff.py:648` | PASS: anonymous denied; authorized/object cases NOT TESTED individually |
| PUT | `/api/v1/staff/shift-assignments` | MANAGER/ADMIN | `backend/app/api/staff.py:658` | PASS: anonymous denied; authorized/object cases NOT TESTED individually |
| GET | `/api/v1/staff/leave` | STAFF | `backend/app/api/staff.py:670` | PASS: anonymous denied; authorized/object cases NOT TESTED individually |
| POST | `/api/v1/staff/leave` | STAFF | `backend/app/api/staff.py:677` | PASS: anonymous denied; authorized/object cases NOT TESTED individually |
| POST | `/api/v1/staff/leave/{leave_id}/review` | MANAGER/ADMIN | `backend/app/api/staff.py:685` | PASS: anonymous denied; authorized/object cases NOT TESTED individually |
| GET | `/api/v1/staff/dashboard` | MANAGER/ADMIN | `backend/app/api/staff.py:698` | PASS: anonymous denied; authorized/object cases NOT TESTED individually |
| GET | `/api/v1/staff/reports/v2` | MANAGER/ADMIN | `backend/app/api/staff.py:708` | PASS: anonymous denied; authorized/object cases NOT TESTED individually |
| GET | `/api/v1/staff/finance/overview` | MANAGER/ADMIN | `backend/app/api/staff.py:718` | PASS: anonymous denied; authorized/object cases NOT TESTED individually |
| GET | `/api/v1/staff/finance/expenses` | MANAGER/ADMIN | `backend/app/api/staff.py:728` | PASS: anonymous denied; authorized/object cases NOT TESTED individually |
| POST | `/api/v1/staff/finance/expenses` | MANAGER/ADMIN | `backend/app/api/staff.py:759` | PASS: anonymous denied; authorized/object cases NOT TESTED individually |
| GET | `/api/v1/staff/finance/expenses/{expense_id}` | MANAGER/ADMIN | `backend/app/api/staff.py:774` | PASS: anonymous denied; authorized/object cases NOT TESTED individually |
| GET | `/api/v1/staff/finance/expenses/{expense_id}/voucher` | MANAGER/ADMIN | `backend/app/api/staff.py:786` | PASS: anonymous denied; authorized/object cases NOT TESTED individually |
| POST | `/api/v1/staff/finance/expenses/{expense_id}/evidence/upload` | MANAGER/ADMIN | `backend/app/api/staff.py:799` | PASS: anonymous denied; authorized/object cases NOT TESTED individually |
| POST | `/api/v1/staff/finance/expenses/{expense_id}/evidence/{evidence_id}/complete` | MANAGER/ADMIN | `backend/app/api/staff.py:825` | PASS: anonymous denied; authorized/object cases NOT TESTED individually |
| POST | `/api/v1/staff/finance/expenses/{expense_id}/void` | MANAGER/ADMIN | `backend/app/api/staff.py:855` | PASS: anonymous denied; authorized/object cases NOT TESTED individually |
| GET | `/api/v1/staff/finance/cash/pending` | MANAGER/ADMIN | `backend/app/api/staff.py:871` | PASS: anonymous denied; authorized/object cases NOT TESTED individually |
| GET | `/api/v1/staff/finance/cash/pending/{staff_id}` | MANAGER/ADMIN | `backend/app/api/staff.py:880` | PASS: anonymous denied; authorized/object cases NOT TESTED individually |
| GET | `/api/v1/staff/finance/cash/reconciliations` | MANAGER/ADMIN | `backend/app/api/staff.py:889` | PASS: anonymous denied; authorized/object cases NOT TESTED individually |
| POST | `/api/v1/staff/finance/cash/reconciliations` | MANAGER/ADMIN | `backend/app/api/staff.py:903` | PASS: anonymous denied; authorized/object cases NOT TESTED individually |
| GET | `/api/v1/staff/finance/cash/reconciliations/{reconciliation_id}` | MANAGER/ADMIN | `backend/app/api/staff.py:918` | PASS: anonymous denied; authorized/object cases NOT TESTED individually |
| POST | `/api/v1/staff/finance/cash/reconciliations/{reconciliation_id}/void` | MANAGER/ADMIN | `backend/app/api/staff.py:930` | PASS: anonymous denied; authorized/object cases NOT TESTED individually |
| GET | `/api/v1/staff/finance/cash/mine` | STAFF | `backend/app/api/staff.py:943` | PASS: anonymous denied; authorized/object cases NOT TESTED individually |
| GET | `/api/v1/staff/inventory/overview` | MANAGER/ADMIN | `backend/app/api/staff.py:953` | PASS: anonymous denied; authorized/object cases NOT TESTED individually |
| GET | `/api/v1/staff/inventory/consumption/attention` | MANAGER/ADMIN | `backend/app/api/staff.py:960` | PASS: anonymous denied; authorized/object cases NOT TESTED individually |
| POST | `/api/v1/staff/inventory/consumption/{run_id}/review` | MANAGER/ADMIN | `backend/app/api/staff.py:973` | PASS: anonymous denied; authorized/object cases NOT TESTED individually |
| GET | `/api/v1/staff/inventory/items` | STAFF | `backend/app/api/staff.py:986` | PASS: anonymous denied; authorized/object cases NOT TESTED individually |
| POST | `/api/v1/staff/inventory/items` | MANAGER/ADMIN | `backend/app/api/staff.py:1008` | PASS: anonymous denied; authorized/object cases NOT TESTED individually |
| GET | `/api/v1/staff/inventory/items/{item_id}` | STAFF | `backend/app/api/staff.py:1018` | PASS: anonymous denied; authorized/object cases NOT TESTED individually |
| PATCH | `/api/v1/staff/inventory/items/{item_id}` | MANAGER/ADMIN | `backend/app/api/staff.py:1025` | PASS: anonymous denied; authorized/object cases NOT TESTED individually |
| GET | `/api/v1/staff/inventory/locations` | STAFF | `backend/app/api/staff.py:1038` | PASS: anonymous denied; authorized/object cases NOT TESTED individually |
| POST | `/api/v1/staff/inventory/locations` | MANAGER/ADMIN | `backend/app/api/staff.py:1045` | PASS: anonymous denied; authorized/object cases NOT TESTED individually |
| PATCH | `/api/v1/staff/inventory/locations/{location_id}` | MANAGER/ADMIN | `backend/app/api/staff.py:1055` | PASS: anonymous denied; authorized/object cases NOT TESTED individually |
| GET | `/api/v1/staff/inventory/stock` | STAFF | `backend/app/api/staff.py:1068` | PASS: anonymous denied; authorized/object cases NOT TESTED individually |
| PATCH | `/api/v1/staff/inventory/locations/{location_id}/items/{item_id}/threshold` | MANAGER/ADMIN | `backend/app/api/staff.py:1094` | PASS: anonymous denied; authorized/object cases NOT TESTED individually |
| POST | `/api/v1/staff/inventory/receipts` | MANAGER/ADMIN | `backend/app/api/staff.py:1108` | PASS: anonymous denied; authorized/object cases NOT TESTED individually |
| POST | `/api/v1/staff/inventory/transfers` | MANAGER/ADMIN | `backend/app/api/staff.py:1121` | PASS: anonymous denied; authorized/object cases NOT TESTED individually |
| POST | `/api/v1/staff/inventory/usage` | STAFF | `backend/app/api/staff.py:1132` | PASS: anonymous denied; authorized/object cases NOT TESTED individually |
| POST | `/api/v1/staff/inventory/wastage` | MANAGER/ADMIN | `backend/app/api/staff.py:1143` | PASS: anonymous denied; authorized/object cases NOT TESTED individually |
| POST | `/api/v1/staff/inventory/stock-counts` | MANAGER/ADMIN | `backend/app/api/staff.py:1154` | PASS: anonymous denied; authorized/object cases NOT TESTED individually |
| GET | `/api/v1/staff/inventory/movements` | STAFF | `backend/app/api/staff.py:1165` | PASS: anonymous denied; authorized/object cases NOT TESTED individually |
| GET | `/api/v1/staff/inventory/reports/usage` | MANAGER/ADMIN | `backend/app/api/staff.py:1196` | PASS: anonymous denied; authorized/object cases NOT TESTED individually |
| GET | `/api/v1/staff/inventory/teams/{team_id}/summary` | STAFF | `backend/app/api/staff.py:1206` | PASS: anonymous denied; authorized/object cases NOT TESTED individually |
| GET | `/api/v1/staff/inventory/services/{service_id}/template` | STAFF | `backend/app/api/staff.py:1216` | PASS: anonymous denied; authorized/object cases NOT TESTED individually |
| PUT | `/api/v1/staff/inventory/services/{service_id}/template` | MANAGER/ADMIN | `backend/app/api/staff.py:1226` | PASS: anonymous denied; authorized/object cases NOT TESTED individually |
| GET | `/api/v1/staff/management-check` | MANAGER/ADMIN | `backend/app/api/staff.py:1239` | PASS: anonymous denied; authorized/object cases NOT TESTED individually |
| GET | `/api/v1/staff/jobs` | STAFF | `backend/app/api/staff.py:1244` | PASS: anonymous denied; authorized/object cases NOT TESTED individually |
| GET | `/api/v1/staff/jobs/calendar` | STAFF | `backend/app/api/staff.py:1285` | PASS: anonymous denied; authorized/object cases NOT TESTED individually |
| GET | `/api/v1/staff/jobs/{job_id}` | STAFF | `backend/app/api/staff.py:1295` | PASS: anonymous denied; authorized/object cases NOT TESTED individually |
| GET | `/api/v1/staff/jobs/{job_id}/communications` | MANAGER/ADMIN | `backend/app/api/staff.py:1302` | PASS: anonymous denied; authorized/object cases NOT TESTED individually |
| POST | `/api/v1/staff/jobs/{job_id}/notifications/delay` | MANAGER/ADMIN | `backend/app/api/staff.py:1313` | PASS: anonymous denied; authorized/object cases NOT TESTED individually |
| GET | `/api/v1/staff/jobs/{job_id}/quality` | STAFF | `backend/app/api/staff.py:1324` | PASS: anonymous denied; authorized/object cases NOT TESTED individually |
| PUT | `/api/v1/staff/jobs/{job_id}/quality/inspection` | STAFF | `backend/app/api/staff.py:1371` | PASS: anonymous denied; authorized/object cases NOT TESTED individually |
| PUT | `/api/v1/staff/jobs/{job_id}/quality/checklist` | STAFF | `backend/app/api/staff.py:1383` | PASS: anonymous denied; authorized/object cases NOT TESTED individually |
| POST | `/api/v1/staff/jobs/{job_id}/quality/issues` | STAFF | `backend/app/api/staff.py:1395` | PASS: anonymous denied; authorized/object cases NOT TESTED individually |
| POST | `/api/v1/staff/jobs/{job_id}/quality/photos/upload` | STAFF | `backend/app/api/staff.py:1411` | PASS: anonymous denied; authorized/object cases NOT TESTED individually |
| POST | `/api/v1/staff/jobs/{job_id}/quality/photos/{photo_id}/complete` | STAFF | `backend/app/api/staff.py:1440` | PASS: anonymous denied; authorized/object cases NOT TESTED individually |
| POST | `/api/v1/staff/jobs/{job_id}/quality/complaints` | MANAGER/ADMIN | `backend/app/api/staff.py:1469` | PASS: anonymous denied; authorized/object cases NOT TESTED individually |
| POST | `/api/v1/staff/jobs/{job_id}/quality/complaints/{complaint_id}/review` | MANAGER/ADMIN | `backend/app/api/staff.py:1481` | PASS: anonymous denied; authorized/object cases NOT TESTED individually |
| POST | `/api/v1/staff/jobs/{job_id}/start-trip` | STAFF | `backend/app/api/staff.py:1499` | PASS: anonymous denied; authorized/object cases NOT TESTED individually |
| POST | `/api/v1/staff/jobs/{job_id}/start` | STAFF | `backend/app/api/staff.py:1537` | PASS: anonymous denied; authorized/object cases NOT TESTED individually |
| POST | `/api/v1/staff/jobs/{job_id}/arrive` | STAFF | `backend/app/api/staff.py:1550` | PASS: anonymous denied; authorized/object cases NOT TESTED individually |
| POST | `/api/v1/staff/jobs/{job_id}/complete` | STAFF | `backend/app/api/staff.py:1563` | PASS: anonymous denied; authorized/object cases NOT TESTED individually |
| POST | `/api/v1/staff/jobs/{job_id}/cash-payment` | STAFF | `backend/app/api/staff.py:1585` | PASS: anonymous denied; authorized/object cases NOT TESTED individually |
| PATCH | `/api/v1/staff/jobs/{job_id}/assignment` | MANAGER/ADMIN | `backend/app/api/staff.py:1598` | PASS: anonymous denied; authorized/object cases NOT TESTED individually |
| GET | `/api/v1/staff/jobs/{job_id}/assignment-options` | MANAGER/ADMIN | `backend/app/api/staff.py:1608` | PASS: anonymous denied; authorized/object cases NOT TESTED individually |
| GET | `/api/v1/staff/team` | MANAGER/ADMIN | `backend/app/api/staff.py:1615` | PASS: anonymous denied; authorized/object cases NOT TESTED individually |
| GET | `/api/v1/staff/reports/summary` | MANAGER/ADMIN | `backend/app/api/staff.py:1620` | PASS: anonymous denied; authorized/object cases NOT TESTED individually |
| GET | `/api/v1/staff/cancellations` | MANAGER/ADMIN | `backend/app/api/staff.py:1627` | PASS: anonymous denied; authorized/object cases NOT TESTED individually |
| POST | `/api/v1/staff/cancellations/{cancellation_id}/review` | MANAGER/ADMIN | `backend/app/api/staff.py:1632` | PASS: anonymous denied; authorized/object cases NOT TESTED individually |
| GET | `/api/v1/staff/customers` | MANAGER/ADMIN | `backend/app/api/staff.py:1645` | PASS: anonymous denied; authorized/object cases NOT TESTED individually |
| GET | `/api/v1/staff/customers/{customer_id}` | MANAGER/ADMIN | `backend/app/api/staff.py:1656` | PASS: anonymous denied; authorized/object cases NOT TESTED individually |
| PATCH | `/api/v1/staff/customers/{customer_id}` | MANAGER/ADMIN | `backend/app/api/staff.py:1673` | PASS: anonymous denied; authorized/object cases NOT TESTED individually |
| POST | `/api/v1/staff/customers/{customer_id}/addresses` | MANAGER/ADMIN | `backend/app/api/staff.py:1690` | PASS: anonymous denied; authorized/object cases NOT TESTED individually |
| PATCH | `/api/v1/staff/customers/{customer_id}/addresses/{address_id}` | MANAGER/ADMIN | `backend/app/api/staff.py:1706` | PASS: anonymous denied; authorized/object cases NOT TESTED individually |
| DELETE | `/api/v1/staff/customers/{customer_id}/addresses/{address_id}` | MANAGER/ADMIN | `backend/app/api/staff.py:1720` | PASS: anonymous denied; authorized/object cases NOT TESTED individually |
| POST | `/api/v1/staff/customers/{customer_id}/vehicles` | MANAGER/ADMIN | `backend/app/api/staff.py:1737` | PASS: anonymous denied; authorized/object cases NOT TESTED individually |
| PATCH | `/api/v1/staff/customers/{customer_id}/vehicles/{vehicle_id}` | MANAGER/ADMIN | `backend/app/api/staff.py:1753` | PASS: anonymous denied; authorized/object cases NOT TESTED individually |
| DELETE | `/api/v1/staff/customers/{customer_id}/vehicles/{vehicle_id}` | MANAGER/ADMIN | `backend/app/api/staff.py:1767` | PASS: anonymous denied; authorized/object cases NOT TESTED individually |
| POST | `/api/v1/staff/customers/{customer_id}/loyalty/adjustments` | MANAGER/ADMIN | `backend/app/api/staff.py:1780` | PASS: anonymous denied; authorized/object cases NOT TESTED individually |
| GET | `/api/v1/staff/loyalty/settings` | MANAGER/ADMIN | `backend/app/api/staff.py:1799` | PASS: anonymous denied; authorized/object cases NOT TESTED individually |
| PATCH | `/api/v1/staff/loyalty/settings` | MANAGER/ADMIN | `backend/app/api/staff.py:1804` | PASS: anonymous denied; authorized/object cases NOT TESTED individually |
| GET | `/api/v1/staff/bookings/{booking_id}/reschedule-options` | MANAGER/ADMIN | `backend/app/api/staff.py:1814` | PASS: anonymous denied; authorized/object cases NOT TESTED individually |
| POST | `/api/v1/staff/bookings/{booking_id}/reschedule` | MANAGER/ADMIN | `backend/app/api/staff.py:1827` | PASS: anonymous denied; authorized/object cases NOT TESTED individually |
| GET | `/api/v1/staff/customer-policies` | MANAGER/ADMIN | `backend/app/api/staff.py:1918` | PASS: anonymous denied; authorized/object cases NOT TESTED individually |
| POST | `/api/v1/staff/bookings/{booking_id}/policy-provision` | MANAGER/ADMIN | `backend/app/api/staff.py:1923` | PASS: anonymous denied; authorized/object cases NOT TESTED individually |
| PATCH | `/api/v1/staff/bookings/{booking_id}/archive` | MANAGER/ADMIN | `backend/app/api/staff.py:1952` | PASS: anonymous denied; authorized/object cases NOT TESTED individually |
| GET | `/health` | PUBLIC | `backend/app/api/system.py:11` | NOT TESTED individually (see test inventory) |
| GET | `/ready` | PUBLIC | `backend/app/api/system.py:16` | NOT TESTED individually (see test inventory) |
