import {
  ArrowLeftOutlined,
  CopyOutlined,
  HistoryOutlined,
  PlayCircleOutlined,
  SaveOutlined,
} from "@ant-design/icons";
import {
  Alert,
  App,
  Button,
  Checkbox,
  Input,
  Modal,
  Select,
  Tabs,
  Tag,
} from "antd";
import { useEffect, useRef, useState } from "react";
import {
  disableAgent,
  getVersions,
  previewAgent,
  restoreAgent,
  saveAgent,
} from "./api";
import { ConnectionsChooser } from "./ConnectionsChooser";
import { IOEditor } from "./IOEditor";
import { ResourceForm } from "./ResourceForm";
import { TestDrawer } from "./TestDrawer";
import { statusLabels } from "./types";
import type { AgentConfig, Catalog, ResourceKind } from "./types";

export function AgentEditor({
  initial,
  catalog,
  onSaved,
  onBack,
  onCopy,
  onRefresh,
  onDirty,
}: {
  initial: AgentConfig;
  catalog: Catalog;
  onSaved: (agent: AgentConfig) => Promise<void>;
  onBack: () => void;
  onCopy: () => void;
  onRefresh: () => Promise<void>;
  onDirty: (dirty: boolean) => void;
}) {
  const { message } = App.useApp();
  const [agent, setAgent] = useState<AgentConfig>(() =>
    JSON.parse(JSON.stringify(initial)),
  );
  const baseline = useRef(JSON.stringify(initial));
  const editorRef = useRef<HTMLDivElement>(null);
  const [tab, setTab] = useState("basic");
  const [busy, setBusy] = useState(false);
  const [test, setTest] = useState(false);
  const [resourceKind, setResourceKind] = useState<ResourceKind>();
  const [preview, setPreview] = useState("");
  const [sample, setSample] = useState('{"query":"请研究品类策略"}');
  const [versions, setVersions] =
    useState<{ version: number; created_at: string }[]>();
  const update = (patch: Partial<AgentConfig>) => {
    setAgent((previous) => ({ ...previous, ...patch }));
    setPreview("");
  };
  useEffect(() => {
    onDirty(JSON.stringify(agent) !== baseline.current);
  }, [agent, onDirty]);
  useEffect(() => () => onDirty(false), [onDirty]);
  function checkEditors() {
    if (editorRef.current?.querySelector(".field-error, [data-invalid]"))
      throw new Error("请先修正 JSON 编辑器中的错误");
  }
  async function save(publish = false) {
    setBusy(true);
    try {
      checkEditors();
      const saved = await saveAgent(agent, publish);
      baseline.current = JSON.stringify(saved);
      setAgent(saved);
      onDirty(false);
      await onSaved(saved);
      message.success(
        publish ? "助手配置已启用，新任务将使用此版本" : "草稿已保存",
      );
    } catch (error) {
      message.error(error instanceof Error ? error.message : "保存失败");
    } finally {
      setBusy(false);
    }
  }
  async function showPreview() {
    setBusy(true);
    try {
      checkEditors();
      setPreview((await previewAgent(agent, JSON.parse(sample))).prompt);
    } catch (error) {
      message.error(error instanceof Error ? error.message : "预览失败");
    } finally {
      setBusy(false);
    }
  }
  async function showVersions() {
    try {
      setVersions(await getVersions(agent.id!));
    } catch (error) {
      message.error(error instanceof Error ? error.message : "读取失败");
    }
  }
  async function restore(version: number) {
    setBusy(true);
    try {
      const restored = await restoreAgent(agent.id!, version);
      baseline.current = JSON.stringify(restored);
      setAgent(restored);
      onDirty(false);
      setVersions(undefined);
      await onSaved(restored);
      message.success("已恢复到草稿，原启用版本继续生效");
    } catch (error) {
      message.error(error instanceof Error ? error.message : "恢复失败");
    } finally {
      setBusy(false);
    }
  }
  async function disable() {
    setBusy(true);
    try {
      const saved = await disableAgent(agent.id!);
      baseline.current = JSON.stringify(saved);
      setAgent(saved);
      await onSaved(saved);
      message.success("助手已停用，后续任务不再调度");
    } catch (error) {
      message.error(error instanceof Error ? error.message : "停用失败");
    } finally {
      setBusy(false);
    }
  }
  const connection = (kind: ResourceKind) => (
    <ConnectionsChooser
      kind={kind}
      agent={agent}
      resources={catalog.resources}
      update={update}
      onAdd={() => setResourceKind(kind)}
    />
  );
  return (
    <main className="management-main">
      <header className="management-header">
        <div>
          <Button type="text" icon={<ArrowLeftOutlined />} onClick={onBack}>
            返回对话
          </Button>
          <span className="panel-kicker">AGENT SETTINGS</span>
          <h2>
            {agent.name || "创建你的助手"}{" "}
            <Tag>{statusLabels[initial.status || "draft"]}</Tag>
          </h2>
          <p>
            {agent.version
              ? `启用版本 v${agent.version} · 草稿修订 ${agent.revision}`
              : "完善行为和能力配置，让主 Agent 知道何时调用它。"}
            {agent.has_changes ? " · 草稿有未启用的修改" : ""}
          </p>
        </div>
        <div className="management-actions">
          <Button
            icon={<PlayCircleOutlined />}
            onClick={() => {
              try {
                checkEditors();
                setTest(true);
              } catch (error) {
                message.error((error as Error).message);
              }
            }}
          >
            测试助手
          </Button>
          <Button
            icon={<SaveOutlined />}
            loading={busy}
            onClick={() => void save()}
          >
            保存草稿
          </Button>
          <Button type="primary" loading={busy} onClick={() => void save(true)}>
            保存并启用
          </Button>
        </div>
      </header>
      <div className="management-content" ref={editorRef}>
        <Tabs
          activeKey={tab}
          onChange={setTab}
          items={[
            {
              key: "basic",
              label: "基本设置",
              children: (
                <div className="settings-stack">
                  <section className="settings-card">
                    <h3>定义助手的角色</h3>
                    <div className="field-grid">
                      <label>
                        助手名称
                        <Input
                          aria-label="助手名称"
                          value={agent.name}
                          maxLength={60}
                          onChange={(e) => update({ name: e.target.value })}
                        />
                      </label>
                      <label>
                        图标
                        <Select
                          value={agent.icon}
                          options={[
                            { value: "research", label: "网络研究" },
                            { value: "database", label: "数据分析" },
                            { value: "knowledge", label: "知识问答" },
                            { value: "spark", label: "通用助手" },
                          ]}
                          onChange={(icon) => update({ icon })}
                        />
                      </label>
                    </div>
                    <label className="form-label">
                      能力描述 · 主 Agent 调度依据
                      <Input.TextArea
                        aria-label="能力描述"
                        rows={4}
                        value={agent.description}
                        placeholder="擅长什么、哪些任务应该调用它、适用范围是什么"
                        onChange={(e) =>
                          update({ description: e.target.value })
                        }
                      />
                    </label>
                    <label className="form-label">
                      模型名称
                      <Input
                        aria-label="助手模型名称"
                        value={agent.model_name}
                        placeholder="留空继承 .env 中主 Agent 的模型配置"
                        onChange={(e) => update({ model_name: e.target.value })}
                      />
                    </label>
                  </section>
                  <section className="settings-card">
                    <h3>内置工具</h3>
                    <p>
                      勾选助手可以使用的实际工具；外部能力在知识库、Skills 和
                      MCP 页签中连接。
                    </p>
                    <Checkbox.Group
                      className="builtin-tool-grid"
                      value={agent.builtin_tools}
                      options={catalog.builtin_tools.map((tool) => ({
                        value: tool.id,
                        label: tool.name,
                      }))}
                      onChange={(values) =>
                        update({ builtin_tools: values as string[] })
                      }
                    />
                  </section>
                  <section className="settings-card">
                    <h3>版本与状态</h3>
                    <p>
                      草稿不会改变主 Agent
                      的调度行为；保存并启用后，对后续任务生效。
                    </p>
                    <div className="management-actions">
                      <Button icon={<CopyOutlined />} onClick={onCopy}>
                        复制为新助手
                      </Button>
                      <Button
                        icon={<HistoryOutlined />}
                        disabled={!agent.version}
                        onClick={() => void showVersions()}
                      >
                        历史版本
                      </Button>
                      <Button
                        danger
                        disabled={!agent.enabled}
                        loading={busy}
                        onClick={() =>
                          Modal.confirm({
                            title: "停用这个助手？",
                            content:
                              "正在运行的任务继续使用原配置，后续任务不再调度它。",
                            onOk: disable,
                          })
                        }
                      >
                        停用助手
                      </Button>
                    </div>
                  </section>
                </div>
              ),
            },
            {
              key: "prompt",
              label: "提示词",
              children: (
                <div className="settings-stack">
                  <section className="settings-card">
                    <div className="settings-heading">
                      <div>
                        <h3>编辑系统提示词</h3>
                        <p>
                          写清角色、目标、工作步骤与约束，完整指令可直接查看和修改。
                        </p>
                      </div>
                      <Select
                        aria-label="插入提示词变量"
                        placeholder="插入变量"
                        value={null}
                        style={{ minWidth: 150 }}
                        options={[
                          ...new Set([
                            ...agent.input_fields.map((field) => field.name),
                            "query",
                            "files",
                            "output_format",
                          ]),
                        ].map((name) => ({
                          value: name,
                          label: `{{${name}}}`,
                        }))}
                        onChange={(name) =>
                          update({
                            system_prompt:
                              agent.system_prompt + `\n{{${name}}}`,
                          })
                        }
                      />
                    </div>
                    <Input.TextArea
                      aria-label="系统提示词"
                      className="prompt-input"
                      value={agent.system_prompt}
                      rows={16}
                      onChange={(e) =>
                        update({ system_prompt: e.target.value })
                      }
                    />
                  </section>
                  <section className="settings-card">
                    <h3>生效预览</h3>
                    <p>
                      用示例输入查看最终组装的提示词，包括输入输出约束、资源说明和系统工作规则。
                    </p>
                    <Input.TextArea
                      aria-label="预览示例输入"
                      className="code-input"
                      rows={3}
                      value={sample}
                      onChange={(e) => setSample(e.target.value)}
                    />
                    <Button loading={busy} onClick={() => void showPreview()}>
                      生成生效预览
                    </Button>
                    {preview && <pre className="prompt-preview">{preview}</pre>}
                  </section>
                </div>
              ),
            },
            {
              key: "io",
              label: "输入输出",
              children: <IOEditor agent={agent} update={update} />,
            },
            {
              key: "knowledge",
              label: "知识库",
              children: connection("knowledge"),
            },
            { key: "skill", label: "Skills", children: connection("skill") },
            { key: "mcp", label: "MCP", children: connection("mcp") },
          ]}
        />
      </div>
      {resourceKind && (
        <ResourceForm
          kind={resourceKind}
          onClose={() => setResourceKind(undefined)}
          onSaved={(resource) => {
            if (resource.kind === "skill")
              update({
                skill_ids: [...new Set([...agent.skill_ids, resource.id])],
              });
            if (
              resource.kind === "knowledge" &&
              !agent.knowledge.some((item) => item.resource_id === resource.id)
            )
              update({
                knowledge: [
                  ...agent.knowledge,
                  { resource_id: resource.id, chat_ids: [] },
                ],
              });
            if (
              resource.kind === "mcp" &&
              !agent.mcp.some((item) => item.resource_id === resource.id)
            )
              update({
                mcp: [...agent.mcp, { resource_id: resource.id, tools: [] }],
              });
            void onRefresh();
          }}
        />
      )}
      {test && <TestDrawer agent={agent} onClose={() => setTest(false)} />}
      {versions && (
        <Modal
          open
          title="历史启用版本"
          footer={null}
          onCancel={() => setVersions(undefined)}
        >
          {versions.map((version) => (
            <div className="version-row" key={version.version}>
              <div>
                <strong>v{version.version}</strong>
                <p>{new Date(version.created_at).toLocaleString()}</p>
              </div>
              <Button
                loading={busy}
                onClick={() =>
                  Modal.confirm({
                    title: `恢复 v${version.version} 到草稿？`,
                    content: "当前草稿将被替换，启用版本保持不变。",
                    onOk: () => restore(version.version),
                  })
                }
              >
                恢复到草稿
              </Button>
            </div>
          ))}
        </Modal>
      )}
      {!agent.id && (
        <Alert
          className="new-agent-note"
          type="info"
          message="新助手先保存为草稿，再测试并启用；资源连接可以稍后完善。"
        />
      )}
    </main>
  );
}
