# Privileged authenticator recovery — controlled operator procedure

**Staging verification:** the native technical sequence was executed using synthetic identities: 24 checks passed, including suspension, two distinct synthetic admin identities, native session/factor operations, no privileged AAL1 window and audit completion. See [final assessment](STAGING_FINAL.md) and [results](follow-up/staging-recovery.json). Human identity proof, independent human approvals and production operation remain NOT TESTED. The temporary operator used for the drill is retired and its credential revoked; it is not a product recovery endpoint.

This procedure is prepared for approval. It was **not executed on live accounts**. It intentionally provides no public recovery or factor-removal endpoint. A password reset, email link, help-desk message, supplied staff ID, or customer session is not sufficient authorization.

1. Open a restricted recovery case. Independently verify the employee's identity against existing company records and an established contact channel (in-person verification where possible). Do not accept a newly supplied telephone number or inbox as proof. Record an opaque case reference, not identity documents or TOTP secrets, in application audit metadata.
2. Require two distinct authorized administrators to approve the case. Record both immutable Auth user IDs and approval timestamps in the restricted case. A target cannot approve their own recovery. If only one application administrator exists, require the platform/account owner and a separately authorized company officer; do not silently reduce this to self-service email recovery.
3. With approved owner-level operations access, suspend the target's `staff_profiles.is_active` and record `mfa_recovery_started` in `audit_events` in one transaction. Record target staff ID, business ID, actor Auth ID, second approver Auth ID and case reference. The role must remain manager/admin; **never downgrade to employee to bypass MFA**. Use the SQL template below only after replacing and reviewing all placeholders.
4. Revoke every target session. A reviewed owner transaction can remove that user's rows from `auth.sessions`; this is prepared production configuration/account work requiring approval, not an operation performed by this audit. The existing private session check rejects old JWTs after this revocation. Do not copy refresh tokens or request a target's password/TOTP.
5. Through Supabase's native Auth Admin MFA tools, remove only the lost factor ID for the verified target. Use the Dashboard or `supabase.auth.admin.mfa.deleteFactor({ userId, id })` from a trusted operator environment; service-role credentials must never enter a browser, mobile app, ticket or transcript. Re-establish the first factor through the provider's approved recovery flow if compromise is suspected. Password reset alone must not complete the case.
6. After independently confirming first-factor control, supervise native TOTP enrollment/challenge/verification while keeping staff access suspended. Native Auth enrollment does not require privileged business API access. Verify that the target's new session references the target's verified replacement TOTP factor, then restore the staff active flag only after the controlled approvals and checks. The staging drill proved that even a verified AAL2 session remained denied while the staff account was suspended. Do not supply a fixed OTP or enroll a shared company authenticator.
7. Record `mfa_recovery_completed`, the new factor ID (not its secret), both approvers and the case reference. Notify the established account contact through the approved company channel. Review access logs for the affected interval and keep the case under the company's restricted retention policy. If any step fails, leave the account suspended and record the failure; do not grant temporary MFA exemptions.

Example **preparation template**, not an executed migration:

```sql
BEGIN;
-- The operator must independently verify the two approvals and identity proof.
-- All UUIDs and the opaque case reference must be reviewed before execution.
UPDATE public.staff_profiles
SET is_active = false
WHERE id = '<target-staff-uuid>'::uuid
  AND business_id = '<business-uuid>'::uuid
  AND role IN ('manager','admin');
-- Require exactly one updated target row before proceeding.
INSERT INTO public.audit_events
  (id,business_id,actor_auth_user_id,event_type,entity_type,entity_id,metadata)
VALUES
  (gen_random_uuid(),'<business-uuid>'::uuid,'<operator-auth-uuid>'::uuid,
   'mfa_recovery_started','staff_profile','<target-staff-uuid>'::uuid,
   jsonb_build_object('second_approver_auth_user_id','<different-approver-uuid>',
                     'case_reference','<approved-case-reference>'));
-- Session removal and native factor deletion require the approved target Auth ID.
COMMIT;
```

The template deliberately does not automate human identity proof or approve itself. Store the approvals in a restricted system, verify row counts and target IDs, and add completion/failure audit events. Operators with database-owner or service-role access are outside the public application trust boundary and require account MFA, least privilege and monitored access.

The technical suspension/session/factor/re-enrollment/audit sequence has staging evidence. Failed human identity proof, same-person approval rejection in the operating process, actual independent approval governance and production operator readiness still require a manual drill. This document does not claim those human controls were certified by automated tests.
