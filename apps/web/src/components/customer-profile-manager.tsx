"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { useAuth } from "./auth-provider";
import { LocationPicker } from "./location-picker";
import { PhoneInput } from "./phone-input";
import { createCustomerAddress, createCustomerVehicle, deleteCustomerAddress, deleteCustomerVehicle, friendlyError, getCustomerProfile, updateCustomerAddress, updateCustomerProfile, updateCustomerVehicle, type SavedAddressInput, type SavedVehicleInput } from "@/lib/api";
import { normalizePhone } from "@/lib/phone";
import type { CustomerProfileBootstrap, CustomerSavedAddress, CustomerSavedVehicle, Location } from "@/lib/types";
import type { CountryCode } from "libphonenumber-js/min";

const emptyLocation: Location = { written_address: "", location_url: "", latitude: null, longitude: null, instructions: "" };
const emptyVehicle: SavedVehicleInput = { make: "", model: "", year: null, vehicle_type: "", colour: null, plate_number: null, notes: null };

export function CustomerProfileManager() {
  const { user, loading: authLoading } = useAuth();
  const router = useRouter();
  const [data, setData] = useState<CustomerProfileBootstrap | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [saving, setSaving] = useState(false);
  const [personal, setPersonal] = useState<{ first_name: string; surname: string; phone: string; phone_country: CountryCode }>({ first_name: "", surname: "", phone: "", phone_country: "AE" });
  const [addressEditor, setAddressEditor] = useState<{ id?: string; label: string; is_default: boolean; location: Location } | null>(null);
  const [vehicleEditor, setVehicleEditor] = useState<(SavedVehicleInput & { id?: string }) | null>(null);

  useEffect(() => { if (!authLoading && !user) router.replace("/login?returnTo=%2Faccount%2Fprofile"); }, [authLoading, router, user]);
  const load = useCallback(async () => {
    if (!user) return;
    setError("");
    try {
      const next = await getCustomerProfile();
      setData(next);
      setPersonal({ first_name: next.profile?.first_name ?? String(user.user_metadata.first_name ?? ""), surname: next.profile?.surname ?? String(user.user_metadata.surname ?? ""), phone: next.profile?.phone ?? "", phone_country: "AE" });
    } catch (reason) { setError(friendlyError(reason)); }
  }, [user]);
  useEffect(() => { const timer = window.setTimeout(() => void load(), 0); return () => window.clearTimeout(timer); }, [load]);

  async function savePersonal() {
    const phone = normalizePhone(personal.phone, personal.phone_country);
    if (!phone) { setError("Enter a valid international phone number."); return; }
    setSaving(true); setError(""); setNotice("");
    try { const next = await updateCustomerProfile({ first_name: personal.first_name, surname: personal.surname, phone }); setData(next); setPersonal((value) => ({ ...value, phone })); setNotice("Changes saved."); }
    catch (reason) { setError(friendlyError(reason)); } finally { setSaving(false); }
  }

  function editAddress(address?: CustomerSavedAddress) {
    setAddressEditor(address ? { id: address.id, label: address.label, is_default: address.is_default, location: { written_address: address.written_address, location_url: address.location_url, latitude: address.latitude, longitude: address.longitude, instructions: address.location_instructions ?? "" } } : { label: "Home", is_default: !data?.addresses.length, location: emptyLocation });
  }
  async function saveAddress() {
    if (!addressEditor) return;
    const input: SavedAddressInput = { label: addressEditor.label, is_default: addressEditor.is_default, ...addressEditor.location };
    setSaving(true); setError("");
    try { addressEditor.id ? await updateCustomerAddress(addressEditor.id, input) : await createCustomerAddress(input); setAddressEditor(null); setNotice("Location saved."); await load(); }
    catch (reason) { setError(friendlyError(reason)); } finally { setSaving(false); }
  }
  async function removeAddress(id: string) { setSaving(true); try { await deleteCustomerAddress(id); setNotice("Location removed."); await load(); } catch (reason) { setError(friendlyError(reason)); } finally { setSaving(false); } }

  async function saveVehicle() {
    if (!vehicleEditor) return;
    setSaving(true); setError("");
    try { const { id, ...input } = vehicleEditor; id ? await updateCustomerVehicle(id, input) : await createCustomerVehicle(input); setVehicleEditor(null); setNotice(id ? "Vehicle updated." : "Vehicle added."); await load(); }
    catch (reason) { setError(friendlyError(reason)); } finally { setSaving(false); }
  }
  async function removeVehicle(id: string) { setSaving(true); try { await deleteCustomerVehicle(id); setNotice("Vehicle removed."); await load(); } catch (reason) { setError(friendlyError(reason)); } finally { setSaving(false); } }

  if (authLoading || (user && !data && !error)) return <main className="account-page"><div className="shell account-shell"><div className="loading-panel"><span className="spinner dark" /><strong>Loading your profile</strong></div></div></main>;
  if (!user) return null;
  return <main className="account-page"><div className="shell account-shell">
    <div className="account-heading"><div><p className="eyebrow"><span /> Account</p><h1>Profile</h1><p>Keep the details you reuse for future bookings.</p></div><Link className="button button-ghost" href="/account">Bookings</Link></div>
    {error && <div className="error-banner" role="alert">{error} {!data && <button type="button" onClick={() => void load()}>Try again</button>}</div>}{notice && <div className="inline-notice" role="status"><strong>{notice}</strong></div>}
    <section className="profile-panel"><h2>Personal information</h2><div className="form-grid two"><label><span>First name</span><input value={personal.first_name} onChange={(event) => setPersonal({ ...personal, first_name: event.target.value })} /></label><label><span>Surname</span><input value={personal.surname} onChange={(event) => setPersonal({ ...personal, surname: event.target.value })} /></label><label><span>Email address</span><input value={data?.authenticated_email ?? user.email ?? ""} readOnly aria-readonly="true" /><small>Change this through your secure login identity.</small></label><PhoneInput value={personal.phone} country={personal.phone_country} onChange={(phone) => setPersonal({ ...personal, phone })} onCountryChange={(phone_country) => setPersonal({ ...personal, phone_country })} /></div><button className="button" disabled={saving} onClick={() => void savePersonal()} type="button">Save personal information</button></section>
    <ProfileList title="Saved locations" addLabel="Add location" disabled={!data?.profile} onAdd={() => editAddress()}>{data?.addresses.map((address) => <article className="profile-item" key={address.id}><div><strong>{address.label}{address.is_default ? " · Default" : ""}</strong><span>{address.written_address}</span></div><div><button type="button" onClick={() => editAddress(address)}>Edit</button><button type="button" onClick={() => void removeAddress(address.id)}>Remove</button></div></article>)}</ProfileList>
    {addressEditor && <section className="profile-panel"><h2>{addressEditor.id ? "Edit location" : "Add location"}</h2><div className="form-grid two"><label><span>Label</span><input value={addressEditor.label} onChange={(event) => setAddressEditor({ ...addressEditor, label: event.target.value })} /></label><label className="checkbox-row"><input type="checkbox" checked={addressEditor.is_default} onChange={(event) => setAddressEditor({ ...addressEditor, is_default: event.target.checked })} /> Default location</label></div><LocationPicker location={addressEditor.location} errors={{}} onFieldChange={(field, value) => setAddressEditor({ ...addressEditor, location: { ...addressEditor.location, [field]: value, ...(field === "location_url" ? { latitude: null, longitude: null } : {}) } })} onCoordinatesChange={(value, writtenAddress) => setAddressEditor({ ...addressEditor, location: { ...addressEditor.location, ...value, written_address: writtenAddress || addressEditor.location.written_address, location_url: `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(`${value.latitude},${value.longitude}`)}` } })} /><div className="profile-actions"><button className="button" disabled={saving} type="button" onClick={() => void saveAddress()}>Save location</button><button className="button button-ghost" type="button" onClick={() => setAddressEditor(null)}>Cancel</button></div></section>}
    <ProfileList title="Saved vehicles" addLabel="Add vehicle" disabled={!data?.profile} onAdd={() => setVehicleEditor({ ...emptyVehicle })}>{data?.vehicles.map((vehicle) => <article className="profile-item" key={vehicle.id}><div><strong>{vehicle.make} {vehicle.model}</strong><span>{[vehicle.year, vehicle.colour, vehicle.plate_number].filter(Boolean).join(" · ")}</span></div><div><button type="button" onClick={() => setVehicleEditor({ ...vehicle })}>Edit</button><button type="button" onClick={() => void removeVehicle(vehicle.id)}>Remove</button></div></article>)}</ProfileList>
    {vehicleEditor && <VehicleEditor value={vehicleEditor} saving={saving} onChange={setVehicleEditor} onSave={() => void saveVehicle()} onCancel={() => setVehicleEditor(null)} />}
    {!data?.profile && <p className="profile-help">Save personal information first to add locations and vehicles.</p>}
  </div></main>;
}

