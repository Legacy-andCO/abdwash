import { t } from "../i18n";
import { Alert } from "../alert";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  Platform,
  Image,
  Linking,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { useNetInfo } from "@react-native-community/netinfo";
import * as ImagePicker from "expo-image-picker";
import { CryptoDigestAlgorithm, digest } from "expo-crypto";
import { ImageManipulator, SaveFormat } from "expo-image-manipulator";
import { capabilities } from "../capabilities";
import { DatePickerField } from "./pickers";
import {
  AppButton,
  Card,
  EmptyState,
  Skeleton,
  StatusChip,
  uiStyles,
} from "./ui";
import { domainErrorMessage } from "../errors/domainErrors";
import type {
  Job,
  JobComplaint,
  JobPhoto,
  JobQuality,
  StaffContext,
} from "../lib";
import {
  useAvailabilityQuery,
  useChecklistMutation,
  useComplaintMutation,
  useComplaintReviewMutation,
  useInspectionMutation,
  usePhotoUploadMutation,
  useQualityIssueMutation,
} from "../queries/operations";
import {
  availablePhotoCategories,
  qualitySummary,
  qualityWritesDisabled,
  toggledChecklist,
} from "../quality/qualityState";
import { colors, radii, spacing } from "../theme";
import { formatUaeDateTime, formatUaeTime, uaeDateKey, wallDate } from "../time/uaeTime";

type PhotoDraft = {
  uri: string;
  category: JobPhoto["category"];
  clientRequestId: string;
  failure?: { reason: unknown };
};

const MAX_PHOTO_QUEUE = 8;
const MAX_JOB_PHOTOS = 48;
const MAX_PREPARED_BYTES = 8 * 1024 * 1024;
const PHOTO_TYPES = new Set([
  "image/jpeg", "image/png", "image/webp", "image/heic", "image/heif", "image/avif",
]);

function photoCategoryLabel(category: JobPhoto["category"]) {
  return t({
    before: "Before service",
    after: "After service",
    damage: "Damage",
    issue: "Issue",
  }[category]);
}

async function preparePhoto(asset: ImagePicker.ImagePickerAsset) {
  const mimeType = asset.mimeType || asset.file?.type;
  if (
    (mimeType && !PHOTO_TYPES.has(mimeType)) ||
    (asset.fileSize ?? asset.file?.size ?? 0) > 30 * 1024 * 1024 ||
    asset.width * asset.height > 60_000_000
  ) {
    throw new Error("Invalid source image");
  }
  const manipulator = ImageManipulator.manipulate(asset.uri);
  if (Math.max(asset.width, asset.height) > 1600) {
    manipulator.resize(asset.height > asset.width ? { height: 1600 } : { width: 1600 });
  }
  const rendered = await manipulator.renderAsync();
  const prepared = await rendered.saveAsync({ compress: 0.75, format: SaveFormat.JPEG });
  const response = await fetch(prepared.uri);
  const bytes = await response.arrayBuffer();
  if (!bytes.byteLength || bytes.byteLength > MAX_PREPARED_BYTES) {
    throw new Error("Invalid prepared image size");
  }
  const hash = await digest(CryptoDigestAlgorithm.SHA256, bytes);
  return {
    uri: prepared.uri,
    hash: Array.from(new Uint8Array(hash), (byte) => byte.toString(16).padStart(2, "0")).join(""),
  };
}

