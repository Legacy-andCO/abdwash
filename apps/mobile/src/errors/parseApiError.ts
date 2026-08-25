type ValidationIssue = {
  loc?: Array<string | number>;
  msg?: string;
  type?: string;
};

export type ParsedApiError = {
  code: string;
  message: string;
  requestId?: string;
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function validationMessage(issues: ValidationIssue[]) {
  return issues
    .slice(0, 3)
    .map((issue) => {
      const rawField = [...(issue.loc ?? [])]
        .reverse()
        .find((part) => typeof part === "string" && part !== "body");
      const field =
        typeof rawField === "string"
          ? rawField.replaceAll("_", " ").replace(/^./, (value) => value.toUpperCase())
          : "Request";
      return `${field}: ${issue.msg ?? "Invalid value"}`;
    })
    .join(" ");
}

export function parseApiErrorPayload(
  payload: unknown,
  status: number,
): ParsedApiError {
  const body = isRecord(payload) ? payload : {};
  const detail = body.detail;
  if (Array.isArray(detail)) {
    return {
      code: "VALIDATION_ERROR",
      message: validationMessage(
        detail.filter(isRecord).map((issue) => issue as ValidationIssue),
      ) || "Review the highlighted fields and try again.",
      requestId:
        typeof body.request_id === "string" ? body.request_id : undefined,
    };
  }
  const detailObject = isRecord(detail) ? detail : undefined;
  const directCode = typeof body.code === "string" ? body.code : undefined;
  const detailCode =
    typeof detailObject?.code === "string" ? detailObject.code : undefined;
  const directMessage =
    typeof body.message === "string" ? body.message : undefined;
  const detailMessage =
    typeof detailObject?.message === "string"
      ? detailObject.message
      : typeof detail === "string"
        ? detail
        : undefined;
  return {
    code:
      directCode ??
      detailCode ??
      (status === 401 ? "UNAUTHORIZED" : "REQUEST_FAILED"),
    message:
      directMessage ??
      detailMessage ??
      directCode ??
      detailCode ??
      "Request failed",
    requestId:
      typeof body.request_id === "string" ? body.request_id : undefined,
  };
}
