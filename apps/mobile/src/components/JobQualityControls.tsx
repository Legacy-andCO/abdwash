import { useEffect, useMemo, useRef, useState } from "react";
import {
  Alert,
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
import { ImageManipulator, SaveFormat } from "expo-image-manipulator";
import { capabilities } from "../capabilities";
import { DatePickerField, toIsoDate } from "./pickers";
import {
  AppButton,
  Card,
  EmptyState,
  Skeleton,
  StatusChip,
  uiStyles,
} from "./ui";
import { domainErrorMessage } from "../errors/domainErrors";
import { newClientEventId } from "../idempotency/clientEventId";
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

type PhotoDraft = {
  uri: string;
  category: JobPhoto["category"];
  clientRequestId: string;
};

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
  const [draft, setDraft] = useState<PhotoDraft | null>(null);
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

  async function choosePhoto(source: "camera" | "library") {
    const permission =
      source === "camera"
        ? await ImagePicker.requestCameraPermissionsAsync()
        : await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (!permission.granted) {
      Alert.alert(
        "Permission needed",
        source === "camera"
          ? "Allow camera access to capture job evidence."
          : "Allow photo access to select job evidence.",
      );
      return;
    }
    const result =
      source === "camera"
        ? await ImagePicker.launchCameraAsync({
            mediaTypes: ["images"],
            quality: 0.9,
          })
        : await ImagePicker.launchImageLibraryAsync({
            mediaTypes: ["images"],
            quality: 0.9,
            allowsMultipleSelection: false,
          });
    if (result.canceled || !result.assets[0]) return;
    const manipulator = ImageManipulator.manipulate(result.assets[0].uri);
    manipulator.resize({ width: 1600 });
    const rendered = await manipulator.renderAsync();
    const prepared = await rendered.saveAsync({
      compress: 0.75,
      format: SaveFormat.JPEG,
    });
    setDraft({
      uri: prepared.uri,
      category: photoCategory,
      clientRequestId: newClientEventId(),
    });
  }

  async function uploadDraft() {
    if (!draft) return;
    try {
      await photo.mutateAsync(draft);
      setDraft(null);
    } catch (reason) {
      Alert.alert(
        "Photo not uploaded",
        domainErrorMessage(reason, "Keep the preview and try uploading again."),
      );
    }
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
        "Inspection not saved",
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
      Alert.alert("Issue not saved", domainErrorMessage(reason, "Try again."));
    }
  }

  async function addComplaint() {
    try {
      await complaint.mutateAsync(complaintText.trim());
      setComplaintText("");
    } catch (reason) {
      Alert.alert(
        "Complaint not saved",
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
          title="Quality record unavailable"
          body={domainErrorMessage(
            error,
            "We couldn't load this job's quality record.",
          )}
        />
        <AppButton title="Try again" tone="secondary" onPress={onRetry} />
      </Card>
    );
  const summary = qualitySummary(quality);
  const canWork = ["arrived", "in_progress"].includes(job.status);
  const canManage = capabilities(context.role).canManageAnyJob;
  return (
    <Card>
      <Text style={styles.section}>JOB QUALITY</Text>
      {offline ? (
        <Text style={uiStyles.error}>
          Offline · saved quality evidence is visible, but changes and uploads
          require a connection.
        </Text>
      ) : null}
      {canWork ? (
        <View style={styles.block}>
          <Text style={styles.title}>Vehicle inspection</Text>
          <TextInput
            accessibilityLabel="Vehicle condition notes"
            editable={!offline}
            multiline
            placeholder="Overall condition notes"
            style={[uiStyles.field, styles.multiline]}
            value={condition}
            onChangeText={setCondition}
          />
          <Text style={uiStyles.label}>EXISTING DAMAGE</Text>
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
                  {value ? value.replaceAll("_", " ") : "None"}
                </Text>
              </Pressable>
            ))}
          </View>
          {damageCategory ? (
            <TextInput
              accessibilityLabel="Existing damage notes"
              editable={!offline}
              multiline
              placeholder="Where is the damage?"
              style={[uiStyles.field, styles.multiline]}
              value={damageNotes}
              onChangeText={setDamageNotes}
            />
          ) : null}
          <AppButton
            title={
              inspection.isPending
                ? "Saving…"
                : quality.inspection
                  ? "Update inspection"
                  : "Complete inspection"
            }
            disabled={offline || inspection.isPending}
            loading={inspection.isPending}
            onPress={() => void saveInspection()}
          />
        </View>
      ) : quality.inspection ? (
        <View style={styles.block}>
          <Text style={styles.title}>Inspection</Text>
          <Text style={uiStyles.muted}>
            {quality.inspection.completed_by_staff_name} ·{" "}
            {new Date(quality.inspection.completed_at).toLocaleString()}
          </Text>
          {quality.inspection.condition_notes ? (
            <Text style={uiStyles.body}>
              {quality.inspection.condition_notes}
            </Text>
          ) : null}
          {quality.inspection.damage_category ? (
            <Text style={uiStyles.body}>
              {quality.inspection.damage_category.replaceAll("_", " ")} ·{" "}
              {quality.inspection.damage_notes || "No additional note"}
            </Text>
          ) : null}
        </View>
      ) : (
        <Text style={uiStyles.muted}>
          No inspection was recorded for this job.
        </Text>
      )}

      {categories.length ? (
        <View style={styles.block}>
          <Text style={styles.title}>Photo evidence</Text>
          <View style={styles.choices}>
            {categories.map((category) => (
              <Pressable
                key={category}
                style={[
                  styles.choice,
                  photoCategory === category ? styles.selected : undefined,
                ]}
                onPress={() => setPhotoCategory(category)}
              >
                <Text style={styles.choiceText}>{category.toUpperCase()}</Text>
              </Pressable>
            ))}
          </View>
          {draft ? (
            <View style={styles.preview}>
              <Image source={{ uri: draft.uri }} style={styles.previewImage} />
              <Text style={uiStyles.muted}>
                {draft.category.toUpperCase()} preview
              </Text>
              <AppButton
                title={photo.isPending ? "Uploading…" : "Upload photo"}
                disabled={offline || photo.isPending}
                loading={photo.isPending}
                onPress={() => void uploadDraft()}
              />
              <AppButton
                title="Remove preview"
                tone="secondary"
                disabled={photo.isPending}
                onPress={() => setDraft(null)}
              />
            </View>
          ) : (
            <View style={styles.actions}>
              <View style={styles.flex}>
                <AppButton
                  title="Take photo"
                  disabled={offline}
                  onPress={() => void choosePhoto("camera")}
                />
              </View>
              <View style={styles.flex}>
                <AppButton
                  title="Choose photo"
                  tone="secondary"
                  disabled={offline}
                  onPress={() => void choosePhoto("library")}
                />
              </View>
            </View>
          )}
        </View>
      ) : null}

      <PhotoStrip photos={quality.photos} />

      {quality.checklist.length ? (
        <View style={styles.block}>
          <Text style={styles.title}>
            Service checklist · {summary.checklist}
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
                      "Checklist not saved",
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
                {item.is_required ? "" : " · optional"}
              </Text>
            </Pressable>
          ))}
        </View>
      ) : (
        <Text style={uiStyles.muted}>
          No checklist was configured for this historical job.
        </Text>
      )}

      {canWork ? (
        <View style={styles.block}>
          {!issueOpen ? (
            <AppButton
              title="Add issue"
              tone="secondary"
              disabled={offline}
              onPress={() => setIssueOpen(true)}
            />
          ) : (
            <>
              <Text style={styles.title}>Report an issue</Text>
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
                      {value.replaceAll("_", " ")}
                    </Text>
                  </Pressable>
                ))}
              </View>
              <TextInput
                multiline
                placeholder="What happened?"
                style={[uiStyles.field, styles.multiline]}
                value={issueNote}
                onChangeText={setIssueNote}
              />
              {quality.photos.length ? (
                <>
                  <Text style={uiStyles.label}>OPTIONAL PHOTO</Text>
                  <View style={styles.choices}>
                    <Pressable
                      style={[
                        styles.choice,
                        issuePhotoId === null ? styles.selected : undefined,
                      ]}
                      onPress={() => setIssuePhotoId(null)}
                    >
                      <Text style={styles.choiceText}>None</Text>
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
                title={issue.isPending ? "Saving…" : "Save issue"}
                disabled={
                  offline || issue.isPending || issueNote.trim().length < 2
                }
                loading={issue.isPending}
                onPress={() => void saveIssue()}
              />
              <AppButton
                title="Cancel"
                tone="secondary"
                onPress={() => setIssueOpen(false)}
              />
            </>
          )}
        </View>
      ) : null}

      {quality.issues.length ? (
        <View style={styles.block}>
          <Text style={styles.title}>Issues</Text>
          {quality.issues.map((item) => (
            <View key={item.id} style={styles.record}>
              <Text style={styles.recordTitle}>
                {item.category.replaceAll("_", " ")}
              </Text>
              <Text style={uiStyles.body}>{item.note}</Text>
              <Text style={uiStyles.muted}>
                {item.created_by_staff_name} ·{" "}
                {new Date(item.created_at).toLocaleString()}
              </Text>
            </View>
          ))}
        </View>
      ) : null}

      <View style={styles.summary}>
        <Summary label="Checklist" value={summary.checklist} />
        <Summary label="Before" value={String(summary.before)} />
        <Summary label="After" value={String(summary.after)} />
        <Summary label="Issues" value={String(summary.issues)} />
      </View>
      {!quality.can_complete && job.status === "in_progress" ? (
        <Text style={uiStyles.error}>
          Complete all required checklist items before completing the wash.
        </Text>
      ) : null}

      {canManage && job.status === "completed" ? (
        <View style={styles.block}>
          <Text style={styles.title}>Customer complaints</Text>
          {quality.complaints.map((item) => (
            <View key={item.id} style={styles.record}>
              <View style={uiStyles.row}>
                <Text style={styles.recordTitle}>{item.description}</Text>
                <StatusChip value={item.status} />
              </View>
              <Text style={uiStyles.muted}>
                Opened by {item.created_by_staff_name}
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
                      label="Review"
                      disabled={offline}
                    />
                  ) : null}
                  <ComplaintButton
                    context={context}
                    job={job}
                    complaint={item}
                    decision="resolved"
                    label="Resolve"
                    disabled={offline}
                  />
                  <ComplaintButton
                    context={context}
                    job={job}
                    complaint={item}
                    decision="rejected"
                    label="Reject"
                    disabled={offline}
                  />
                  <AppButton
                    title="Approve rewash"
                    tone="secondary"
                    disabled={offline}
                    onPress={() => setRewash(item)}
                  />
                </View>
              ) : item.correction_job_id ? (
                <Text style={styles.rewash}>
                  REWASH JOB · {item.correction_job_id}
                </Text>
              ) : null}
            </View>
          ))}
          <TextInput
            multiline
            placeholder="Record a customer complaint"
            style={[uiStyles.field, styles.multiline]}
            value={complaintText}
            onChangeText={setComplaintText}
          />
          <AppButton
            title={complaint.isPending ? "Saving…" : "Add complaint"}
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
              {category.toUpperCase()} · {matching.length}
            </Text>
            <View style={styles.photos}>
              {matching.map((item) => (
                <Pressable
                  key={item.id}
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
      title={mutation.isPending ? "Saving…" : label}
      disabled={disabled || mutation.isPending}
      loading={mutation.isPending}
      onPress={() =>
        void mutation
          .mutateAsync({ complaintId: complaint.id, decision })
          .catch((reason) =>
            Alert.alert(
              "Complaint not updated",
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
  const [day, setDay] = useState(() => toIsoDate(new Date()));
  const [choice, setChoice] = useState<{
    startTime: string;
    resourceId: string;
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
          ? slot.resources.map((resource) => ({
              startTime: slot.time,
              resourceId: resource.resource_id,
              label: `${new Date(slot.starts_at).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })} · ${resource.resource_name}`,
            }))
          : [],
      ),
    [availability.data],
  );
  return (
    <View style={styles.scheduler}>
      <Text style={styles.title}>Schedule complimentary rewash</Text>
      <DatePickerField
        label="Correction date"
        value={day}
        minimumDate={new Date()}
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
            key={`${option.startTime}-${option.resourceId}`}
            style={[
              styles.choice,
              choice?.startTime === option.startTime &&
              choice.resourceId === option.resourceId
                ? styles.selected
                : undefined,
            ]}
            onPress={() => setChoice(option)}
          >
            <Text style={styles.choiceText}>{option.label}</Text>
          </Pressable>
        ))
      ) : (
        <EmptyState title="No correction times available" />
      )}
      <AppButton
        title={
          mutation.isPending ? "Approving…" : "Approve and schedule rewash"
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
                "Rewash not scheduled",
                domainErrorMessage(
                  reason,
                  "Choose another time and try again.",
                ),
              ),
            )
        }
      />
      <AppButton title="Cancel" tone="secondary" onPress={onClose} />
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
  flex: { flex: 1 },
  preview: { gap: spacing.sm },
  previewImage: {
    width: "100%",
    height: 220,
    borderRadius: radii.md,
    backgroundColor: colors.surfaceElevated,
  },
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