export function JobQualityControls({
  context,
  job,
  quality,
  pending,
  error,
  onRetry,
}: {
  context: StaffContext;
  job: Job;
  quality?: JobQuality;
  pending: boolean;
  error: unknown;
  onRetry: () => void;
}) {
  const netInfo = useNetInfo();
  const offline = qualityWritesDisabled(netInfo.isConnected);
  const inspection = useInspectionMutation(context, job.id);
  const checklist = useChecklistMutation(context, job.id);
  const issue = useQualityIssueMutation(context, job.id);
  const photo = usePhotoUploadMutation(context, job.id);
  const complaint = useComplaintMutation(context, job.id);
  const [condition, setCondition] = useState("");
  const [damageCategory, setDamageCategory] = useState("");
  const [damageNotes, setDamageNotes] = useState("");
  const [photoCategory, setPhotoCategory] =
    useState<JobPhoto["category"]>("before");
  const [drafts, setDrafts] = useState<PhotoDraft[]>([]);
  const [photoPicking, setPhotoPicking] = useState(false);
  const [uploadProgress, setUploadProgress] = useState<{ current: number; total: number } | null>(null);
  const [uploadedPhotos, setUploadedPhotos] = useState(0);
  const [pickNotice, setPickNotice] = useState("");
  const photoBusy = useRef(false);
  const [issueOpen, setIssueOpen] = useState(false);
  const [issueCategory, setIssueCategory] = useState("other");
  const [issueNote, setIssueNote] = useState("");
  const [issuePhotoId, setIssuePhotoId] = useState<string | null>(null);
  const [complaintText, setComplaintText] = useState("");
  const [rewash, setRewash] = useState<JobComplaint | null>(null);
  const loadedInspectionId = useRef<string | null>(null);
  useEffect(() => {
    if (!quality?.inspection) return;
    if (loadedInspectionId.current === quality.inspection.id) return;
    loadedInspectionId.current = quality.inspection.id;
    setCondition(quality.inspection.condition_notes ?? "");
    setDamageCategory(quality.inspection.damage_category ?? "");
    setDamageNotes(quality.inspection.damage_notes ?? "");
  }, [quality?.inspection]);
  const categories = useMemo(
    () => availablePhotoCategories(job.status),
    [job.status],
  );
  useEffect(() => {
    if (categories.length && !categories.includes(photoCategory))
      setPhotoCategory(categories[0]);
  }, [categories, photoCategory]);
  const queueLimit = Math.min(MAX_PHOTO_QUEUE, MAX_JOB_PHOTOS - (quality?.photos.length ?? 0));
  const photoWorking = photoPicking || uploadProgress !== null;

  async function choosePhoto(source: "camera" | "library") {
    const slots = queueLimit - drafts.length;
    if (photoBusy.current || slots <= 0) return;
    setPickNotice("");
    setUploadedPhotos(0);
    // On web, the picker must open on the tap, and some browsers omit cancellation.
    let ownsPicker = Platform.OS !== "web";
    if (ownsPicker) {
      photoBusy.current = true;
      setPhotoPicking(true);
    }
    try {
      if (source === "camera" && Platform.OS !== "web") {
        const permission = await ImagePicker.requestCameraPermissionsAsync();
        if (!permission.granted) {
          setPickNotice("Allow camera access to capture job evidence.");
          return;
        }
      }
      const options: ImagePicker.ImagePickerOptions = { mediaTypes: ["images"], quality: 1 };
      const result = source === "camera"
        ? await ImagePicker.launchCameraAsync(options)
        : await ImagePicker.launchImageLibraryAsync({
          ...options, allowsMultipleSelection: true, selectionLimit: slots,
        });
      if (result.canceled || (Platform.OS === "web" && photoBusy.current)) return;
      ownsPicker = true;
      photoBusy.current = true;
      setPhotoPicking(true);
      const selected: PhotoDraft[] = [];
      const queued = new Set(drafts.map((item) => item.clientRequestId));
      let rejected = 0;
      let duplicates = 0;
      for (const asset of result.assets.slice(0, MAX_PHOTO_QUEUE)) {
        if (selected.length === slots) break;
        try {
          const { uri, hash } = await preparePhoto(asset);
          const clientRequestId = `photo:${job.id}:${context.staff_id}:${photoCategory}:${hash}`;
          if (queued.has(clientRequestId)) {
            duplicates += 1;
            continue;
          }
          queued.add(clientRequestId);
          selected.push({ uri, category: photoCategory, clientRequestId });
        } catch {
          rejected += 1;
        }
      }
      setDrafts((previous) => [...previous, ...selected.filter(
        (item) => !previous.some((draft) => draft.clientRequestId === item.clientRequestId),
      )].slice(0, queueLimit));
      if (rejected) setPickNotice("Some images could not be added. Choose a supported image under 30 MB.");
      else if (duplicates) setPickNotice("Duplicate photos were skipped.");
      else if (result.assets.length > slots) setPickNotice("The photo queue is full. Upload or remove photos to add more.");
    } catch {
      setPickNotice("Could not open photos. Check permissions and try again.");
    } finally {
      if (ownsPicker) {
        photoBusy.current = false;
        setPhotoPicking(false);
      }
    }
  }

  async function uploadDrafts() {
    if (photoBusy.current || !drafts.length) return;
    photoBusy.current = true;
    setUploadedPhotos(0);
    setPickNotice("");
    let uploaded = 0;
    for (const [index, draft] of drafts.entries()) {
      setUploadProgress({ current: index + 1, total: drafts.length });
      try {
        await photo.mutateAsync(draft);
        setDrafts((items) => items.filter((item) => item.clientRequestId !== draft.clientRequestId));
        uploaded += 1;
      } catch (reason) {
        setDrafts((items) => items.map((item) => item.clientRequestId === draft.clientRequestId
          ? { ...item, failure: { reason } }
          : item));
      }
    }
    photoBusy.current = false;
    setUploadProgress(null);
    setUploadedPhotos(uploaded);
  }

  async function saveInspection() {
    try {
      await inspection.mutateAsync({
        condition_notes: condition.trim() || null,
        damage_category: damageCategory || null,
        damage_notes: damageNotes.trim() || null,
      });
    } catch (reason) {
      Alert.alert(
        t("Inspection not saved"),
        domainErrorMessage(reason, "Try again."),
      );
    }
  }

  async function saveIssue() {
    try {
      await issue.mutateAsync({
        category: issueCategory,
        note: issueNote.trim(),
        photo_id: issuePhotoId,
      });
      setIssueNote("");
      setIssuePhotoId(null);
      setIssueOpen(false);
    } catch (reason) {
      Alert.alert(t("Issue not saved"), domainErrorMessage(reason, "Try again."));
    }
  }

  async function addComplaint() {
    try {
      await complaint.mutateAsync(complaintText.trim());
      setComplaintText("");
    } catch (reason) {
      Alert.alert(
        t("Complaint not saved"),
        domainErrorMessage(reason, "Try again."),
      );
    }
  }

  if (pending && !quality)
    return (
      <Card>
        <Skeleton rows={4} />
      </Card>
    );
  if (!quality)
    return (
      <Card>
        <EmptyState
          title={t("Vehicle condition record couldn't be loaded")}
          body={domainErrorMessage(
            error,
            "We couldn't load this job's quality record.",
          )}
        />
        <AppButton title={t("Try again")} tone="secondary" onPress={onRetry} />
      </Card>
    );
  const summary = qualitySummary(quality);
  const canWork = ["arrived", "in_progress"].includes(job.status);
  const canManage = capabilities(context.role).canManageAnyJob;
  return (
    <Card>
      <Text style={styles.section}>{t("JOB QUALITY")}</Text>
      {error ? (
        <View style={styles.block}>
          <Text style={uiStyles.error}>
            {" " + t("Vehicle condition record couldn't be refreshed. The last saved details remain visible.") + " "}</Text>
          <AppButton title={t("Try again")} tone="secondary" onPress={onRetry} />
        </View>
      ) : null}
      {offline ? (
        <Text style={uiStyles.error}>
          {" " + t("Offline · saved quality evidence is visible, but changes and uploads require a connection.") + " "}</Text>
      ) : null}
      {canWork ? (
        <View style={styles.block}>
          <Text style={styles.title}>{t("Vehicle inspection")}</Text>
          <TextInput
            accessibilityLabel={t("Vehicle condition notes")}
            editable={!offline}
            multiline
            placeholder={t("Overall condition notes")}
            style={[uiStyles.field, styles.multiline]}
            value={condition}
            onChangeText={setCondition}
          />
          <Text style={uiStyles.label}>{t("EXISTING DAMAGE")}</Text>
          <View style={styles.choices}>
            {[
              "",
              "scratch",
              "dent",
              "paint_damage",
              "wheel_damage",
              "glass_damage",
              "interior_damage",
              "stain",
              "other",
            ].map((value) => (
              <Pressable
                key={value || "none"}
                disabled={offline}
                style={[
                  styles.choice,
                  damageCategory === value ? styles.selected : undefined,
                ]}
                onPress={() => setDamageCategory(value)}
              >
                <Text style={styles.choiceText}>
                  {value ? t(value.replaceAll("_", " ")) : t("None")}
                </Text>
              </Pressable>
            ))}
          </View>
          {damageCategory ? (
            <TextInput
              accessibilityLabel={t("Existing damage notes")}
              editable={!offline}
              multiline
              placeholder={t("Where is the damage?")}
              style={[uiStyles.field, styles.multiline]}
              value={damageNotes}
              onChangeText={setDamageNotes}
            />
          ) : null}
          <AppButton
            title={
              inspection.isPending
                ? t("Saving…")
                : quality.inspection
                  ? t("Update inspection")
                  : t("Complete inspection")
            }
            disabled={offline || inspection.isPending}
            loading={inspection.isPending}
            onPress={() => void saveInspection()}
          />
        </View>
      ) : quality.inspection ? (
        <View style={styles.block}>
          <Text style={styles.title}>{t("Inspection")}</Text>
          <Text style={uiStyles.muted}>
            {quality.inspection.completed_by_staff_name} ·{" "}
            {formatUaeDateTime(quality.inspection.completed_at)}
          </Text>
          {quality.inspection.condition_notes ? (
            <Text style={uiStyles.body}>
              {quality.inspection.condition_notes}
            </Text>
          ) : null}
          {quality.inspection.damage_category ? (
            <Text style={uiStyles.body}>
              {t(quality.inspection.damage_category.replaceAll("_", " "))} ·{" "}
              {quality.inspection.damage_notes || t("No additional note")}
            </Text>
          ) : null}
        </View>
      ) : (
        <Text style={uiStyles.muted}>
          {" " + t("No inspection was recorded for this job.") + " "}</Text>
      )}

      {categories.length || drafts.length || uploadedPhotos ? (
        <View style={styles.block}>
          <Text style={styles.title}>{t("Photo evidence")}</Text>
          <View style={styles.choices}>
            {categories.map((category) => (
              <Pressable
                key={category}
                accessibilityRole="button"
                accessibilityState={{ selected: photoCategory === category }}
                disabled={photoWorking}
                style={[
                  styles.choice,
                  photoCategory === category ? styles.selected : undefined,
                ]}
                onPress={() => setPhotoCategory(category)}
              >
                <Text style={styles.choiceText}>{photoCategoryLabel(category)}</Text>
              </Pressable>
            ))}
          </View>
          {categories.length ? (
            <View style={styles.actions}>
              <View style={styles.flex}>
                <AppButton
                  title={t("Take photo")}
                  disabled={offline || photoWorking || drafts.length >= queueLimit}
                  onPress={() => void choosePhoto("camera")}
                />
              </View>
              <View style={styles.flex}>
                <AppButton
                  title={t("Choose photos")}
                  tone="secondary"
                  disabled={offline || photoWorking || drafts.length >= queueLimit}
                  onPress={() => void choosePhoto("library")}
                />
              </View>
            </View>
          ) : null}
          {photoPicking ? <Text accessibilityLiveRegion="polite" style={uiStyles.muted}>{t("Preparing photos…")}</Text> : null}
          {pickNotice ? <Text accessibilityLiveRegion="polite" style={uiStyles.body}>{t(pickNotice)}</Text> : null}
          {queueLimit <= 0 && categories.length ? (
            <Text style={uiStyles.muted}>{t("This job has reached its photo limit.")}</Text>
          ) : null}
          {drafts.length ? (
            <>
              <Text style={uiStyles.label}>{t("{count} photos to upload", { count: drafts.length })}</Text>
              {drafts.map((draft, index) => (
                <View key={draft.clientRequestId} style={styles.preview}>
                  <Image source={{ uri: draft.uri }} style={styles.thumb} resizeMode="cover"
                    accessibilityLabel={t("Selected photo {number}", { number: index + 1 })} />
                  <View style={styles.flex}>
                    <Text style={uiStyles.body}>{photoCategoryLabel(draft.category)}</Text>
                    {draft.failure ? (
                      <Text accessibilityLiveRegion="polite" style={uiStyles.error}>
                        {domainErrorMessage(draft.failure.reason, "Photo could not be uploaded. Try again.")}
                      </Text>
                    ) : null}
                    <Pressable accessibilityRole="button"
                      accessibilityLabel={t("Remove selected photo {number}", { number: index + 1 })}
                      disabled={photoWorking} style={styles.removePhoto}
                      onPress={() => setDrafts((items) => items.filter((item) => item.clientRequestId !== draft.clientRequestId))}>
                      <Text style={uiStyles.link}>{t("Remove")}</Text>
                    </Pressable>
                  </View>
                </View>
              ))}
              <AppButton
                title={uploadProgress !== null
                  ? t("Uploading photo {current} of {total}", uploadProgress)
                  : drafts.some((draft) => draft.failure) ? t("Retry remaining photos") : t("Upload photos")}
                disabled={offline || photoWorking || !categories.length}
                loading={uploadProgress !== null}
                onPress={() => void uploadDrafts()}
              />
            </>
          ) : null}
          {uploadedPhotos ? (
            <Text accessibilityLiveRegion="polite" style={uiStyles.body}>
              {t("{count} photos uploaded", { count: uploadedPhotos })}
            </Text>
          ) : null}
        </View>
      ) : null}

      <PhotoStrip photos={quality.photos} />

      {quality.checklist.length ? (
        <View style={styles.block}>
          <Text style={styles.title}>
            {" " + t("Service checklist ·") + " "}{summary.checklist}
          </Text>
          {quality.checklist.map((item) => (
            <Pressable
              accessibilityRole="checkbox"
              accessibilityState={{ checked: item.completed_at !== null }}
              disabled={
                offline || job.status !== "in_progress" || checklist.isPending
              }
              key={item.id}
              style={styles.checkRow}
              onPress={() =>
                void checklist
                  .mutateAsync(toggledChecklist(quality.checklist, item.id))
                  .catch((reason) =>
                    Alert.alert(
                      t("Checklist not saved"),
                      domainErrorMessage(reason, "Try again."),
                    ),
                  )
              }
            >
              <Text
                style={item.completed_at ? styles.checkDone : styles.checkEmpty}
              >
                {item.completed_at ? "✓" : "○"}
              </Text>
              <Text style={styles.checkLabel}>
                {item.label}
                {item.is_required ? "" : t(" · optional")}
              </Text>
            </Pressable>
          ))}
        </View>
      ) : (
        <Text style={uiStyles.muted}>
          {" " + t("No checklist was configured for this historical job.") + " "}</Text>
      )}

      {canWork ? (
        <View style={styles.block}>
          {!issueOpen ? (
            <AppButton
              title={t("Add issue")}
              tone="secondary"
              disabled={offline}
              onPress={() => setIssueOpen(true)}
            />
          ) : (
            <>
              <Text style={styles.title}>{t("Report an issue")}</Text>
              <View style={styles.choices}>
                {[
                  "pre_existing_damage",
                  "incomplete_result",
                  "paint_damage",
                  "access_problem",
                  "customer_request",
                  "other",
                ].map((value) => (
                  <Pressable
                    key={value}
                    style={[
                      styles.choice,
                      issueCategory === value ? styles.selected : undefined,
                    ]}
                    onPress={() => setIssueCategory(value)}
                  >
                    <Text style={styles.choiceText}>
                      {t(value.replaceAll("_", " "))}
                    </Text>
                  </Pressable>
                ))}
              </View>
              <TextInput
                multiline
                placeholder={t("What happened?")}
                style={[uiStyles.field, styles.multiline]}
                value={issueNote}
                onChangeText={setIssueNote}
              />
              {quality.photos.length ? (
                <>
                  <Text style={uiStyles.label}>{t("OPTIONAL PHOTO")}</Text>
                  <View style={styles.choices}>
                    <Pressable
                      style={[
                        styles.choice,
                        issuePhotoId === null ? styles.selected : undefined,
                      ]}
                      onPress={() => setIssuePhotoId(null)}
                    >
                      <Text style={styles.choiceText}>{t("None")}</Text>
                    </Pressable>
                    {quality.photos
                      .filter((item) =>
                        ["damage", "issue"].includes(item.category),
                      )
                      .map((item, index) => (
                        <Pressable
                          key={item.id}
                          style={[
                            styles.choice,
                            issuePhotoId === item.id
                              ? styles.selected
                              : undefined,
                          ]}
                          onPress={() => setIssuePhotoId(item.id)}
                        >
                          <Text style={styles.choiceText}>
                            {item.category.toUpperCase()} {index + 1}
                          </Text>
                        </Pressable>
                      ))}
                  </View>
                </>
              ) : null}
              <AppButton
                title={issue.isPending ? t("Saving…") : t("Save issue")}
                disabled={
                  offline || issue.isPending || issueNote.trim().length < 2
                }
                loading={issue.isPending}
                onPress={() => void saveIssue()}
              />
              <AppButton
                title={t("Cancel")}
                tone="secondary"
                onPress={() => setIssueOpen(false)}
              />
            </>
          )}
        </View>
      ) : null}

      {quality.issues.length ? (
        <View style={styles.block}>
          <Text style={styles.title}>{t("Issues")}</Text>
          {quality.issues.map((item) => (
            <View key={item.id} style={styles.record}>
              <Text style={styles.recordTitle}>
                {t(item.category.replaceAll("_", " "))}
              </Text>
              <Text style={uiStyles.body}>{item.note}</Text>
              <Text style={uiStyles.muted}>
                {item.created_by_staff_name} ·{" "}
                {formatUaeDateTime(item.created_at)}
              </Text>
            </View>
          ))}
        </View>
      ) : null}

      <View style={styles.summary}>
        <Summary label={t("Checklist")} value={summary.checklist} />
        <Summary label={t("Before")} value={String(summary.before)} />
        <Summary label={t("After")} value={String(summary.after)} />
        <Summary label={t("Issues")} value={String(summary.issues)} />
      </View>
      {!quality.can_complete && job.status === "in_progress" ? (
        <Text style={uiStyles.error}>
          {" " + t("Complete all required checklist items before completing the wash.") + " "}</Text>
      ) : null}

      {canManage && job.status === "completed" ? (
        <View style={styles.block}>
          <Text style={styles.title}>{t("Customer complaints")}</Text>
          {quality.complaints.map((item) => (
            <View key={item.id} style={styles.record}>
              <View style={uiStyles.row}>
                <Text style={styles.recordTitle}>{item.description}</Text>
                <StatusChip value={item.status} />
              </View>
              <Text style={uiStyles.muted}>
                {" " + t("Opened by") + " "}{item.created_by_staff_name}
              </Text>
              {item.review_note ? (
                <Text style={uiStyles.body}>{item.review_note}</Text>
              ) : null}
              {!item.correction_job_id &&
              !["resolved", "rejected"].includes(item.status) ? (
                <View style={styles.complaintActions}>
                  {item.status === "open" ? (
                    <ComplaintButton
                      context={context}
                      job={job}
                      complaint={item}
                      decision="under_review"
                      label={t("Review")}
                      disabled={offline}
                    />
                  ) : null}
                  <ComplaintButton
                    context={context}
                    job={job}
                    complaint={item}
                    decision="resolved"
                    label={t("Resolve")}
                    disabled={offline}
                  />
                  <ComplaintButton
                    context={context}
                    job={job}
                    complaint={item}
                    decision="rejected"
                    label={t("Reject")}
                    disabled={offline}
                  />
                  <AppButton
                    title={t("Approve rewash")}
                    tone="secondary"
                    disabled={offline}
                    onPress={() => setRewash(item)}
                  />
                </View>
              ) : item.correction_job_id ? (
                <Text style={styles.rewash}>
                  {" " + t("REWASH JOB ·") + " "}{item.correction_job_id}
                </Text>
              ) : null}
            </View>
          ))}
          <TextInput
            multiline
            placeholder={t("Record a customer complaint")}
            style={[uiStyles.field, styles.multiline]}
            value={complaintText}
            onChangeText={setComplaintText}
          />
          <AppButton
            title={complaint.isPending ? t("Saving…") : t("Add complaint")}
            disabled={
              offline || complaint.isPending || complaintText.trim().length < 2
            }
            loading={complaint.isPending}
            onPress={() => void addComplaint()}
          />
          {rewash ? (
            <RewashScheduler
              context={context}
              job={job}
              complaint={rewash}
              onClose={() => setRewash(null)}
            />
          ) : null}
        </View>
      ) : null}
    </Card>
  );
}

