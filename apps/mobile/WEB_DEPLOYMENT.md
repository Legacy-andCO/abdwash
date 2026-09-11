# Expo manager web deployment

The Android and browser apps use the same entry point, screens, Supabase
password login, `/staff/context` authorization, and FastAPI API client.
There is no second manager frontend and no database migration.

## Build

From the repository root, install with `npm ci`, then run:

```sh
npm run build:web --workspace=@trifecta/mobile
```

Equivalently, from `apps/mobile`: `npx expo export --platform web`.
The production SPA is in `apps/mobile/dist` (`dist` relative to the app).
For development, run `npm run web --workspace=@trifecta/mobile`.

## Separate Vercel project

1. Import the same Git repository as a **new** project, e.g. `trifecta-staff`.
2. Set Root Directory to `apps/mobile`, Framework Preset to **Other**, and
   Node.js to 22.x. Enable access to files outside the Root Directory for the
   repository workspace dependencies and root lockfile.
3. The app's `vercel.json` sets install to `npm ci --prefix ../..`, build to
   `npm run build:web`, output to `dist`, and the SPA fallback rewrite.
   Do not use the repo root's `npm run build` (that builds the customer site).
4. Add these build-time variables for Production and any Preview environments:
   - `EXPO_PUBLIC_API_BASE_URL`: HTTPS URL of the existing FastAPI backend,
     not the staff frontend. Keep any existing API path prefix.
   - `EXPO_PUBLIC_SUPABASE_URL`: existing Supabase project URL.
   - `EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY`: public/publishable Supabase key.
   All three are embedded in the bundle. Never use a service-role/secret key.
5. In the backend deployment, append `https://staff.trifecta-wash.com` to
   `CORS_ORIGINS` (JSON array), keeping all existing customer origins. Also add
   the exact Vercel preview origin when testing previews, or use a fixed staging
   domain. Local Expo web normally uses `http://localhost:8081`.
6. Deploy the new project; add `staff.trifecta-wash.com` in its Domains settings
   and apply the DNS record Vercel provides. Leave the customer project intact.
7. Rebuild whenever public environment variables change. The current username/
   password flow does not require an auth redirect. If redirect-based auth is
   enabled later, add the staff origin to Supabase's allowed redirect URLs,
   preserving existing customer settings.

## Browser behavior and boundaries

- Supabase uses its standard browser localStorage persistence, token refresh,
  and cross-tab auth events. SecureStore remains the Android storage. Browser
  privacy settings that block localStorage can prevent persistence across reloads.
- Existing role checks and `/staff/context` remain authoritative; hosting the
  bundle does not grant staff access.
- Date/time fields use browser inputs. Alerts use modal dialogs with the existing
  confirmation labels and callbacks. Main content and forms have desktop width
  limits; sheets remain scrollable and fit narrow viewports.
- Evidence/receipt selection, JPEG preparation and upload use Expo's web
  implementations and the existing upload API. Camera capture depends on the
  browser/device; desktop browsers may show a file chooser instead.
- Trip location uses foreground browser geolocation over HTTPS, with a bounded
  timeout. If denied or unavailable, the existing trip flow continues without
  an ETA. Maps/phone/WhatsApp links require a browser or installed handler.
- Haptic feedback is omitted on web. Android haptics, permissions, pickers,
  storage, and field features keep their existing implementations.
- Navigation stays in the existing app state; tabs do not acquire distinct URLs.
  Reloading restores authentication and opens the existing initial dashboard.

References: [Expo web publishing](https://docs.expo.dev/guides/publishing-websites/)
and [Supabase client options](https://supabase.com/docs/reference/javascript/initializing).
