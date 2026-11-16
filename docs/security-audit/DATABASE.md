# Database and RLS audit

**Historical initial inventory.** Current isolated staging results and all 64 table permission rows are in [STAGING_DATABASE.md](STAGING_DATABASE.md); [STAGING_FINAL.md](STAGING_FINAL.md) records current runtime/TLS limitations and production blockers. The earlier live revision below is not a current staging claim.

Live metadata was read on 2026-11-11; no production application rows were read or modified. Live revision: `dbd74a2d3de9`. Local role tests apply the entire migration chain through `c7e833583da3`. **The local hardening results are not deployed results.**

The client access model is intentional deny-all: browser/native clients use FastAPI. SELECT, INSERT, UPDATE and DELETE have no allowed direct-client path. Backend connections can read all tenants; API ownership/team checks remain the tenant boundary. The new runtime group has no ownership, DDL, TRUNCATE or BYPASSRLS. Its explicit all-row policy grants only the backend the intended access; it does not claim per-tenant RLS.

| Table | Live RLS | Live owner | Live policies | Live client privileges | Local S/I/U/D denial tests | Local backend policy |
|---|---|---|---|---|---|---|
| alembic_version | True | postgres | 0 | broad grants | PASS / PASS / PASS / PASS | no client policy; deny all |
| api_rate_windows | absent | not deployed | 0 | revoked/absent | PASS / PASS / PASS / PASS | backend_only: USING true / WITH CHECK true |
| attendance_sessions | True | postgres | 0 | broad grants | PASS / PASS / PASS / PASS | backend_only: USING true / WITH CHECK true |
| audit_events | True | postgres | 0 | broad grants | PASS / PASS / PASS / PASS | backend_only: USING true / WITH CHECK true |
| booking_service_addons | True | postgres | 0 | revoked/absent | PASS / PASS / PASS / PASS | backend_only: USING true / WITH CHECK true |
| booking_services | True | postgres | 0 | broad grants | PASS / PASS / PASS / PASS | backend_only: USING true / WITH CHECK true |
| booking_vehicles | True | postgres | 0 | broad grants | PASS / PASS / PASS / PASS | backend_only: USING true / WITH CHECK true |
| bookings | True | postgres | 0 | broad grants | PASS / PASS / PASS / PASS | backend_only: USING true / WITH CHECK true |
| business_operating_hours | True | postgres | 0 | revoked/absent | PASS / PASS / PASS / PASS | backend_only: USING true / WITH CHECK true |
| business_settings | True | postgres | 0 | broad grants | PASS / PASS / PASS / PASS | backend_only: USING true / WITH CHECK true |
| business_sync_revisions | True | postgres | 0 | broad grants | PASS / PASS / PASS / PASS | backend_only: USING true / WITH CHECK true |
| businesses | True | postgres | 0 | broad grants | PASS / PASS / PASS / PASS | backend_only: USING true / WITH CHECK true |
| cancellation_requests | True | postgres | 0 | broad grants | PASS / PASS / PASS / PASS | backend_only: USING true / WITH CHECK true |
| cash_reconciliation_payments | True | postgres | 0 | broad grants | PASS / PASS / PASS / PASS | backend_only: USING true / WITH CHECK true |
| cash_reconciliations | True | postgres | 0 | broad grants | PASS / PASS / PASS / PASS | backend_only: USING true / WITH CHECK true |
| complaint_rate_windows | absent | not deployed | 0 | revoked/absent | PASS / PASS / PASS / PASS | backend_only: USING true / WITH CHECK true |
| coupon_service_eligibility | True | postgres | 0 | revoked/absent | PASS / PASS / PASS / PASS | backend_only: USING true / WITH CHECK true |
| coupon_vehicle_eligibility | True | postgres | 0 | revoked/absent | PASS / PASS / PASS / PASS | backend_only: USING true / WITH CHECK true |
| coupons | True | postgres | 0 | revoked/absent | PASS / PASS / PASS / PASS | backend_only: USING true / WITH CHECK true |
| customer_addresses | True | postgres | 0 | broad grants | PASS / PASS / PASS / PASS | backend_only: USING true / WITH CHECK true |
| customer_complaints | absent | not deployed | 0 | revoked/absent | PASS / PASS / PASS / PASS | backend_only: USING true / WITH CHECK true |
| customer_payment_methods | True | postgres | 0 | broad grants | PASS / PASS / PASS / PASS | backend_only: USING true / WITH CHECK true |
| customer_profiles | True | postgres | 0 | broad grants | PASS / PASS / PASS / PASS | backend_only: USING true / WITH CHECK true |
| customer_review_prompt_states | True | postgres | 0 | broad grants | PASS / PASS / PASS / PASS | backend_only: USING true / WITH CHECK true |
| customer_reviews | True | postgres | 0 | broad grants | PASS / PASS / PASS / PASS | backend_only: USING true / WITH CHECK true |
| deleted_customer_identities | True | postgres | 0 | broad grants | PASS / PASS / PASS / PASS | backend_only: USING true / WITH CHECK true |
| expense_evidence | True | postgres | 0 | broad grants | PASS / PASS / PASS / PASS | backend_only: USING true / WITH CHECK true |
| expenses | True | postgres | 0 | broad grants | PASS / PASS / PASS / PASS | backend_only: USING true / WITH CHECK true |
| guest_review_verification_attempts | True | postgres | 0 | broad grants | PASS / PASS / PASS / PASS | backend_only: USING true / WITH CHECK true |
| idempotency_records | True | postgres | 0 | broad grants | PASS / PASS / PASS / PASS | backend_only: USING true / WITH CHECK true |
| inventory_items | True | postgres | 0 | revoked/absent | PASS / PASS / PASS / PASS | backend_only: USING true / WITH CHECK true |
| inventory_locations | True | postgres | 0 | revoked/absent | PASS / PASS / PASS / PASS | backend_only: USING true / WITH CHECK true |
| inventory_movements | True | postgres | 0 | revoked/absent | PASS / PASS / PASS / PASS | backend_only: USING true / WITH CHECK true |
| inventory_operations | True | postgres | 0 | revoked/absent | PASS / PASS / PASS / PASS | backend_only: USING true / WITH CHECK true |
| inventory_stock | True | postgres | 0 | revoked/absent | PASS / PASS / PASS / PASS | backend_only: USING true / WITH CHECK true |
| invoice_sequences | True | postgres | 0 | broad grants | PASS / PASS / PASS / PASS | backend_only: USING true / WITH CHECK true |
| job_checklist_items | True | postgres | 0 | broad grants | PASS / PASS / PASS / PASS | backend_only: USING true / WITH CHECK true |
| job_complaints | True | postgres | 0 | broad grants | PASS / PASS / PASS / PASS | backend_only: USING true / WITH CHECK true |
| job_events | True | postgres | 0 | broad grants | PASS / PASS / PASS / PASS | backend_only: USING true / WITH CHECK true |
| job_inspections | True | postgres | 0 | broad grants | PASS / PASS / PASS / PASS | backend_only: USING true / WITH CHECK true |
| job_inventory_consumption_lines | True | postgres | 0 | revoked/absent | PASS / PASS / PASS / PASS | backend_only: USING true / WITH CHECK true |
| job_inventory_consumption_runs | True | postgres | 0 | revoked/absent | PASS / PASS / PASS / PASS | backend_only: USING true / WITH CHECK true |
| job_photos | True | postgres | 0 | broad grants | PASS / PASS / PASS / PASS | backend_only: USING true / WITH CHECK true |
| job_quality_issues | True | postgres | 0 | broad grants | PASS / PASS / PASS / PASS | backend_only: USING true / WITH CHECK true |
| jobs | True | postgres | 0 | broad grants | PASS / PASS / PASS / PASS | backend_only: USING true / WITH CHECK true |
| leave_requests | True | postgres | 0 | broad grants | PASS / PASS / PASS / PASS | backend_only: USING true / WITH CHECK true |
| loyalty_events | True | postgres | 0 | broad grants | PASS / PASS / PASS / PASS | backend_only: USING true / WITH CHECK true |
| loyalty_rewards | True | postgres | 0 | broad grants | PASS / PASS / PASS / PASS | backend_only: USING true / WITH CHECK true |
| notification_outbox | True | postgres | 0 | broad grants | PASS / PASS / PASS / PASS | backend_only: USING true / WITH CHECK true |
| payment_transactions | True | postgres | 0 | broad grants | PASS / PASS / PASS / PASS | backend_only: USING true / WITH CHECK true |
| payments | True | postgres | 0 | broad grants | PASS / PASS / PASS / PASS | backend_only: USING true / WITH CHECK true |
| revenue_invoices | True | postgres | 0 | broad grants | PASS / PASS / PASS / PASS | backend_only: USING true / WITH CHECK true |
| schedule_resources | True | postgres | 0 | broad grants | PASS / PASS / PASS / PASS | backend_only: USING true / WITH CHECK true |
| schedule_slots | True | postgres | 0 | broad grants | PASS / PASS / PASS / PASS | backend_only: USING true / WITH CHECK true |
| service_addons | True | postgres | 0 | broad grants | PASS / PASS / PASS / PASS | backend_only: USING true / WITH CHECK true |
| service_inventory_templates | True | postgres | 0 | revoked/absent | PASS / PASS / PASS / PASS | backend_only: USING true / WITH CHECK true |
| service_prices | True | postgres | 0 | revoked/absent | PASS / PASS / PASS / PASS | backend_only: USING true / WITH CHECK true |
| services | True | postgres | 0 | broad grants | PASS / PASS / PASS / PASS | backend_only: USING true / WITH CHECK true |
| shifts | True | postgres | 0 | broad grants | PASS / PASS / PASS / PASS | backend_only: USING true / WITH CHECK true |
| slot_hold_groups | True | postgres | 0 | broad grants | PASS / PASS / PASS / PASS | backend_only: USING true / WITH CHECK true |
| staff_profiles | True | postgres | 0 | broad grants | PASS / PASS / PASS / PASS | backend_only: USING true / WITH CHECK true |
| staff_shift_assignments | True | postgres | 0 | broad grants | PASS / PASS / PASS / PASS | backend_only: USING true / WITH CHECK true |
| team_memberships | True | postgres | 0 | broad grants | PASS / PASS / PASS / PASS | backend_only: USING true / WITH CHECK true |
| vehicles | True | postgres | 0 | broad grants | PASS / PASS / PASS / PASS | backend_only: USING true / WITH CHECK true |

