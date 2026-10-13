export type Schema = Record<string, unknown>;
export type ResourceKind = "knowledge" | "skill" | "mcp";
export interface InputField {
  name: string;
  type: "string" | "number" | "boolean" | "array" | "object";
  required: boolean;
  description: string;
  source: "query" | "files" | "context" | "manual";
  default: unknown;
  enum: string[];
}
export interface AgentConfig {
  id: string | null;
  revision: number;
  name: string;
  description: string;
  icon: "research" | "database" | "knowledge" | "spark";
  system_prompt: string;
  model_name: string;
  builtin_tools: string[];
  input_fields: InputField[];
  input_schema: Schema | null;
  output_format: "text" | "markdown" | "json";
  output_schema: Schema;
  required_sections: string[];
  artifacts: ("markdown" | "pdf")[];
  knowledge: { resource_id: string; chat_ids: string[] }[];
  skill_ids: string[];
  mcp: { resource_id: string; tools: string[] }[];
  enabled?: boolean;
  version?: number;
  has_changes?: boolean;
  status?: string;
}
export interface ToolSpec {
  name: string;
  description?: string;
  inputSchema?: Schema;
}
export interface Resource {
  id: string;
  revision: number;
  kind: ResourceKind;
  name: string;
  description: string;
  config: {
    url?: string;
    secret_env?: string;
    transport?: "http" | "sse" | "stdio";
    command?: string;
    args?: string[];
    content?: string;
    files?: Record<string, string>;
    version?: string;
    required_tools?: string[];
  };
  status: string;
  message: string;
  has_secret: boolean;
  discovery: {
    chats?: { id: string; name: string; datasets: string[] }[];
    datasets?: { id: string; name: string }[];
    tools?: ToolSpec[];
  };
}
export interface Catalog {
  agents: AgentConfig[];
  resources: Resource[];
  builtin_tools: { id: string; name: string }[];
}
export interface TraceEvent {
  event: string;
  message: string;
  timestamp: string;
  data: unknown;
}
export interface TestResult {
  status: string;
  result?: unknown;
  message?: string;
  events: TraceEvent[];
  files: { name: string; path: string }[];
  revision?: number;
}
export const statusLabels: Record<string, string> = {
  draft: "草稿",
  enabled: "已启用",
  disabled: "已停用",
  unconfigured: "待配置",
  ready: "可用",
  error: "连接异常",
};
export const kindLabels: Record<ResourceKind, string> = {
  knowledge: "知识库",
  skill: "Skills",
  mcp: "MCP",
};

export function newAgent(template?: AgentConfig): AgentConfig {
  return {
    id: null,
    revision: 0,
    name: template ? template.name + "（副本）" : "",
    description: "",
    icon: "spark",
    system_prompt:
      "你是一名专业的研究助手。\n\n目标：根据用户需求收集信息，给出有依据的分析。\n\n工作步骤：\n1. 明确问题和边界。\n2. 使用已连接的资源获取资料。\n3. 整理结论，说明依据和下一步行动。\n\n约束：资料不足时说明缺口，不编造来源或数据。",
    model_name: "",
    builtin_tools: [],
    input_fields: [
      {
        name: "query",
        type: "string",
        required: true,
        description: "本次任务问题",
        source: "query",
        default: null,
        enum: [],
      },
    ],
    input_schema: null,
    output_format: "markdown",
    output_schema: {
      type: "object",
      properties: { answer: { type: "string" } },
      required: ["answer"],
    },
    required_sections: [],
    artifacts: [],
    knowledge: [],
    skill_ids: [],
    mcp: [],
    ...(template ? JSON.parse(JSON.stringify(template)) : {}),
    ...(template
      ? {
          id: null,
          revision: 0,
          name: template.name + "（副本）",
          version: 0,
          enabled: false,
          status: "draft",
          has_changes: false,
        }
      : {}),
  };
}
