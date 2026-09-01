"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { useAuth } from "./auth-provider";
import { LocationPicker } from "./location-picker";
import { PhoneInput } from "./phone-input";
import {
  createCustomerAddress,
  createCustomerVehicle,
  deleteCustomerAccount,
  deleteCustomerAddress,
  deleteCustomerVehicle,
  updateCustomerAddress,
  updateCustomerProfile,
  updateCustomerVehicle,
  type SavedAddressInput,
  type SavedVehicleInput,
} from "@/lib/api";
import {
  clearCachedCustomerProfile,
  loadCustomerProfile,
  setCachedCustomerProfile,
} from "@/lib/customer-profile-resource";
import { clearCachedCustomerBookings } from "@/lib/customer-bookings-resource";
import { localizedCustomerError } from "@/lib/customer-error";
import type { TranslationKey } from "@/lib/i18n";
import { normalizePhone } from "@/lib/phone";
import type {
  CustomerProfileBootstrap,
  CustomerSavedAddress,
  CustomerSavedVehicle,
  Location,
} from "@/lib/types";
import type { CountryCode } from "libphonenumber-js/min";
import { useI18n } from "./i18n-provider";
import { isVehicleType, VEHICLE_TYPES } from "@/lib/vehicle-types";
import { clearCustomerBrowserState } from "@/lib/guest-device";
import { AuthenticatedPasswordChange } from "./authenticated-password-change";

const emptyLocation: Location = {
  written_address: "",
  location_url: "",
  latitude: null,
  longitude: null,
  instructions: "",
};
const emptyVehicle: SavedVehicleInput = {
  make: "",
  model: "",
  year: null,
  vehicle_type: "",
  colour: null,
  plate_number: "",
  notes: null,
};