Local tests additionally deny TRUNCATE on every table for both client roles, deny backend TRUNCATE, and verify backend reads. 64 tables × 2 client roles × 5 operations = 640 real SQL permission attempts. The API tests use separate synthetic signed identities and two tenants on this runtime role.

## Provider and infrastructure relations

| Schema | Relation | Kind | RLS | Force RLS | Owner | Runtime data result |
|---|---|---|---|---|---|---|
| auth | audit_log_entries | r | True | False | supabase_auth_admin | NOT TESTED; provider-managed metadata only |
| auth | custom_oauth_providers | r | False | False | supabase_auth_admin | NOT TESTED; provider-managed metadata only |
| auth | flow_state | r | True | False | supabase_auth_admin | NOT TESTED; provider-managed metadata only |
| auth | identities | r | True | False | supabase_auth_admin | NOT TESTED; provider-managed metadata only |
| auth | instances | r | True | False | supabase_auth_admin | NOT TESTED; provider-managed metadata only |
| auth | mfa_amr_claims | r | True | False | supabase_auth_admin | NOT TESTED; provider-managed metadata only |
| auth | mfa_challenges | r | True | False | supabase_auth_admin | NOT TESTED; provider-managed metadata only |
| auth | mfa_factors | r | True | False | supabase_auth_admin | NOT TESTED; provider-managed metadata only |
| auth | mfa_recovery_code_sets | r | False | False | supabase_auth_admin | NOT TESTED; provider-managed metadata only |
| auth | mfa_recovery_codes | r | False | False | supabase_auth_admin | NOT TESTED; provider-managed metadata only |
| auth | oauth_authorizations | r | False | False | supabase_auth_admin | NOT TESTED; provider-managed metadata only |
| auth | oauth_client_states | r | False | False | supabase_auth_admin | NOT TESTED; provider-managed metadata only |
| auth | oauth_clients | r | False | False | supabase_auth_admin | NOT TESTED; provider-managed metadata only |
| auth | oauth_consents | r | False | False | supabase_auth_admin | NOT TESTED; provider-managed metadata only |
| auth | one_time_tokens | r | True | False | supabase_auth_admin | NOT TESTED; provider-managed metadata only |
| auth | refresh_tokens | r | True | False | supabase_auth_admin | NOT TESTED; provider-managed metadata only |
| auth | saml_providers | r | True | False | supabase_auth_admin | NOT TESTED; provider-managed metadata only |
| auth | saml_relay_states | r | True | False | supabase_auth_admin | NOT TESTED; provider-managed metadata only |
| auth | schema_migrations | r | True | False | supabase_auth_admin | NOT TESTED; provider-managed metadata only |
| auth | scim_tokens | r | False | False | supabase_auth_admin | NOT TESTED; provider-managed metadata only |
| auth | scim_users | r | False | False | supabase_auth_admin | NOT TESTED; provider-managed metadata only |
| auth | sessions | r | True | False | supabase_auth_admin | NOT TESTED; provider-managed metadata only |
| auth | sso_domains | r | True | False | supabase_auth_admin | NOT TESTED; provider-managed metadata only |
| auth | sso_providers | r | True | False | supabase_auth_admin | NOT TESTED; provider-managed metadata only |
| auth | users | r | True | False | supabase_auth_admin | NOT TESTED; provider-managed metadata only |
| auth | webauthn_challenges | r | False | False | supabase_auth_admin | NOT TESTED; provider-managed metadata only |
| auth | webauthn_credentials | r | False | False | supabase_auth_admin | NOT TESTED; provider-managed metadata only |
| cron | job | r | True | False | supabase_admin | NOT TESTED; provider-managed metadata only |
| cron | job_run_details | r | True | False | supabase_admin | NOT TESTED; provider-managed metadata only |
| extensions | pg_stat_statements | v | False | False | postgres | NOT TESTED; provider-managed metadata only |
| extensions | pg_stat_statements_info | v | False | False | postgres | NOT TESTED; provider-managed metadata only |
| net | _http_response | r | False | False | supabase_admin | NOT TESTED; provider-managed metadata only |
| net | http_request_queue | r | False | False | supabase_admin | NOT TESTED; provider-managed metadata only |
| realtime | messages | p | True | False | supabase_realtime_admin | NOT TESTED; provider-managed metadata only |
| realtime | schema_migrations | r | False | False | supabase_admin | NOT TESTED; provider-managed metadata only |
| realtime | subscription | r | False | False | supabase_realtime_admin | NOT TESTED; provider-managed metadata only |
| storage | buckets | r | True | False | supabase_storage_admin | NOT TESTED; provider-managed metadata only |
| storage | buckets_analytics | r | True | False | supabase_storage_admin | NOT TESTED; provider-managed metadata only |
| storage | buckets_vectors | r | True | False | supabase_storage_admin | NOT TESTED; provider-managed metadata only |
| storage | migrations | r | True | False | supabase_storage_admin | NOT TESTED; provider-managed metadata only |
| storage | objects | r | True | False | supabase_storage_admin | NOT TESTED; provider-managed metadata only |
| storage | s3_multipart_uploads | r | True | False | supabase_storage_admin | NOT TESTED; provider-managed metadata only |
| storage | s3_multipart_uploads_parts | r | True | False | supabase_storage_admin | NOT TESTED; provider-managed metadata only |
| storage | vector_indexes | r | True | False | supabase_storage_admin | NOT TESTED; provider-managed metadata only |
| supabase_migrations | schema_migrations | r | False | False | postgres | NOT TESTED; provider-managed metadata only |
| vault | decrypted_secrets | v | False | False | supabase_admin | NOT TESTED; provider-managed metadata only |
| vault | secrets | r | False | False | supabase_admin | NOT TESTED; provider-managed metadata only |

