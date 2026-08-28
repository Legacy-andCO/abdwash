-- Trifecta notification outbox scheduling. Stable deployed job and Vault names are retained.
-- Vault values are deliberately provisioned separately and never committed here.

create extension if not exists pg_cron with schema pg_catalog;
create extension if not exists pg_net;
create extension if not exists supabase_vault with schema vault;

grant usage on schema cron to postgres;
grant all privileges on all tables in schema cron to postgres;

select cron.schedule(
  'abdwash-notification-dispatch',
  '* * * * *',
  $job$
    select net.http_post(
      url := settings.dispatch_url,
      headers := jsonb_build_object(
        'Content-Type', 'application/json',
        'X-Outbox-Dispatch-Secret', settings.dispatch_secret
      ),
      body := '{}'::jsonb,
      timeout_milliseconds := 15000
    ) as request_id
    from (
      select
        nullif(max(decrypted_secret) filter (
          where name = 'abdwash_outbox_dispatch_url'
        ), '') as dispatch_url,
        nullif(max(decrypted_secret) filter (
          where name = 'abdwash_outbox_dispatch_secret'
        ), '') as dispatch_secret
      from vault.decrypted_secrets
      where name in (
        'abdwash_outbox_dispatch_url',
        'abdwash_outbox_dispatch_secret'
      )
    ) as settings
    where settings.dispatch_url is not null
      and settings.dispatch_secret is not null;
  $job$
);