function PhotoStrip({ photos }: { photos: JobPhoto[] }) {
  if (!photos.length) return null;
  return (
    <View style={styles.block}>
      {(["before", "after", "damage", "issue"] as const).map((category) => {
        const matching = photos.filter((item) => item.category === category);
        return matching.length ? (
          <View key={category}>
            <Text style={uiStyles.label}>
              {photoCategoryLabel(category)} · {matching.length}
            </Text>
            <View style={styles.photos}>
              {matching.map((item) => (
                <Pressable
                  key={item.id}
                  accessibilityRole="button"
                  accessibilityLabel={t("View {category} photo", { category: photoCategoryLabel(category) })}
                  disabled={!item.access_url}
                  onPress={() =>
                    item.access_url && void Linking.openURL(item.access_url)
                  }
                >
                  {item.access_url ? (
                    <Image
                      source={{ uri: item.access_url }}
                      style={styles.thumb}
                    />
                  ) : (
                    <View style={[styles.thumb, styles.placeholder]} />
                  )}
                </Pressable>
              ))}
            </View>
          </View>
        ) : null;
      })}
    </View>
  );
}

function ComplaintButton({
  context,
  job,
  complaint,
  decision,
  label,
  disabled,
}: {
  context: StaffContext;
  job: Job;
  complaint: JobComplaint;
  decision: "resolved" | "rejected" | "under_review";
  label: string;
  disabled: boolean;
}) {
  const mutation = useComplaintReviewMutation(context, job);
  return (
    <AppButton
      title={mutation.isPending ? t("Saving…") : label}
      disabled={disabled || mutation.isPending}
      loading={mutation.isPending}
      onPress={() =>
        void mutation
          .mutateAsync({ complaintId: complaint.id, decision })
          .catch((reason) =>
            Alert.alert(
              t("Complaint not updated"),
              domainErrorMessage(reason, "Try again."),
            ),
          )
      }
    />
  );
}