function ProfileList({ title, addLabel, disabled, onAdd, children }: { title: string; addLabel: string; disabled: boolean; onAdd: () => void; children: React.ReactNode }) { return <section className="profile-panel"><header><h2>{title}</h2><button className="button button-small" disabled={disabled} type="button" onClick={onAdd}>+ {addLabel}</button></header><div className="profile-list">{children}</div></section>; }
function VehicleEditor({ value, saving, onChange, onSave, onCancel }: { value: SavedVehicleInput & { id?: string }; saving: boolean; onChange: (value: SavedVehicleInput & { id?: string }) => void; onSave: () => void; onCancel: () => void }) { const input = (field: keyof SavedVehicleInput, label: string) => <label><span>{label}</span><input value={value[field] ?? ""} onChange={(event) => onChange({ ...value, [field]: field === "year" ? (event.target.value ? Number(event.target.value) : null) : event.target.value || null })} /></label>; return <section className="profile-panel"><h2>{value.id ? "Edit vehicle" : "Add vehicle"}</h2><div className="form-grid two">{input("make", "Make")}{input("model", "Model")}{input("year", "Year")}{input("vehicle_type", "Vehicle type")}{input("colour", "Colour")}{input("plate_number", "Plate number")}</div>{input("notes", "Notes")}<div className="profile-actions"><button className="button" disabled={saving} type="button" onClick={onSave}>Save vehicle</button><button className="button button-ghost" type="button" onClick={onCancel}>Cancel</button></div></section>; }