export function CustomerProfileManager() {
  const { language, t } = useI18n();
  const languageRef = useRef(language);
  const translationRef = useRef(t);
  const { user, loading: authLoading, logoutAfterAccountDeletion } = useAuth();
  const router = useRouter();
  const [data, setData] = useState<CustomerProfileBootstrap | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [saving, setSaving] = useState(false);
  const [personal, setPersonal] = useState<{
    first_name: string;
    surname: string;
    phone: string;
    phone_country: CountryCode;
  }>({ first_name: "", surname: "", phone: "", phone_country: "AE" });
  const [addressEditor, setAddressEditor] = useState<{
    id?: string;
    label: string;
    is_default: boolean;
    location: Location;
  } | null>(null);
  const [vehicleEditor, setVehicleEditor] = useState<
    (SavedVehicleInput & { id?: string }) | null
  >(null);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [deleteConfirmation, setDeleteConfirmation] = useState("");
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    languageRef.current = language;
    translationRef.current = t;
  }, [language, t]);

  useEffect(() => {
    if (!authLoading && !user)
      router.replace("/login?returnTo=%2Faccount%2Fprofile");
  }, [authLoading, router, user]);
  const load = useCallback(async () => {
    if (!user) return;
    setError("");
    try {
      const next = await loadCustomerProfile(user.id, { refresh: true });
      setData(next);
      setPersonal({
        first_name:
          next.profile?.first_name ??
          String(user.user_metadata.first_name ?? ""),
        surname:
          next.profile?.surname ?? String(user.user_metadata.surname ?? ""),
        phone: next.profile?.phone ?? "",
        phone_country: "AE",
      });
    } catch (reason) {
      setError(
        localizedCustomerError(
          reason,
          languageRef.current,
          translationRef.current,
        ),
      );
    }
  }, [user]);
  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  async function savePersonal() {
    if (!user) return;
    const phone = normalizePhone(personal.phone, personal.phone_country);
    if (!phone) {
      setError(t("profile.phoneError"));
      return;
    }
    setSaving(true);
    setError("");
    setNotice("");
    try {
      const next = await updateCustomerProfile({
        first_name: personal.first_name,
        surname: personal.surname,
        phone,
      });
      setCachedCustomerProfile(user.id, next);
      setData(next);
      setPersonal((value) => ({ ...value, phone }));
      setNotice(t("profile.changesSaved"));
    } catch (reason) {
      setError(localizedCustomerError(reason, language, t));
    } finally {
      setSaving(false);
    }
  }

  function editAddress(address?: CustomerSavedAddress) {
    setAddressEditor(
      address
        ? {
            id: address.id,
            label: address.label,
            is_default: address.is_default,
            location: {
              written_address: address.written_address,
              location_url: address.location_url,
              latitude: address.latitude,
              longitude: address.longitude,
              instructions: address.location_instructions ?? "",
            },
          }
        : {
            label: t("profile.home"),
            is_default: !data?.addresses.length,
            location: emptyLocation,
          },
    );
  }
  async function saveAddress() {
    if (!addressEditor) return;
    const input: SavedAddressInput = {
      label: addressEditor.label,
      is_default: addressEditor.is_default,
      ...addressEditor.location,
    };
    setSaving(true);
    setError("");
    try {
      addressEditor.id
        ? await updateCustomerAddress(addressEditor.id, input)
        : await createCustomerAddress(input);
      setAddressEditor(null);
      setNotice(t("profile.locationSaved"));
      await load();
    } catch (reason) {
      setError(localizedCustomerError(reason, language, t));
    } finally {
      setSaving(false);
    }
  }
  async function removeAddress(id: string) {
    setSaving(true);
    try {
      await deleteCustomerAddress(id);
      setNotice(t("profile.locationRemoved"));
      await load();
    } catch (reason) {
      setError(localizedCustomerError(reason, language, t));
    } finally {
      setSaving(false);
    }
  }

  async function saveVehicle() {
    if (!vehicleEditor) return;
    if (!vehicleEditor.plate_number.trim()) {
      setError(t("booking.validation.plate"));
      return;
    }
    if (!isVehicleType(vehicleEditor.vehicle_type)) {
      setError(t("booking.validation.vehicleType"));
      return;
    }
    setSaving(true);
    setError("");
    try {
      const { id, ...input } = vehicleEditor;
      id
        ? await updateCustomerVehicle(id, input)
        : await createCustomerVehicle(input);
      setVehicleEditor(null);
      setNotice(id ? t("profile.vehicleUpdated") : t("profile.vehicleAdded"));
      await load();
    } catch (reason) {
      setError(localizedCustomerError(reason, language, t));
    } finally {
      setSaving(false);
    }
  }
  async function removeVehicle(id: string) {
    setSaving(true);
    try {
      await deleteCustomerVehicle(id);
      setNotice(t("profile.vehicleRemoved"));
      await load();
    } catch (reason) {
      setError(localizedCustomerError(reason, language, t));
    } finally {
      setSaving(false);
    }
  }

  async function deleteAccount() {
    if (!user || deleteConfirmation !== "DELETE") return;
    setDeleting(true);
    setError("");
    try {
      await deleteCustomerAccount();
      clearCustomerBrowserState(user.id);
      clearCachedCustomerProfile(user.id);
      clearCachedCustomerBookings(user.id);
      await logoutAfterAccountDeletion();
      router.replace("/?accountDeleted=1");
    } catch (reason) {
      setError(localizedCustomerError(reason, language, t));
      setDeleteOpen(false);
    } finally {
      setDeleting(false);
    }
  }

  if (authLoading || (user && !data && !error))
    return (
      <main className="account-page">
        <div className="shell account-shell">
          <div className="loading-panel">
            <span className="spinner dark" />
            <strong>{t("profile.loading")}</strong>
          </div>
        </div>
      </main>
    );
  if (!user) return null;
  return (
    <main className="account-page">
      <div className="shell account-shell">
        <div className="account-heading">
          <div>
            <p className="eyebrow">
              <span /> {t("nav.account")}
            </p>
            <h1>{t("profile.title")}</h1>
            <p>{t("profile.copy")}</p>
          </div>
          <Link className="button button-ghost" href="/account">
            {t("profile.bookings")}
          </Link>
        </div>
        {error && (
          <div className="error-banner" role="alert">
            {error}{" "}
            {!data && (
              <button type="button" onClick={() => void load()}>
                {t("common.tryAgain")}
              </button>
            )}
          </div>
        )}
        {notice && (
          <div className="inline-notice" role="status">
            <strong>{notice}</strong>
          </div>
        )}
        <section className="profile-panel">
          <h2>{t("profile.personal")}</h2>
          <div className="form-grid two">
            <label>
              <span>{t("booking.details.firstName")}</span>
              <input
                value={personal.first_name}
                onChange={(event) =>
                  setPersonal({ ...personal, first_name: event.target.value })
                }
              />
            </label>
            <label>
              <span>{t("booking.details.surname")}</span>
              <input
                value={personal.surname}
                onChange={(event) =>
                  setPersonal({ ...personal, surname: event.target.value })
                }
              />
            </label>
            <label>
              <span>{t("auth.email")}</span>
              <input
                value={data?.authenticated_email ?? user.email ?? ""}
                readOnly
                aria-readonly="true"
              />
              <small>{t("profile.emailHint")}</small>
            </label>
            <PhoneInput
              value={personal.phone}
              country={personal.phone_country}
              onChange={(phone) => setPersonal({ ...personal, phone })}
              onCountryChange={(phone_country) =>
                setPersonal({ ...personal, phone_country })
              }
            />
          </div>
          <button
            className="button"
            disabled={saving}
            onClick={() => void savePersonal()}
            type="button"
          >
            {t("profile.savePersonal")}
          </button>
        </section>
        <AuthenticatedPasswordChange />
        {data?.loyalty && (
          <section className="profile-panel loyalty-card" id="rewards">
            <header>
              <div>
                <p className="eyebrow">
                  <span /> {t("profile.loyaltyEyebrow")}
                </p>
                <h2>{t("profile.loyaltyTitle")}</h2>
              </div>
              {data.loyalty.available_rewards > 0 && (
                <strong className="loyalty-reward-badge">
                  {t("profile.rewardsAvailable", {
                    count: data.loyalty.available_rewards,
                  })}
                </strong>
              )}
            </header>
            <div
              className="loyalty-progress"
              role="progressbar"
              aria-valuemin={0}
              aria-valuemax={data.loyalty.required_washes}
              aria-valuenow={Math.min(
                data.loyalty.progress_washes,
                data.loyalty.required_washes,
              )}
            >
              <span
                style={{
                  width: `${Math.min(100, (data.loyalty.progress_washes / data.loyalty.required_washes) * 100)}%`,
                }}
              />
            </div>
            <div className="loyalty-metrics">
              <strong>
                {t("profile.loyaltyProgress", {
                  current: data.loyalty.progress_washes,
                  required: data.loyalty.required_washes,
                })}
              </strong>
              <span>
                {data.loyalty.available_rewards
                  ? t("profile.useRewardBooking")
                  : t("profile.washesRemaining", {
                      count: data.loyalty.washes_remaining,
                    })}
              </span>
              <small>
                {t("profile.lifetimeWashes", {
                  count: data.loyalty.lifetime_qualifying_washes,
                })}{" "}
                ·{" "}
                {t("profile.redeemedRewards", {
                  count: data.loyalty.redeemed_rewards,
                })}
              </small>
            </div>
            {data.loyalty.history.length > 0 && (
              <details className="loyalty-history">
                <summary>{t("profile.loyaltyHistory")}</summary>
                {data.loyalty.history.slice(0, 10).map((item) => (
                  <div key={item.id}>
                    <span>
                      {t(
                        `profile.loyaltyEvent.${item.event_type}` as TranslationKey,
                      )}
                      {item.vehicle_label ? ` · ${item.vehicle_label}` : ""}
                    </span>
                    <small>
                      {item.quantity > 0 ? "+" : ""}
                      {item.quantity} ·{" "}
                      {new Date(item.created_at).toLocaleDateString(
                        language === "ar" ? "ar-AE" : "en-AE",
                      )}
                    </small>
                  </div>
                ))}
              </details>
            )}
          </section>
        )}
        <ProfileList
          title={t("profile.savedLocations")}
          addLabel={t("profile.addLocation")}
          disabled={!data?.profile}
          onAdd={() => editAddress()}
        >
          {data?.addresses.map((address) => (
            <article className="profile-item" key={address.id}>
              <div>
                <strong>
                  {address.label}
                  {address.is_default
                    ? ` · ${t("booking.details.default")}`
                    : ""}
                </strong>
                <span>{address.written_address}</span>
              </div>
              <div>
                <button type="button" onClick={() => editAddress(address)}>
                  {t("common.edit")}
                </button>
                <button
                  type="button"
                  onClick={() => void removeAddress(address.id)}
                >
                  {t("common.remove")}
                </button>
              </div>
            </article>
          ))}
        </ProfileList>
        {addressEditor && (
          <section className="profile-panel">
            <h2>
              {addressEditor.id
                ? t("profile.editLocation")
                : t("profile.addLocation")}
            </h2>
            <div className="form-grid two">
              <label>
                <span>{t("profile.label")}</span>
                <input
                  value={addressEditor.label}
                  onChange={(event) =>
                    setAddressEditor({
                      ...addressEditor,
                      label: event.target.value,
                    })
                  }
                />
              </label>
              <label className="checkbox-row">
                <input
                  type="checkbox"
                  checked={addressEditor.is_default}
                  onChange={(event) =>
                    setAddressEditor({
                      ...addressEditor,
                      is_default: event.target.checked,
                    })
                  }
                />{" "}
                {t("profile.defaultLocation")}
              </label>
            </div>
            <LocationPicker
              location={addressEditor.location}
              errors={{}}
              onFieldChange={(field, value) =>
                setAddressEditor({
                  ...addressEditor,
                  location: {
                    ...addressEditor.location,
                    [field]: value,
                    ...(field === "location_url"
                      ? { latitude: null, longitude: null }
                      : {}),
                  },
                })
              }
              onCoordinatesChange={(value, writtenAddress) =>
                setAddressEditor({
                  ...addressEditor,
                  location: {
                    ...addressEditor.location,
                    ...value,
                    written_address:
                      writtenAddress || addressEditor.location.written_address,
                    location_url: `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(`${value.latitude},${value.longitude}`)}`,
                  },
                })
              }
            />
            <div className="profile-actions">
              <button
                className="button"
                disabled={saving}
                type="button"
                onClick={() => void saveAddress()}
              >
                {t("profile.saveLocation")}
              </button>
              <button
                className="button button-ghost"
                type="button"
                onClick={() => setAddressEditor(null)}
              >
                {t("common.cancel")}
              </button>
            </div>
          </section>
        )}
        <ProfileList
          title={t("profile.savedVehicles")}
          addLabel={t("profile.addVehicle")}
          disabled={!data?.profile}
          onAdd={() => setVehicleEditor({ ...emptyVehicle })}
        >
          {data?.vehicles.map((vehicle) => (
            <article className="profile-item" key={vehicle.id}>
              <div>
                <strong>
                  {vehicle.make} {vehicle.model}
                </strong>
                <span className="bidi-ltr">
                  {[vehicle.year, vehicle.colour, vehicle.plate_number]
                    .filter(Boolean)
                    .join(" · ")}
                </span>
              </div>
              <div>
                <button
                  type="button"
                  onClick={() =>
                    setVehicleEditor({
                      ...vehicle,
                      plate_number: vehicle.plate_number ?? "",
                    })
                  }
                >
                  {t("common.edit")}
                </button>
                <button
                  type="button"
                  onClick={() => void removeVehicle(vehicle.id)}
                >
                  {t("common.remove")}
                </button>
              </div>
            </article>
          ))}
        </ProfileList>
        {vehicleEditor && (
          <VehicleEditor
            value={vehicleEditor}
            saving={saving}
            onChange={setVehicleEditor}
            onSave={() => void saveVehicle()}
            onCancel={() => setVehicleEditor(null)}
          />
        )}
        {!data?.profile && <p className="profile-help">{t("profile.help")}</p>}
        <section className="profile-panel danger-zone">
          <div><p className="eyebrow"><span /> {t("profile.dangerZone")}</p><h2>{t("profile.deleteAccount")}</h2><p>{t("profile.deleteAccountCopy")}</p></div>
          <button className="button button-danger" type="button" onClick={() => setDeleteOpen(true)}>{t("profile.deleteAccount")}</button>
        </section>
        {deleteOpen && <div className="modal-backdrop" onMouseDown={(event) => { if (event.currentTarget === event.target && !deleting) setDeleteOpen(false); }}>
          <section className="confirmation-dialog delete-account-dialog" role="dialog" aria-modal="true" aria-labelledby="delete-account-title">
            <h2 id="delete-account-title">{t("profile.deleteAccountTitle")}</h2>
            <p>{t("profile.deleteAccountWarning")}</p>
            <p>{t("profile.deleteAccountRetention")}</p>
            <label><span>{t("profile.typeDelete")}</span><input className="bidi-ltr" autoComplete="off" value={deleteConfirmation} onChange={(event) => setDeleteConfirmation(event.target.value)} /></label>
            <div className="profile-actions"><button className="button button-ghost" type="button" disabled={deleting} onClick={() => setDeleteOpen(false)}>{t("common.cancel")}</button><button className="button button-danger" type="button" disabled={deleting || deleteConfirmation !== "DELETE"} onClick={() => void deleteAccount()}>{deleting ? t("common.saving") : t("profile.deleteMyAccount")}</button></div>
          </section>
        </div>}
      </div>
    </main>
  );
}

