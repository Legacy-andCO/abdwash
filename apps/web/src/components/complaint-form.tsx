"use client";

import Link from "next/link";
import { useRef, useState, type FormEvent } from "react";
import { ApiError, createComplaint } from "@/lib/api";
import { normalizePhone } from "@/lib/phone";
import { POLICY_REVISION, policyTitles } from "@/lib/policies";
import { useI18n } from "./i18n-provider";

const imageTypes = ["image/jpeg", "image/png", "image/webp"];
const uploadLimit = 1024 * 1024;
const sourceLimit = 15 * uploadLimit;
const categories = {
  service: { en: "Service quality or incomplete work", ar: "جودة الخدمة أو عدم اكتمالها" },
  damage: { en: "Vehicle damage", ar: "ضرر بالمركبة" },
  belongings: { en: "Missing belongings", ar: "فقد المقتنيات" },
  booking: { en: "Booking or scheduling", ar: "الحجز أو المواعيد" },
  payment: { en: "Price, payment or refund", ar: "السعر أو الدفع أو الاسترداد" },
  conduct: { en: "Staff conduct", ar: "سلوك الموظفين" },
  privacy: { en: "Privacy", ar: "الخصوصية" },
  other: { en: "Other", ar: "أخرى" },
};

const copy = {
  en: {
    heading: "Submit a complaint",
    name: "Full name",
    email: "Email",
    phone: "Telephone",
    contact: "Provide at least one contact method. Include the country code for international numbers.",
    missingContact: "Enter an email address or telephone number.",
    invalidPhone: "Enter a valid telephone number.",
    booking: "Booking reference (optional)",
    date: "Service date (optional)",
    category: "Complaint category",
    choose: "Choose a category",
    description: "Describe what happened",
    evidence: "Photos (optional)",
    evidenceHelp: "Attach up to two JPEG, PNG or WebP images. Images up to 15 MB can be resized on your device to fit the 1 MB upload limit.",
    evidenceResize: "This photo could not be resized. Try a smaller JPEG, PNG or WebP image.",
    sensitive: "Leave out identity documents, card numbers and other sensitive details unrelated to your complaint.",
    acknowledge: "I acknowledge the",
    submit: "Submit complaint",
    busy: "Submitting…",
    received: "Your complaint was saved. Keep this reference for follow-up.",
    invalid: "Check the form fields and try again.",
    limited: "Too many submissions. Please try again later or contact Trifecta directly.",
    revision: "The privacy notice has changed. Reload this page and review it again.",
    failure: "We could not confirm receipt. Please try again or contact Trifecta directly.",
  },
  ar: {
    heading: "تقديم شكوى",
    name: "الاسم الكامل",
    email: "البريد الإلكتروني",
    phone: "رقم الهاتف",
    contact: "أدخل وسيلة تواصل واحدة على الأقل. أضف رمز الدولة للأرقام الدولية.",
    missingContact: "أدخل عنوان بريد إلكتروني أو رقم هاتف.",
    invalidPhone: "أدخل رقم هاتف صالحاً.",
    booking: "مرجع الحجز (اختياري)",
    date: "تاريخ الخدمة (اختياري)",
    category: "فئة الشكوى",
    choose: "اختر فئة",
    description: "اشرح ما حدث",
    evidence: "صور (اختياري)",
    evidenceHelp: "أرفق صورتين على الأكثر بصيغة JPEG أو PNG أو WebP. يمكن تصغير الصور التي لا تتجاوز 15 ميغابايت على جهازك لتناسب حد الرفع البالغ 1 ميغابايت.",
    evidenceResize: "تعذّر تصغير هذه الصورة. جرّب صورة أصغر بصيغة JPEG أو PNG أو WebP.",
    sensitive: "يرجى تجنب إرفاق وثائق الهوية أو أرقام البطاقات أو تفاصيل حساسة لا تتعلق بالشكوى.",
    acknowledge: "أقرّ بالاطلاع على",
    submit: "إرسال الشكوى",
    busy: "جارٍ الإرسال…",
    received: "حُفظت شكواك. احتفظ بهذا المرجع للمتابعة.",
    invalid: "تحقق من الحقول وحاول مجدداً.",
    limited: "تم تجاوز عدد المحاولات. حاول لاحقاً أو تواصل مباشرةً مع تريفيكتا.",
    revision: "تم تحديث إشعار الخصوصية. أعد تحميل الصفحة وراجعه من جديد.",
    failure: "تعذر تأكيد الاستلام. حاول مجدداً أو تواصل مباشرةً مع تريفيكتا.",
  },
};

async function resizePhoto(file: File): Promise<Blob> {
  if (file.size <= uploadLimit) return file;
  const image = await createImageBitmap(file);
  try {
    if (image.width * image.height > 64_000_000) throw new Error("Image dimensions exceed limit");
    const canvas = document.createElement("canvas");
    const context = canvas.getContext("2d", { alpha: false });
    if (!context) throw new Error("Image conversion unavailable");
    for (const edge of [1920, 1280, 800]) {
      const scale = Math.min(1, edge / Math.max(image.width, image.height));
      canvas.width = Math.max(1, Math.round(image.width * scale));
      canvas.height = Math.max(1, Math.round(image.height * scale));
      context.fillStyle = "#fff";
      context.fillRect(0, 0, canvas.width, canvas.height);
      context.drawImage(image, 0, 0, canvas.width, canvas.height);
      const resized = await new Promise<Blob | null>((resolve) =>
        canvas.toBlob(resolve, "image/jpeg", 0.82));
      if (resized && resized.size <= uploadLimit && resized.type === "image/jpeg") return resized;
    }
    throw new Error("Image could not fit the upload limit");
  } finally {
    image.close();
  }
}

