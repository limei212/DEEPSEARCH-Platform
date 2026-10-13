import {
  Alert,
  App,
  Button,
  Checkbox,
  Input,
  Modal,
  Select,
  Upload,
} from "antd";
import { UploadOutlined } from "@ant-design/icons";
import { useState } from "react";
import { importSkill, probeResource, saveResource } from "./api";
import { kindLabels } from "./types";
import type { Resource, ResourceKind } from "./types";

const skillTemplate =
  "---\nname: research-guide\ndescription: 按证据整理研究结论与行动建议\nversion: '1.0'\nrequired_tools: []\n---\n\n# 研究步骤\n1. 确认任务目标和资料范围。\n2. 收集证据，保留来源。\n3. 区分事实与推断。\n4. 整理结论、依据和行动建议。";

export function ResourceForm({
  kind,
  resource,
  onClose,
  onSaved,
}: {
  kind: ResourceKind;
  resource?: Resource;
  onClose: () => void;
  onSaved: (resource: Resource) => void;
}) {
  const { message } = App.useApp();
  const [savedResource, setSavedResource] = useState(resource);
  const [name, setName] = useState(resource?.name || "");
  const [description, setDescription] = useState(resource?.description || "");
  const [config, setConfig] = useState<Resource["config"]>(
    resource?.config ||
      (kind === "skill"
        ? {
            content: skillTemplate,
            version: "1.0",
            files: {},
            required_tools: [],
          }
        : kind === "knowledge"
          ? { url: "" }
          : { transport: "http", url: "", args: [] }),
  );
  const [secret, setSecret] = useState("");
  const [clearSecret, setClearSecret] = useState(false);
  const [busy, setBusy] = useState(false);
  const [probe, setProbe] = useState<Resource>();
  const patch = (values: Partial<Resource["config"]>) => {
    setConfig((previous) => ({ ...previous, ...values }));
    setProbe(undefined);
  };
  async function save(test = false) {
    setBusy(true);
    try {
      if (!name.trim()) throw new Error("请填写资源名称");
      const result = await saveResource({
        id: savedResource?.id,
        revision: savedResource?.revision || 0,
        kind,
        name,
        description,
        config,
        ...(secret ? { secret } : {}),
        clear_secret: clearSecret,
      });
      const saved = test ? await probeResource(result.id) : result;
      setSavedResource(saved);
      setConfig(saved.config);
      setSecret("");
      setClearSecret(false);
      if (test) setProbe(saved);
      onSaved(saved);
      message.success(
        test
          ? saved.status === "ready"
            ? "连接成功"
            : "已保存，连接测试未通过"
          : "资源已保存",
      );
      if (!test) onClose();
    } catch (error) {
      message.error(error instanceof Error ? error.message : "保存失败");
    } finally {
      setBusy(false);
    }
  }
  return (
    <Modal
      open
      title={`${resource ? "编辑" : "新增"}${kindLabels[kind]}`}
      width={760}
      onCancel={() => {
        if (!busy) onClose();
      }}
      footer={
        <>
          <Button disabled={busy} onClick={onClose}>
            取消
          </Button>
          {kind !== "skill" && (
            <Button loading={busy} onClick={() => void save(true)}>
              保存并测试连接
            </Button>
          )}
          <Button type="primary" loading={busy} onClick={() => void save()}>
            保存资源
          </Button>
        </>
      }
    >
      <div className="settings-stack resource-form">
        {kind === "skill" && (
          <Upload
            accept=".md,.zip"
            showUploadList={false}
            beforeUpload={(file) => {
              setBusy(true);
              void importSkill(file)
                .then((saved) => {
                  message.success("技能包已导入");
                  onSaved(saved);
                  onClose();
                })
                .catch((error) => message.error(error.message))
                .finally(() => setBusy(false));
              return false;
            }}
          >
            <Button icon={<UploadOutlined />} disabled={busy}>
              导入 SKILL.md / ZIP
            </Button>
          </Upload>
        )}
        <label className="form-label">
          资源名称
          <Input
            aria-label="资源名称"
            value={name}
            onChange={(e) => setName(e.target.value)}
            maxLength={100}
          />
        </label>
        <label className="form-label">
          说明
          <Input.TextArea
            aria-label="资源说明"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={2}
          />
        </label>
        {kind === "mcp" && (
          <label className="form-label">
            连接方式
            <Select
              value={config.transport}
              options={[
                { value: "http", label: "远程 HTTP" },
                { value: "sse", label: "远程 SSE" },
                { value: "stdio", label: "本地 stdio" },
              ]}
              onChange={(transport) => patch({ transport })}
            />
          </label>
        )}
        {kind !== "skill" &&
          (config.transport !== "stdio" ? (
            <>
              <label className="form-label">
                {kind === "knowledge" ? "RAGFlow 服务地址" : "MCP 服务地址"}
                <Input
                  aria-label="服务地址"
                  placeholder={
                    kind === "knowledge"
                      ? "http://127.0.0.1:9380"
                      : "https://example.com/mcp"
                  }
                  value={config.url}
                  onChange={(e) => patch({ url: e.target.value })}
                />
              </label>
              <label className="form-label">
                API Key / Bearer Token
                <Input.Password
                  aria-label="资源 API Key"
                  autoComplete="new-password"
                  value={secret}
                  onChange={(e) => {
                    setSecret(e.target.value);
                    setProbe(undefined);
                  }}
                  placeholder={
                  savedResource?.has_secret
                      ? "已保存，留空保持原值"
                      : "按服务要求填写；无认证服务可留空"
                  }
                />
              </label>
              {config.secret_env && (
                <p className="resource-meta">
                  当前从后端环境变量 {config.secret_env} 读取认证配置。
                </p>
              )}
            {savedResource?.has_secret && (
                <Checkbox
                  checked={clearSecret}
                  onChange={(e) => setClearSecret(e.target.checked)}
                >
                  清除已保存的认证配置
                </Checkbox>
              )}
            </>
          ) : (
            <>
              <label className="form-label">
                启动命令
                <Input
                  aria-label="MCP 启动命令"
                  value={config.command}
                  placeholder="例如 python、node 或 npx"
                  onChange={(e) => patch({ command: e.target.value })}
                />
              </label>
              <label className="form-label">
                启动参数（每行一个）
                <Input.TextArea
                  aria-label="MCP 启动参数"
                  value={(config.args || []).join("\n")}
                  rows={4}
                  onChange={(e) =>
                    patch({ args: e.target.value.split("\n").filter(Boolean) })
                  }
                />
              </label>
              <Alert
                type="info"
                showIcon
                message="点击测试或运行助手时，后端会启动这里配置的本地 MCP 程序。命令需要在运行项目的电脑上可用。"
              />
            </>
          ))}
        {kind === "skill" && (
          <>
            <label className="form-label">
              版本
              <Input
                value={config.version}
                onChange={(e) => patch({ version: e.target.value })}
              />
            </label>
            <label className="form-label">
              所需工具（逗号分隔）
              <Input
                value={(config.required_tools || []).join(",")}
                onChange={(e) =>
                  patch({
                    required_tools: e.target.value
                      .split(",")
                      .map((item) => item.trim())
                      .filter(Boolean),
                  })
                }
              />
            </label>
            <label className="form-label">
              SKILL.md
              <Input.TextArea
                aria-label="SKILL.md 内容"
                className="code-input"
                rows={12}
                value={config.content}
                onChange={(e) => patch({ content: e.target.value })}
              />
            </label>
            {!!Object.keys(config.files || {}).length && (
              <p className="resource-meta">
                附属文件：{Object.keys(config.files || {}).join("、")}
              </p>
            )}
          </>
        )}
        {probe && (
          <Alert
            showIcon
            type={probe.status === "ready" ? "success" : "error"}
            message={probe.message}
          />
        )}
      </div>
    </Modal>
  );
}
