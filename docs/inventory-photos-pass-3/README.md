# Trifecta Pass 3 · Vehicle consumption and job photos

The implementation is in the workspace. Alembic revision `d38bf74a923c` was applied to the existing staging project `mgfzfgvlrxwyyftwukwf`. Application verification ran from a local preview connected to staging.

## Automatic inventory consumption

Trifecta already supported service-wide material rates, completion-triggered stock movements, manual adjustments, and immutable job consumption records. The migration adds vehicle categories to the existing rate table and a vehicle-category snapshot to new consumption records. Existing service-wide rates become fallbacks.

Managers and admins open **Inventory → Catalogue → Product → Automatic consumption**, choose a service or package, enter the amount per vehicle category, and save. Products use their stock unit. Volume and weight can also be entered in the compatible smaller or larger unit. A blank entry uses the existing service fallback when available. Without a fallback, a missing category for a configured product raises an inventory review and deducts nothing for that line. An explicit zero skips the product. A service with no configured products retains the existing no-template outcome.

Completion calculates each booked vehicle and service line independently. The existing ledger records the combined product movement, and job history retains the per-vehicle amounts. Job completion, stock changes, and audit records commit together. Repeated and concurrent completion requests return the completed job. Rate edits record the previous and new values in the audit log.

## Job photos

Trifecta already used Expo's system picker, booking-scoped photo records, and signed access to private Supabase Storage. Staff can now select multiple gallery photos, add camera shots to the same queue, preview and remove selections, and upload the queue. The app keeps confirmed images visible and retains failed previews for retry. The existing before-service, after-service, damage, and issue categories are available at the relevant job stages.

The queue accepts up to eight images at a time and the job allows up to 48. The app resizes large images to a 1,600-pixel long edge and compresses them as JPEG. Stable request IDs and immutable object paths let an interrupted upload resume without creating another record or object. The native camera picker still returns one shot per launch. [Expo ImagePicker documentation](https://docs.expo.dev/versions/latest/sdk/imagepicker/)

## Focused verification

- **Staging inventory.** A synthetic five-vehicle booking covered sedan, SUV, and van rates, two services, and the service fallback. Two simultaneous completion requests and further replays produced one completion event and one 635 ml stock movement. An injected failure rolled back completion and inventory together. Rate edits preserved history. Missing rates, explicit zero, invalid input, staff permissions, and manual stock-count audit were verified. [Staging results](staging-verification.json)
- **Staff browser.** English and Arabic RTL layouts fit at 320 and 390 pixels. Chrome selected three gallery files, removed one, skipped a duplicate, preserved one confirmed photo through a simulated failure, and recovered the second photo without uploading its bytes again. The API returned 404 when a photo from one booking was submitted for another. Staging handled Auth and the database. A local Storage fixture supplied signed URLs and injected the interruption. The hosted bucket's privacy, MIME allowlist, and 8 MB limit were checked separately. [Browser results](browser-verification.json)
- **Pass 1 and 2.** Staging payment history, employee attendance overview and history, staff access boundaries, and admin TOTP sign-in passed. The focused backend suite passed 105 tests and the staff app suite passed 194. Ruff, mypy, workspace TypeScript, and the Expo web export passed.

| Screen | English | Arabic |
| --- | --- | --- |
| Automatic consumption after save | [320 px](inventory-en-320.png) | [390 px](inventory-ar-390.png) |
| Photo queue and interrupted upload | [320 px queue](photos-en-320.png) | [390 px retry](photos-ar-390.png) |

## Remaining verification

Pass 4 can cover physical iOS and Android camera capture, backgrounding and reconnect, and the extended session checks. A live signed upload and read against hosted Storage also remains to be verified with a staging Storage service credential. Pass 3 used focused checks and stopped after the browser and database results above.
