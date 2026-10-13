import { API_BASE_URL } from "../lib/config";
import type { AgentConfig, Catalog, Resource, TestResult } from "./types";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(API_BASE_URL + "/api/manage" + path, init);
  const payload = await response.json();
  if (!response.ok)
    throw new Error(
      typeof payload.detail === "string"
        ? payload.detail
        : "配置内容不符合要求，请检查必填项和字段类型",
    );
  return payload;
}
const json = (body: unknown): RequestInit => ({
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});
export const getCatalog = () => request<Catalog>("/catalog");
export const saveAgent = (agent: AgentConfig, publish = false) =>
  request<AgentConfig>("/agents?publish=" + publish, json(agent));
export const disableAgent = (id: string) =>
  request<AgentConfig>(`/agents/${id}/disable`, { method: "POST" });
export const getVersions = (id: string) =>
  request<{ version: number; created_at: string }[]>(`/agents/${id}/versions`);
export const restoreAgent = (id: string, version: number) =>
  request<AgentConfig>(`/agents/${id}/restore/${version}`, { method: "POST" });
export const previewAgent = (
  agent: AgentConfig,
  values: Record<string, unknown>,
) =>
  request<{ prompt: string; input: unknown }>(
    "/preview",
    json({ agent, values }),
  );
export const testAgent = (
  agent: AgentConfig,
  values: Record<string, unknown>,
  thread_id: string,
) => request<TestResult>("/test", json({ agent, values, thread_id }));
export const saveResource = (
  resource: Partial<Resource> & { secret?: string; clear_secret?: boolean },
) => request<Resource>("/resources", json(resource));
export const probeResource = (id: string) =>
  request<Resource>(`/resources/${id}/probe`, { method: "POST" });
export function importSkill(file: File) {
  const body = new FormData();
  body.append("file", file);
  return request<Resource>("/skills/import", { method: "POST", body });
}