## Functions and procedures

ACLs, configuration, return types, roles, defaults and policies are preserved in `evidence/live-db-metadata.json`. Event triggers and non-internal triggers are in `live-db-extra.json`. Vendor function semantics were not dynamically tested.

| Schema | Function | Arguments | Definer | Owner | Configuration | Execution result |
|---|---|---|---|---|---|---|
| auth | email |  | False | supabase_auth_admin | None | NOT TESTED (metadata inspection) |
| auth | jwt |  | False | supabase_auth_admin | None | NOT TESTED (metadata inspection) |
| auth | role |  | False | supabase_auth_admin | None | NOT TESTED (metadata inspection) |
| auth | uid |  | False | supabase_auth_admin | None | NOT TESTED (metadata inspection) |
| cron | alter_job | job_id bigint, schedule text, command text, database text, username text, active boolean | False | supabase_admin | None | NOT TESTED (metadata inspection) |
| cron | job_cache_invalidate |  | False | supabase_admin | None | NOT TESTED (metadata inspection) |
| cron | schedule | job_name text, schedule text, command text | False | supabase_admin | None | NOT TESTED (metadata inspection) |
| cron | schedule | schedule text, command text | False | supabase_admin | None | NOT TESTED (metadata inspection) |
| cron | schedule_in_database | job_name text, schedule text, command text, database text, username text, active boolean | False | supabase_admin | None | NOT TESTED (metadata inspection) |
| cron | unschedule | job_id bigint | False | supabase_admin | None | NOT TESTED (metadata inspection) |
| cron | unschedule | job_name text | False | supabase_admin | None | NOT TESTED (metadata inspection) |
| extensions | armor | bytea | False | postgres | None | NOT TESTED (metadata inspection) |
| extensions | armor | bytea, text[], text[] | False | postgres | None | NOT TESTED (metadata inspection) |
| extensions | crypt | text, text | False | postgres | None | NOT TESTED (metadata inspection) |
| extensions | dearmor | text | False | postgres | None | NOT TESTED (metadata inspection) |
| extensions | decrypt | bytea, bytea, text | False | postgres | None | NOT TESTED (metadata inspection) |
| extensions | decrypt_iv | bytea, bytea, bytea, text | False | postgres | None | NOT TESTED (metadata inspection) |
| extensions | digest | bytea, text | False | postgres | None | NOT TESTED (metadata inspection) |
| extensions | digest | text, text | False | postgres | None | NOT TESTED (metadata inspection) |
| extensions | encrypt | bytea, bytea, text | False | postgres | None | NOT TESTED (metadata inspection) |
| extensions | encrypt_iv | bytea, bytea, bytea, text | False | postgres | None | NOT TESTED (metadata inspection) |
| extensions | gen_random_bytes | integer | False | postgres | None | NOT TESTED (metadata inspection) |
| extensions | gen_random_uuid |  | False | postgres | None | NOT TESTED (metadata inspection) |
| extensions | gen_salt | text | False | postgres | None | NOT TESTED (metadata inspection) |
| extensions | gen_salt | text, integer | False | postgres | None | NOT TESTED (metadata inspection) |
| extensions | grant_pg_cron_access |  | False | supabase_admin | ['search_path=""'] | NOT TESTED (metadata inspection) |
| extensions | grant_pg_graphql_access |  | False | supabase_admin | ['search_path=""'] | NOT TESTED (metadata inspection) |
| extensions | grant_pg_net_access |  | False | supabase_admin | ['search_path=""'] | NOT TESTED (metadata inspection) |
| extensions | hmac | bytea, bytea, text | False | postgres | None | NOT TESTED (metadata inspection) |
| extensions | hmac | text, text, text | False | postgres | None | NOT TESTED (metadata inspection) |
| extensions | pg_stat_statements | showtext boolean, OUT userid oid, OUT dbid oid, OUT toplevel boolean, OUT queryid bigint, OUT query text, OUT plans bigint, OUT total_plan_time double precision, OUT min_plan_time double precision, OUT max_plan_time double precision, OUT mean_plan_time double precision, OUT stddev_plan_time double precision, OUT calls bigint, OUT total_exec_time double precision, OUT min_exec_time double precision, OUT max_exec_time double precision, OUT mean_exec_time double precision, OUT stddev_exec_time double precision, OUT rows bigint, OUT shared_blks_hit bigint, OUT shared_blks_read bigint, OUT shared_blks_dirtied bigint, OUT shared_blks_written bigint, OUT local_blks_hit bigint, OUT local_blks_read bigint, OUT local_blks_dirtied bigint, OUT local_blks_written bigint, OUT temp_blks_read bigint, OUT temp_blks_written bigint, OUT shared_blk_read_time double precision, OUT shared_blk_write_time double precision, OUT local_blk_read_time double precision, OUT local_blk_write_time double precision, OUT temp_blk_read_time double precision, OUT temp_blk_write_time double precision, OUT wal_records bigint, OUT wal_fpi bigint, OUT wal_bytes numeric, OUT jit_functions bigint, OUT jit_generation_time double precision, OUT jit_inlining_count bigint, OUT jit_inlining_time double precision, OUT jit_optimization_count bigint, OUT jit_optimization_time double precision, OUT jit_emission_count bigint, OUT jit_emission_time double precision, OUT jit_deform_count bigint, OUT jit_deform_time double precision, OUT stats_since timestamp with time zone, OUT minmax_stats_since timestamp with time zone | False | postgres | None | NOT TESTED (metadata inspection) |
| extensions | pg_stat_statements_info | OUT dealloc bigint, OUT stats_reset timestamp with time zone | False | postgres | None | NOT TESTED (metadata inspection) |
| extensions | pg_stat_statements_reset | userid oid, dbid oid, queryid bigint, minmax_only boolean | False | postgres | None | NOT TESTED (metadata inspection) |
| extensions | pgp_armor_headers | text, OUT key text, OUT value text | False | postgres | None | NOT TESTED (metadata inspection) |
| extensions | pgp_key_id | bytea | False | postgres | None | NOT TESTED (metadata inspection) |
| extensions | pgp_pub_decrypt | bytea, bytea | False | postgres | None | NOT TESTED (metadata inspection) |
| extensions | pgp_pub_decrypt | bytea, bytea, text | False | postgres | None | NOT TESTED (metadata inspection) |
| extensions | pgp_pub_decrypt | bytea, bytea, text, text | False | postgres | None | NOT TESTED (metadata inspection) |
| extensions | pgp_pub_decrypt_bytea | bytea, bytea | False | postgres | None | NOT TESTED (metadata inspection) |
| extensions | pgp_pub_decrypt_bytea | bytea, bytea, text | False | postgres | None | NOT TESTED (metadata inspection) |
| extensions | pgp_pub_decrypt_bytea | bytea, bytea, text, text | False | postgres | None | NOT TESTED (metadata inspection) |
| extensions | pgp_pub_encrypt | text, bytea | False | postgres | None | NOT TESTED (metadata inspection) |
| extensions | pgp_pub_encrypt | text, bytea, text | False | postgres | None | NOT TESTED (metadata inspection) |
| extensions | pgp_pub_encrypt_bytea | bytea, bytea | False | postgres | None | NOT TESTED (metadata inspection) |
| extensions | pgp_pub_encrypt_bytea | bytea, bytea, text | False | postgres | None | NOT TESTED (metadata inspection) |
| extensions | pgp_sym_decrypt | bytea, text | False | postgres | None | NOT TESTED (metadata inspection) |
| extensions | pgp_sym_decrypt | bytea, text, text | False | postgres | None | NOT TESTED (metadata inspection) |
| extensions | pgp_sym_decrypt_bytea | bytea, text | False | postgres | None | NOT TESTED (metadata inspection) |
| extensions | pgp_sym_decrypt_bytea | bytea, text, text | False | postgres | None | NOT TESTED (metadata inspection) |
| extensions | pgp_sym_encrypt | text, text | False | postgres | None | NOT TESTED (metadata inspection) |
| extensions | pgp_sym_encrypt | text, text, text | False | postgres | None | NOT TESTED (metadata inspection) |
| extensions | pgp_sym_encrypt_bytea | bytea, text | False | postgres | None | NOT TESTED (metadata inspection) |
| extensions | pgp_sym_encrypt_bytea | bytea, text, text | False | postgres | None | NOT TESTED (metadata inspection) |
| extensions | pgrst_ddl_watch |  | False | supabase_admin | ['search_path=""'] | NOT TESTED (metadata inspection) |
| extensions | pgrst_drop_watch |  | False | supabase_admin | ['search_path=""'] | NOT TESTED (metadata inspection) |
| extensions | set_graphql_placeholder |  | False | supabase_admin | ['search_path=""'] | NOT TESTED (metadata inspection) |
| extensions | uuid_generate_v1 |  | False | postgres | None | NOT TESTED (metadata inspection) |
| extensions | uuid_generate_v1mc |  | False | postgres | None | NOT TESTED (metadata inspection) |
| extensions | uuid_generate_v3 | namespace uuid, name text | False | postgres | None | NOT TESTED (metadata inspection) |
| extensions | uuid_generate_v4 |  | False | postgres | None | NOT TESTED (metadata inspection) |
| extensions | uuid_generate_v5 | namespace uuid, name text | False | postgres | None | NOT TESTED (metadata inspection) |
| extensions | uuid_nil |  | False | postgres | None | NOT TESTED (metadata inspection) |
| extensions | uuid_ns_dns |  | False | postgres | None | NOT TESTED (metadata inspection) |
| extensions | uuid_ns_oid |  | False | postgres | None | NOT TESTED (metadata inspection) |
| extensions | uuid_ns_url |  | False | postgres | None | NOT TESTED (metadata inspection) |
| extensions | uuid_ns_x500 |  | False | postgres | None | NOT TESTED (metadata inspection) |
| graphql_public | graphql | "operationName" text, query text, variables jsonb, extensions jsonb | False | supabase_admin | None | NOT TESTED (metadata inspection) |
| net | _await_response | request_id bigint | False | supabase_admin | None | NOT TESTED (metadata inspection) |
| net | _encode_url_with_params_array | url text, params_array text[] | False | supabase_admin | None | NOT TESTED (metadata inspection) |
| net | _http_collect_response | request_id bigint, async boolean | False | supabase_admin | None | NOT TESTED (metadata inspection) |
| net | _urlencode_string | string character varying | False | supabase_admin | None | NOT TESTED (metadata inspection) |
| net | check_worker_is_up |  | False | supabase_admin | None | NOT TESTED (metadata inspection) |
| net | http_collect_response | request_id bigint, async boolean | False | supabase_admin | None | NOT TESTED (metadata inspection) |
| net | http_delete | url text, params jsonb, headers jsonb, timeout_milliseconds integer, body jsonb | False | supabase_admin | None | NOT TESTED (metadata inspection) |
| net | http_get | url text, params jsonb, headers jsonb, timeout_milliseconds integer | False | supabase_admin | None | NOT TESTED (metadata inspection) |
| net | http_post | url text, body jsonb, params jsonb, headers jsonb, timeout_milliseconds integer | False | supabase_admin | None | NOT TESTED (metadata inspection) |
| net | wait_until_running |  | False | supabase_admin | None | NOT TESTED (metadata inspection) |
| net | wake |  | False | supabase_admin | None | NOT TESTED (metadata inspection) |
| net | worker_restart |  | False | supabase_admin | None | NOT TESTED (metadata inspection) |
| public | rls_auto_enable |  | True | postgres | ['search_path=pg_catalog'] | NOT TESTED (metadata inspection) |
| realtime | apply_rls | wal jsonb, max_record_bytes integer | False | supabase_realtime_admin | None | NOT TESTED (metadata inspection) |
| realtime | broadcast_changes | topic_name text, event_name text, operation text, table_name text, table_schema text, new record, old record, level text | False | supabase_realtime_admin | None | NOT TESTED (metadata inspection) |
| realtime | build_prepared_statement_sql | prepared_statement_name text, entity regclass, columns realtime.wal_column[] | False | supabase_realtime_admin | None | NOT TESTED (metadata inspection) |
| realtime | cast | val text, type_ regtype | False | supabase_realtime_admin | None | NOT TESTED (metadata inspection) |
| realtime | check_equality_op | op realtime.equality_op, type_ regtype, val_1 text, val_2 text | False | supabase_realtime_admin | None | NOT TESTED (metadata inspection) |
| realtime | check_equality_op | op realtime.equality_op, type_ regtype, val_1 text, val_2 text, negate boolean | False | supabase_realtime_admin | None | NOT TESTED (metadata inspection) |
| realtime | is_visible_through_filters | columns realtime.wal_column[], filters realtime.user_defined_filter[] | False | supabase_realtime_admin | None | NOT TESTED (metadata inspection) |
| realtime | list_changes | publication name, slot_name name, max_changes integer, max_record_bytes integer | False | supabase_realtime_admin | ['log_min_messages=fatal'] | NOT TESTED (metadata inspection) |
| realtime | quote_wal2json | entity regclass | False | supabase_realtime_admin | None | NOT TESTED (metadata inspection) |
| realtime | send | payload jsonb, event text, topic text, private boolean | False | supabase_realtime_admin | None | NOT TESTED (metadata inspection) |
| realtime | send_binary | payload bytea, event text, topic text, private boolean | False | supabase_realtime_admin | None | NOT TESTED (metadata inspection) |
| realtime | subscription_check_filters |  | False | supabase_realtime_admin | None | NOT TESTED (metadata inspection) |
| realtime | to_regrole | role_name text | False | supabase_realtime_admin | None | NOT TESTED (metadata inspection) |
| realtime | topic |  | False | supabase_realtime_admin | None | NOT TESTED (metadata inspection) |
| realtime | wal2json_escape_identifier | name text | False | supabase_realtime_admin | None | NOT TESTED (metadata inspection) |
| storage | allow_any_operation | expected_operations text[] | False | supabase_storage_admin | None | NOT TESTED (metadata inspection) |
| storage | allow_only_operation | expected_operation text | False | supabase_storage_admin | None | NOT TESTED (metadata inspection) |
| storage | can_insert_object | bucketid text, name text, owner uuid, metadata jsonb | False | supabase_storage_admin | None | NOT TESTED (metadata inspection) |
| storage | enforce_bucket_name_length |  | False | supabase_storage_admin | None | NOT TESTED (metadata inspection) |
| storage | extension | name text | False | supabase_storage_admin | None | NOT TESTED (metadata inspection) |
| storage | filename | name text | False | supabase_storage_admin | None | NOT TESTED (metadata inspection) |
| storage | foldername | name text | False | supabase_storage_admin | None | NOT TESTED (metadata inspection) |
| storage | get_common_prefix | p_key text, p_prefix text, p_delimiter text | False | supabase_storage_admin | None | NOT TESTED (metadata inspection) |
| storage | get_size_by_bucket |  | False | supabase_storage_admin | None | NOT TESTED (metadata inspection) |
| storage | list_multipart_uploads_with_delimiter | bucket_id text, prefix_param text, delimiter_param text, max_keys integer, next_key_token text, next_upload_token text | False | supabase_storage_admin | None | NOT TESTED (metadata inspection) |
| storage | list_objects_with_delimiter | _bucket_id text, prefix_param text, delimiter_param text, max_keys integer, start_after text, next_token text, sort_order text | False | supabase_storage_admin | None | NOT TESTED (metadata inspection) |
| storage | operation |  | False | supabase_storage_admin | None | NOT TESTED (metadata inspection) |
| storage | protect_delete |  | False | supabase_storage_admin | None | NOT TESTED (metadata inspection) |
| storage | search | prefix text, bucketname text, limits integer, levels integer, offsets integer, search text, sortcolumn text, sortorder text | False | supabase_storage_admin | None | NOT TESTED (metadata inspection) |
| storage | search_by_timestamp | p_prefix text, p_bucket_id text, p_limit integer, p_level integer, p_start_after text, p_sort_order text, p_sort_column text, p_sort_column_after text | False | supabase_storage_admin | None | NOT TESTED (metadata inspection) |
| storage | search_v2 | prefix text, bucket_name text, limits integer, levels integer, start_after text, sort_order text, sort_column text, sort_column_after text | False | supabase_storage_admin | None | NOT TESTED (metadata inspection) |
| storage | update_updated_at_column |  | False | supabase_storage_admin | None | NOT TESTED (metadata inspection) |
| vault | _crypto_aead_det_decrypt | message bytea, additional bytea, key_id bigint, context bytea, nonce bytea | False | supabase_admin | None | NOT TESTED (metadata inspection) |
| vault | _crypto_aead_det_encrypt | message bytea, additional bytea, key_id bigint, context bytea, nonce bytea | False | supabase_admin | None | NOT TESTED (metadata inspection) |
| vault | _crypto_aead_det_noncegen |  | False | supabase_admin | None | NOT TESTED (metadata inspection) |
| vault | create_secret | new_secret text, new_name text, new_description text, new_key_id uuid | True | supabase_admin | ['search_path=""'] | NOT TESTED (metadata inspection) |
| vault | update_secret | secret_id uuid, new_secret text, new_name text, new_description text, new_key_id uuid | True | supabase_admin | ['search_path=""'] | NOT TESTED (metadata inspection) |

`public.rls_auto_enable` returns `event_trigger`, fixes search_path to pg_catalog, and only enables RLS for public tables. The advisor's execute-grant warning is excessive privilege, not a demonstrated remotely callable privilege escalation. Its grant is revoked locally by the migration. The new `app_private.session_active(uuid,uuid)` returns only a boolean; it reads authoritative session/user state, uses an empty search_path, and grants execution only to the runtime group. Its normal/revoked/banned/unverified cases are tested locally.

## Buckets

| Bucket | Live public | Live maximum bytes | MIME allowlist |
|---|---|---|---|
| job-quality-photos | False | 8388608 | ['image/jpeg', 'image/png', 'image/webp'] |

`complaint-evidence` and `expense-evidence` are required by source but were absent in the inspected project. Storage policies are included in the raw policy inventory. Signed URL expiry and tenant selection are source/unit-tested, not verified against a live isolated Supabase Storage instance.
