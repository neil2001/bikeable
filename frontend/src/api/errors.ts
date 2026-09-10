import type { ApiErrorCode, ApiErrorEnvelope } from "../types/api";

export class ApiClientError extends Error {
  readonly code: ApiErrorCode;
  readonly details: Record<string, unknown>;
  readonly status: number;

  constructor(
    code: ApiErrorCode,
    message: string,
    status: number,
    details: Record<string, unknown> = {},
  ) {
    super(message);
    this.name = "ApiClientError";
    this.code = code;
    this.status = status;
    this.details = details;
  }
}

function isErrorEnvelope(value: unknown): value is ApiErrorEnvelope {
  if (typeof value !== "object" || value === null || !("error" in value)) {
    return false;
  }
  const error = (value as ApiErrorEnvelope).error;
  return (
    typeof error === "object" &&
    error !== null &&
    typeof error.code === "string" &&
    typeof error.message === "string"
  );
}

export async function parseApiResponse<T>(response: Response): Promise<T> {
  const payload: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    if (isErrorEnvelope(payload)) {
      throw new ApiClientError(
        payload.error.code,
        payload.error.message,
        response.status,
        payload.error.details,
      );
    }
    throw new ApiClientError(
      "INTERNAL_ERROR",
      "Request failed.",
      response.status,
    );
  }
  return payload as T;
}