function RewashScheduler({
  context,
  job,
  complaint,
  onClose,
}: {
  context: StaffContext;
  job: Job;
  complaint: JobComplaint;
  onClose: () => void;
}) {
  const [day, setDay] = useState(() => uaeDateKey());
  const [choice, setChoice] = useState<{
    startTime: string;
  } | null>(null);
  const availability = useAvailabilityQuery(
    context,
    job.booking_id,
    day,
    Math.max(1, job.vehicles.length),
    true,
  );
  const mutation = useComplaintReviewMutation(context, job);
  const options = useMemo(
    () =>
      (availability.data?.slots ?? []).flatMap((slot) =>
        slot.available
          ? [{
              startTime: slot.time,
              label: formatUaeTime(slot.starts_at),
            }]
          : [],
      ),
    [availability.data],
  );
  return (
    <View style={styles.scheduler}>
      <Text style={styles.title}>{t("Schedule complimentary rewash")}</Text>
      <DatePickerField
        label={t("Correction date")}
        value={day}
        minimumDate={wallDate(uaeDateKey())}
        onChange={(value) => {
          setDay(value);
          setChoice(null);
        }}
      />
      {availability.isPending ? (
        <Skeleton rows={3} />
      ) : options.length ? (
        options.map((option) => (
          <Pressable
            key={option.startTime}
            style={[
              styles.choice,
              choice?.startTime === option.startTime
                ? styles.selected
                : undefined,
            ]}
            onPress={() => setChoice(option)}
          >
            <Text style={styles.choiceText}>{option.label}</Text>
          </Pressable>
        ))
      ) : (
        <EmptyState title={t("No correction times available")} />
      )}
      <AppButton
        title={
          mutation.isPending ? t("Approving…") : t("Approve and schedule rewash")
        }
        disabled={mutation.isPending || !choice}
        loading={mutation.isPending}
        onPress={() =>
          choice &&
          void mutation
            .mutateAsync({
              complaintId: complaint.id,
              decision: "approve_rewash",
              appointment: { day, ...choice },
            })
            .then(onClose)
            .catch((reason) =>
              Alert.alert(
                t("Rewash not scheduled"),
                domainErrorMessage(
                  reason,
                  "Choose another time and try again.",
                ),
              ),
            )
        }
      />
      <AppButton title={t("Cancel")} tone="secondary" onPress={onClose} />
    </View>
  );
}

