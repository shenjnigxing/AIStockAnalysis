"use client";

import { useMemo, useState, useTransition } from "react";
import { useRouter } from "next/navigation";

type OpsResponse = {
  ok: boolean;
  status: number;
  error: string | null;
  data: unknown;
};

export function ApiActionForm({
  title,
  path,
  initialPayload,
  method = "POST",
  buttonText = "Execute",
  refreshAfterSuccess = true,
  allowPathEdit = false
}: {
  title: string;
  path: string;
  initialPayload: Record<string, unknown>;
  method?: "POST" | "PUT" | "PATCH" | "DELETE";
  buttonText?: string;
  refreshAfterSuccess?: boolean;
  allowPathEdit?: boolean;
}) {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();
  const [pathInput, setPathInput] = useState(path);
  const [payloadText, setPayloadText] = useState(() => JSON.stringify(initialPayload, null, 2));
  const [result, setResult] = useState<OpsResponse | null>(null);
  const [inputError, setInputError] = useState<string | null>(null);

  const prettyResult = useMemo(() => (result ? JSON.stringify(result, null, 2) : ""), [result]);

  const submit = async () => {
    setInputError(null);
    let payload: Record<string, unknown>;
    try {
      payload = JSON.parse(payloadText) as Record<string, unknown>;
    } catch {
      setInputError("Payload is not valid JSON.");
      return;
    }

    const response = await fetch("/api/ops", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path: pathInput, method, payload })
    });
    const body = (await response.json()) as OpsResponse;
    setResult(body);
    if (body.ok && refreshAfterSuccess) {
      startTransition(() => {
        router.refresh();
      });
    }
  };

  return (
    <div className="actionPanel">
      <h3>{title}</h3>
      <p>
        Endpoint: <code>{method} {pathInput}</code>
      </p>
      {allowPathEdit ? (
        <input
          className="pathInput"
          value={pathInput}
          onChange={(event) => setPathInput(event.target.value)}
          placeholder="/api/..."
        />
      ) : null}
      <textarea
        className="payloadInput"
        value={payloadText}
        onChange={(event) => setPayloadText(event.target.value)}
        rows={8}
      />
      {inputError ? <p className="inputError">{inputError}</p> : null}
      <button type="button" className="actionButton" onClick={submit} disabled={isPending}>
        {isPending ? "Running..." : buttonText}
      </button>
      {result ? (
        <details>
          <summary>Result</summary>
          <pre>{prettyResult}</pre>
        </details>
      ) : null}
    </div>
  );
}