async function encodePhoto(file: File): Promise<{ content_type: string; data: string }> {
  const photo = await resizePhoto(file);
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = reject;
    reader.onload = () => {
      const data = String(reader.result).split(",", 2)[1];
      if (data) resolve({ content_type: photo.type, data });
      else reject(new Error("Image could not be read"));
    };
    reader.readAsDataURL(photo);
  });
}

export function ComplaintForm() {
  const { language } = useI18n();
  const labels = copy[language];
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [reference, setReference] = useState("");
  const lastSubmission = useRef<{ fingerprint: string; language: typeof language; key: string } | null>(null);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    const form = new FormData(event.currentTarget);
    const field = (name: string) => String(form.get(name) ?? "").trim();
    const email = field("email");
    const enteredPhone = field("phone");
    const phone = enteredPhone ? normalizePhone(enteredPhone, "AE") : null;
    if (!email && !enteredPhone) {
      setError(labels.missingContact);
      return;
    }
    if (enteredPhone && !phone) {
      setError(labels.invalidPhone);
      return;
    }
    const files = form.getAll("evidence").filter((file): file is File => file instanceof File && file.size > 0);
    if (files.length > 2 || files.some((file) => file.size > sourceLimit || !imageTypes.includes(file.type))) {
      setError(labels.evidenceHelp);
      return;
    }
    setError("");
    setBusy(true);
    try {
      const evidence = [];
      try {
        for (const file of files) evidence.push(await encodePhoto(file));
      } catch {
        setError(labels.evidenceResize);
        return;
      }
      const payload = {
        name: field("name"),
        email: email || null,
        phone,
        booking_reference: field("booking_reference") || null,
        service_date: field("service_date") || null,
        category: field("category"),
        description: field("description"),
        privacy_acknowledged: form.get("privacy") === "on",
        revision: POLICY_REVISION,
        website: field("website"),
        evidence,
      };
      const fingerprint = JSON.stringify(payload);
      if (lastSubmission.current?.fingerprint !== fingerprint) {
        lastSubmission.current = { fingerprint, language, key: crypto.randomUUID() };
      }
      const receipt = await createComplaint(
        JSON.stringify({ ...payload, language: lastSubmission.current.language }),
        lastSubmission.current.key,
      );
      setReference(receipt.reference);
      lastSubmission.current = null;
    } catch (reason) {
      const code = reason instanceof ApiError ? reason.code : null;
      if (code === "COMPLAINT_RATE_LIMIT") setError(labels.limited);
      else if (code === "POLICY_VERSION_CHANGED") setError(labels.revision);
      else if (code === "COMPLAINT_EVIDENCE_INVALID" || code === "COMPLAINT_TOO_LARGE") {
        setError(labels.evidenceHelp);
      } else if (code === "COMPLAINT_INVALID") setError(labels.invalid);
      else setError(labels.failure);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section id="complaint-form" aria-labelledby="complaint-heading">
      <h2 id="complaint-heading">{labels.heading}</h2>
      {reference ? (
        <div className="inline-notice" role="status">
          <span>{labels.received}</span>
          <strong dir="ltr">{reference}</strong>
        </div>
      ) : (
        <form className="complaint-form" onSubmit={submit}>
          <fieldset disabled={busy}>
            <label>{labels.name}<input name="name" autoComplete="name" required maxLength={120} /></label>
            <p id="complaint-contact-hint">{labels.contact}</p>
            <div className="complaint-fields">
              <label>{labels.email}<input name="email" type="email" autoComplete="email" maxLength={254} dir="ltr" aria-describedby="complaint-contact-hint" /></label>
              <label>{labels.phone}<input name="phone" type="tel" autoComplete="tel" maxLength={40} dir="ltr" aria-describedby="complaint-contact-hint" /></label>
              <label>{labels.booking}<input name="booking_reference" maxLength={64} dir="auto" /></label>
              <label>{labels.date}<input name="service_date" type="date" /></label>
            </div>
            <label>
              {labels.category}
              <select name="category" required defaultValue="">
                <option value="" disabled>{labels.choose}</option>
                {Object.entries(categories).map(([value, label]) => (
                  <option key={value} value={value}>{label[language]}</option>
                ))}
              </select>
            </label>
            <label>
              {labels.description}
              <textarea name="description" rows={5} required minLength={10} maxLength={4000} aria-describedby="complaint-sensitive" dir="auto" />
            </label>
            <p id="complaint-sensitive">{labels.sensitive}</p>
            <label>
              {labels.evidence}
              <input name="evidence" type="file" multiple accept={imageTypes.join(",")} aria-describedby="complaint-evidence-hint" />
            </label>
            <p id="complaint-evidence-hint">{labels.evidenceHelp}</p>
            <div hidden><input name="website" autoComplete="off" tabIndex={-1} /></div>
            <div className="policy-checkbox">
              <input id="complaint-privacy" name="privacy" type="checkbox" required aria-labelledby="complaint-privacy-text" />
              <span id="complaint-privacy-text">
                <label htmlFor="complaint-privacy">{labels.acknowledge}</label>{" "}
                <Link href="/privacy-policy" target="_blank" rel="noopener">{policyTitles["privacy-policy"][language]}</Link>.
              </span>
            </div>
            {error && <p role="alert" className="error-banner">{error}</p>}
            <button className="button" type="submit">{busy ? labels.busy : labels.submit}</button>
          </fieldset>
        </form>
      )}
    </section>
  );
}