function Summary({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.summaryItem}>
      <Text style={styles.summaryValue}>{value}</Text>
      <Text style={uiStyles.muted}>{label}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  section: {
    color: colors.primary,
    fontSize: 11,
    fontWeight: "900",
    letterSpacing: 1.2,
  },
  block: { gap: spacing.sm, marginTop: spacing.md },
  title: { color: colors.text, fontSize: 17, fontWeight: "900" },
  multiline: { minHeight: 72, textAlignVertical: "top" },
  choices: { flexDirection: "row", flexWrap: "wrap", gap: spacing.xs },
  choice: {
    borderColor: colors.border,
    borderWidth: 1,
    borderRadius: radii.sm,
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.sm,
    backgroundColor: colors.surface,
  },
  selected: { borderColor: colors.primary, backgroundColor: colors.secondary },
  choiceText: { color: colors.text, fontSize: 12, fontWeight: "800" },
  actions: { flexDirection: "row", gap: spacing.sm },
  complaintActions: { gap: spacing.sm },
  flex: { flex: 1, minWidth: 0 },
  preview: { flexDirection: "row", alignItems: "center", gap: spacing.sm },
  removePhoto: { minHeight: 44, alignSelf: "flex-start", justifyContent: "center" },
  photos: { flexDirection: "row", flexWrap: "wrap", gap: spacing.sm },
  thumb: {
    width: 76,
    height: 76,
    borderRadius: radii.sm,
    backgroundColor: colors.surfaceElevated,
  },
  placeholder: { borderWidth: 1, borderColor: colors.border },
  checkRow: {
    minHeight: 48,
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  checkDone: { color: colors.success, fontSize: 24, fontWeight: "900" },
  checkEmpty: { color: colors.textSecondary, fontSize: 24, fontWeight: "900" },
  checkLabel: { flex: 1, color: colors.text, fontWeight: "800" },
  record: {
    gap: spacing.xs,
    padding: spacing.sm,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radii.sm,
  },
  recordTitle: { flex: 1, color: colors.text, fontWeight: "900" },
  summary: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.sm,
    marginTop: spacing.md,
  },
  summaryItem: {
    width: "47%",
    padding: spacing.sm,
    borderRadius: radii.sm,
    backgroundColor: colors.surfaceElevated,
  },
  summaryValue: { color: colors.text, fontSize: 20, fontWeight: "900" },
  rewash: { color: colors.primary, fontWeight: "900", fontSize: 11 },
  scheduler: {
    gap: spacing.sm,
    padding: spacing.md,
    backgroundColor: colors.surfaceElevated,
    borderRadius: radii.md,
  },
});
