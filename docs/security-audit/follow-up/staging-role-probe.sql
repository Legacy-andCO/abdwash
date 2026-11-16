CREATE FUNCTION pg_temp.audit_client_permissions() RETURNS jsonb LANGUAGE plpgsql AS $probe$
DECLARE t record; role_name text; operation text; statement text; outcome text; results jsonb:='[]'::jsonb;
BEGIN
FOR t IN SELECT c.relname,a.attname FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace JOIN LATERAL (SELECT attname FROM pg_attribute WHERE attrelid=c.oid AND attnum>0 AND NOT attisdropped ORDER BY attnum LIMIT 1) a ON true WHERE n.nspname='public' AND c.relkind='r' ORDER BY c.relname LOOP
 FOREACH role_name IN ARRAY ARRAY['anon','authenticated'] LOOP
  FOREACH operation IN ARRAY ARRAY['SELECT','INSERT','UPDATE','DELETE','TRUNCATE'] LOOP
   statement:=CASE operation
    WHEN 'SELECT' THEN format('SELECT * FROM public.%I LIMIT 0',t.relname)
    WHEN 'INSERT' THEN format('INSERT INTO public.%I DEFAULT VALUES',t.relname)
    WHEN 'UPDATE' THEN format('UPDATE public.%I SET %I=%I WHERE false',t.relname,t.attname,t.attname)
    WHEN 'DELETE' THEN format('DELETE FROM public.%I WHERE false',t.relname)
    WHEN 'TRUNCATE' THEN format('TRUNCATE ONLY public.%I',t.relname) END;
   BEGIN
    EXECUTE format('SET LOCAL ROLE %I',role_name);
    EXECUTE statement;
    RAISE SQLSTATE 'ZX001' USING MESSAGE='Rollback unexpectedly permitted operation';
   EXCEPTION WHEN OTHERS THEN outcome:=SQLSTATE;
   END;
   RESET ROLE;
   results:=results || jsonb_build_array(jsonb_build_object('table',t.relname,'role',role_name,'operation',operation,'sqlstate',outcome,'result',CASE WHEN outcome='42501' THEN 'PASS' ELSE 'FAIL' END));
  END LOOP;
 END LOOP;
END LOOP;
RETURN results;
END $probe$;
SELECT pg_temp.audit_client_permissions() AS results;
