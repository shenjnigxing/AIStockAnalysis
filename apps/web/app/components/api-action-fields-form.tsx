"use client";

import { useMemo, useRef, useState, useTransition } from "react";
import { useRouter } from "next/navigation";

type OpsResponse = {
  ok: boolean;
  status: number;
  error: string | null;
  data: unknown;
};

type FieldKind = "text" | "number" | "select" | "boolean" | "textarea" | "csv";

type FieldOption = {
  label: string;
  value: string;
};

export type ActionField = {
  name: string;
  label: string;
  kind: FieldKind;
  defaultValue?: string | number | boolean;
  options?: FieldOption[];
  placeholder?: string;
  required?: boolean;
  payloadKey?: string;
  includeInPayload?: boolean;
};

function setByPath(target: Record<string, unknown>, keyPath: string, value: unknown): void {
  const parts = keyPath.split(".");
  let cursor: Record<string, unknown> = target;
  for (let i = 0; i < parts.length - 1; i += 1) {
    const key = parts[i];
    const current = cursor[key];
    if (!current || typeof current !== "object" || Array.isArray(current)) {
      cursor[key] = {};
    }
    cursor = cursor[key] as Record<string, unknown>;
  }
  cursor[parts[parts.length - 1]] = value;
}

function normalizeValue(field: ActionField, rawValue: string | boolean): unknown {
  if (field.kind === "boolean") return Boolean(rawValue);
  if (field.kind === "number") {
    if (rawValue === "") return 0;
    const parsed = Number(rawValue);
    return Number.isFinite(parsed) ? parsed : 0;
  }
  if (field.kind === "csv") {
    return String(rawValue)
      .split(",")
      .map((item) => item.trim())
      .filter((item) => item.length > 0);
  }
  return String(rawValue);
}

function interpolatePath(template: string, values: Record<string, string | boolean>): string {
  let path = template;
  for (const [key, value] of Object.entries(values)) {
    path = path.replaceAll(`{${key}}`, encodeURIComponent(String(value)));
  }
  return path;
}

export function ApiActionFieldsForm({
  title,
  path,
  pathTemplate,
  fields,
  method = "POST",
  buttonText = "执行",
  refreshAfterSuccess = true
}: {
  title: string;
  path: string;
  pathTemplate?: string;
  fields: ActionField[];
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  buttonText?: string;
  refreshAfterSuccess?: boolean;
}) {
  const router = useRouter();
  const submitting = useRef(false);
  const [requestPending, setRequestPending] = useState(false);
  const [isPending, startTransition] = useTransition();
  const [result, setResult] = useState<OpsResponse | null>(null);
  const [inputError, setInputError] = useState<string | null>(null);
  const [values, setValues] = useState<Record<string, string | boolean>>(() => {
    const initial: Record<string, string | boolean> = {};
    for (const field of fields) {
      if (field.kind === "boolean") {
        initial[field.name] = Boolean(field.defaultValue ?? false);
      } else {
        initial[field.name] = String(field.defaultValue ?? "");
      }
    }
    return initial;
  });

  const requestPath = useMemo(() => interpolatePath(pathTemplate || path, values), [path, pathTemplate, values]);
  const prettyResult = useMemo(() => (result ? JSON.stringify(result, null, 2) : ""), [result]);

  const orderKey = useRef<{fingerprint:string;key:string}|null>(null);
  const submit = async () => {
    if (submitting.current) return;
    setInputError(null);
    setResult(null);

    for (const field of fields) {
      if (!field.required) continue;
      const value = values[field.name];
      if (field.kind === "boolean") continue;
      if (String(value ?? "").trim() === "") {
        setInputError(`字段「${field.label}」为必填项。`);
        return;
      }
    }

    for (const field of fields) {
      if (field.kind === "number" && !Number.isFinite(Number(values[field.name]))) {
        setInputError(`字段「${field.label}」必须是有效数字。`);
        return;
      }
    }
    const payload: Record<string, unknown> = {};
    for (const field of fields) {
      if (field.includeInPayload === false) continue;
      const raw = values[field.name];
      const normalized = normalizeValue(field, raw ?? "");
      setByPath(payload, field.payloadKey || field.name, normalized);
    }

    const headers: Record<string,string> = {"Content-Type":"application/json"};
    if (method === 'POST' && requestPath === '/api/paper/orders') {
      const fingerprint = JSON.stringify(payload);
      if (!orderKey.current || orderKey.current.fingerprint !== fingerprint) orderKey.current = {fingerprint,key:crypto.randomUUID()};
      headers['Idempotency-Key'] = orderKey.current.key;
    }
    submitting.current = true;
    setRequestPending(true);
    try {
    const response = await fetch("/api/ops", {
      method: "POST",
      headers,
      body: JSON.stringify({ path: requestPath, method, payload })
    });
    const body = (await response.json()) as OpsResponse;
    setResult(body);
    if (body.ok && refreshAfterSuccess) {
      startTransition(() => {
        router.refresh();
      });
    }
    } catch {
      setResult(null);
      setInputError("请求失败或结果未知，请先核对记录，不要重复提交。");
    } finally {
      submitting.current = false;
      setRequestPending(false);
    }
  };

  return (
    <div className="actionPanel">
      <h3>{title}</h3>
      <p>
        接口：<code>{method} {requestPath}</code>
      </p>
      {fields.length > 0 ? (
        <div className="fieldGrid">
          {fields.map((field) => {
            const value = values[field.name];
            return (
              <label key={field.name} className="formRow">
                <span className="fieldLabel">{field.label}</span>
                {field.kind === "select" ? (
                  <select
                    className="fieldInput"
                    value={String(value ?? "")}
                    onChange={(event) => setValues((prev) => ({ ...prev, [field.name]: event.target.value }))}
                  >
                    {(field.options || []).map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                ) : null}
                {field.kind === "boolean" ? (
                  <input
                    className="fieldCheckbox"
                    type="checkbox"
                    checked={Boolean(value)}
                    onChange={(event) => setValues((prev) => ({ ...prev, [field.name]: event.target.checked }))}
                  />
                ) : null}
                {field.kind === "textarea" ? (
                  <textarea
                    className="fieldInput"
                    value={String(value ?? "")}
                    rows={4}
                    placeholder={field.placeholder}
                    onChange={(event) => setValues((prev) => ({ ...prev, [field.name]: event.target.value }))}
                  />
                ) : null}
                {["text", "number", "csv"].includes(field.kind) ? (
                  <input
                    className="fieldInput"
                    type={field.kind === "number" ? "number" : "text"}
                    value={String(value ?? "")}
                    placeholder={field.placeholder}
                    onChange={(event) => setValues((prev) => ({ ...prev, [field.name]: event.target.value }))}
                  />
                ) : null}
              </label>
            );
          })}
        </div>
      ) : null}
      {inputError ? <p className="inputError">{inputError}</p> : null}
      <button type="button" className="actionButton" onClick={submit} disabled={isPending || requestPending}>
        {isPending || requestPending ? "执行中..." : buttonText}
      </button>
      {result ? (
        <details>
          <summary>返回结果</summary>
          <pre>{prettyResult}</pre>
        </details>
      ) : null}
    </div>
  );
}
