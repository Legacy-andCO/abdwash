// Temporary, isolated test operator. Never deploy to a production project.
// prepare_staging_operator.py substitutes only a token HASH and a short expiry.
import { createClient } from "npm:@supabase/supabase-js@2.112.4";

const EXPECTED_URL = "https://mgfzfgvlrxwyyftwukwf.supabase.co";
const TOKEN_HASH = "__TOKEN_HASH__";
const EXPIRES = "__EXPIRES__";
const names = ["customer_a", "customer_b", "employee", "manager", "admin", "admin_two", "other_employee", "foreign_manager"];
const buckets: Record<string, number> = {"job-quality-photos":8388608,"complaint-evidence":1048576,"expense-evidence":10485760};
const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), {status, headers:{"Content-Type":"application/json","Cache-Control":"no-store"}});

Deno.serve(async (req) => {
  if (Deno.env.get("SUPABASE_URL") !== EXPECTED_URL || Date.now() >= Date.parse(EXPIRES)) return json({error:"disabled"},410);
  if (req.method !== "POST") return json({error:"method"},405);
  const raw = req.headers.get("x-staging-operator") ?? "";
  if (raw.length > 256) return json({error:"unauthorized"},401);
  const hash = Array.from(new Uint8Array(await crypto.subtle.digest("SHA-256", new TextEncoder().encode(raw)))).map(x=>x.toString(16).padStart(2,"0")).join("");
  let difference = hash.length ^ TOKEN_HASH.length;
  for(let i=0;i<hash.length;i++) difference |= hash.charCodeAt(i) ^ (TOKEN_HASH.charCodeAt(i) || 0);
  if (difference !== 0) return json({error:"unauthorized"},401);
  const text = await req.text();
  if(text.length > 8192) return json({error:"size"},413);
  try {
    const body = JSON.parse(text);
    const admin = createClient(EXPECTED_URL,Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!,{auth:{persistSession:false,autoRefreshToken:false}});
    if(body.op === "seed") {
      const users: Record<string,string> = {};
      for(const name of names) {
        if(typeof body.passwords?.[name] !== "string" || body.passwords[name].length < 24) return json({error:"password policy"},400);
      }
      const {data:existing,error:listError} = await admin.auth.admin.listUsers({perPage:100});
      if(listError) return json({error:listError.code ?? "list"},400);
      for(const name of names) {
        const email = `${name}@security.example.com`;
        const found = existing.users.find(x=>x.email === email);
        if(found) { users[name]=found.id; continue; }
        const {data,error}=await admin.auth.admin.createUser({email,password:body.passwords[name],email_confirm:true});
        if(error) return json({error:error.code ?? "create"},400);
        users[name]=data.user.id;
      }
      return json({users}); // no passwords, tokens, factors or provider keys
    }
    if(body.op === "normalize_test_emails") {
      const {data,error}=await admin.auth.admin.listUsers({perPage:100});
      if(error) return json({error:"list"},400);
      let changed=0;
      for(const name of names) {
        const found=data.users.find(x=>x.email===`${name}@security.trifecta.invalid`);
        if(found) {
          const {error}=await admin.auth.admin.updateUserById(found.id,{email:`${name}@security.example.com`,email_confirm:true});
          if(error) return json({error:error.code ?? "normalize"},400);
          changed++;
        }
      }
      return json({changed});
    }
    if(body.op === "buckets") {
      const results = [];
      for(const [name,limit] of Object.entries(buckets)) {
        const config={public:false,fileSizeLimit:limit,allowedMimeTypes:["image/jpeg","image/png","image/webp"]};
        const {data}=await admin.storage.getBucket(name);
        const {error}=data ? await admin.storage.updateBucket(name,config) : await admin.storage.createBucket(name,config);
        if(error) return json({error:error.message},400);
        results.push(name);
      }
      return json({buckets:results});
    }
    if(["ban","unban","delete_factor","sign_out"].includes(body.op)) {
      const {data,error}=await admin.auth.admin.getUserById(body.user_id);
      if(error || !names.some(n=>data.user.email===`${n}@security.example.com` || data.user.email===`${n}@security.trifecta.invalid`)) return json({error:"synthetic users only"},403);
      if(body.op === "ban" || body.op === "unban") {
        const {error}=await admin.auth.admin.updateUserById(body.user_id,{ban_duration:body.op==="ban" ? "1h" : "none"});
        return error ? json({error:error.code ?? "ban"},400) : json({ok:true});
      }
      if(body.op === "delete_factor") {
        const {data:f,error:fe}=await admin.auth.admin.mfa.listFactors({userId:body.user_id});
        if(fe || !f.factors.some(x=>x.id===body.factor_id)) return json({error:"factor ownership"},403);
        const {error}=await admin.auth.admin.mfa.deleteFactor({userId:body.user_id,id:body.factor_id});
        return error ? json({error:error.code ?? "factor"},400) : json({ok:true});
      }
      const {data:session,error:se}=await admin.auth.getUser(body.access_token);
      if(se || session.user.id !== body.user_id) return json({error:"session ownership"},403);
      const {error:signOutError}=await admin.auth.admin.signOut(body.access_token,"global");
      return signOutError ? json({error:signOutError.code ?? "signout"},400) : json({ok:true});
    }
    if(body.op === "upload" || body.op === "download") {
      if(!(body.bucket in buckets) || typeof body.path !== "string" || !/^security-audit\/[a-z0-9_-]+\/[a-z0-9_-]+\.png$/.test(body.path)) return json({error:"test paths only"},403);
      const result=body.op === "upload" ? await admin.storage.from(body.bucket).createSignedUploadUrl(body.path,{upsert:false}) : await admin.storage.from(body.bucket).createSignedUrl(body.path,body.seconds===2?2:60);
      return result.error ? json({error:result.error.message},400) : json(result.data);
    }
    return json({error:"operation"},400);
  } catch { return json({error:"operator failure"},500); }
});