function ProfileList({
  title,
  addLabel,
  disabled,
  onAdd,
  children,
}: {
  title: string;
  addLabel: string;
  disabled: boolean;
  onAdd: () => void;
  children: React.ReactNode;
}) {
  return (
    <section className="profile-panel">
      <header>
        <h2>{title}</h2>
        <button
          className="button button-small"
          disabled={disabled}
          type="button"
          onClick={onAdd}
        >
          + {addLabel}
        </button>
      </header>
      <div className="profile-list">{children}</div>
    </section>
  );
}
function VehicleEditor({
  value,
  saving,
  onChange,
  onSave,
  onCancel,
}: {
  value: SavedVehicleInput & { id?: string };
  saving: boolean;
  onChange: (value: SavedVehicleInput & { id?: string }) => void;
  onSave: () => void;
  onCancel: () => void;
}) {
  const { t } = useI18n();
  const input = (field: keyof SavedVehicleInput, label: string) => (
    <label>
      <span>{label}</span>
      <input
        value={value[field] ?? ""}
        onChange={(event) =>
          onChange({
            ...value,
            [field]:
              field === "year"
                ? event.target.value
                  ? Number(event.target.value)
                  : null
                : event.target.value || null,
          })
        }
      />
    </label>
  );
  return (
    <section className="profile-panel">
      <h2>{value.id ? t("profile.editVehicle") : t("profile.addVehicle")}</h2>
      <div className="form-grid two">
        {input("make", t("booking.vehicles.make"))}
        {input("model", t("booking.vehicles.model"))}
        {input("year", t("booking.vehicles.year"))}
        <label>
          <span>{t("booking.vehicles.type")}</span>
          <select
            value={value.vehicle_type}
            aria-invalid={!isVehicleType(value.vehicle_type)}
            onChange={(event) =>
              onChange({ ...value, vehicle_type: event.target.value })
            }
          >
            <option value="">{t("booking.vehicles.selectType")}</option>
            {value.vehicle_type && !isVehicleType(value.vehicle_type) ? (
              <option value={value.vehicle_type} disabled>
                {value.vehicle_type}
              </option>
            ) : null}
            {VEHICLE_TYPES.map((type) => (
              <option key={type} value={type}>
                {t(`booking.vehicles.type.${type}`)}
              </option>
            ))}
          </select>
        </label>
        {input("colour", t("booking.vehicles.colour"))}
        {input("plate_number", t("booking.vehicles.plateRequired"))}
      </div>
      {input("notes", t("profile.notes"))}
      <div className="profile-actions">
        <button
          className="button"
          disabled={saving}
          type="button"
          onClick={onSave}
        >
          {t("profile.saveVehicle")}
        </button>
        <button
          className="button button-ghost"
          type="button"
          onClick={onCancel}
        >
          {t("common.cancel")}
        </button>
      </div>
    </section>
  );
}
