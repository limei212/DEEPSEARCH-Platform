import {
  ArrowLeftOutlined,
  EditOutlined,
  PlusOutlined,
  ReloadOutlined,
} from "@ant-design/icons";
import { App, Button, Empty, Input, Tabs, Tag } from "antd";
import { useState } from "react";
import { probeResource } from "./api";
import { ResourceForm } from "./ResourceForm";
import { kindLabels, statusLabels } from "./types";
import type { Resource, ResourceKind } from "./types";

export function ResourceCenter({
  resources,
  onRefresh,
  onBack,
}: {
  resources: Resource[];
  onRefresh: () => Promise<void>;
  onBack: () => void;
}) {
  const { message } = App.useApp();
  const [kind, setKind] = useState<ResourceKind>("knowledge");
  const [search, setSearch] = useState("");
  const [editing, setEditing] = useState<Resource | "new" | null>(null);
  const [probing, setProbing] = useState("");
  async function test(resource: Resource) {
    setProbing(resource.id);
    try {
      const saved = await probeResource(resource.id);
      await onRefresh();
      message[saved.status === "ready" ? "success" : "error"](saved.message);
    } catch (error) {
      message.error(error instanceof Error ? error.message : "连接失败");
    } finally {
      setProbing("");
    }
  }
  const filtered = resources.filter(
    (resource) =>
      resource.kind === kind &&
      (resource.name + resource.description)
        .toLowerCase()
        .includes(search.toLowerCase()),
  );
  return (
    <main className="management-main">
      <header className="management-header">
        <div>
          <Button type="text" icon={<ArrowLeftOutlined />} onClick={onBack}>
            返回对话
          </Button>
          <span className="panel-kicker">RESOURCE CENTER</span>
          <h2>连接资源，让能力协同</h2>
          <p>知识库、技能与工具统一管理，可供多个助手连接使用。</p>
        </div>
        <Button
          type="primary"
          icon={<PlusOutlined />}
          onClick={() => setEditing("new")}
        >
          新增{kindLabels[kind]}
        </Button>
      </header>
      <div className="management-content">
        <Tabs
          activeKey={kind}
          onChange={(key) => setKind(key as ResourceKind)}
          items={Object.entries(kindLabels).map(([key, label]) => ({
            key,
            label,
          }))}
        />
        <Input.Search
          aria-label="搜索资源"
          placeholder="搜索资源名称或说明"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="resource-search"
        />
        {!filtered.length && (
          <div className="settings-card">
            <Empty
              image={Empty.PRESENTED_IMAGE_SIMPLE}
              description="还没有资源，新增一个连接开始"
            />
          </div>
        )}
        <div className="resource-grid">
          {filtered.map((resource) => (
            <article className="settings-card resource-card" key={resource.id}>
              <div className="settings-heading">
                <h3>{resource.name}</h3>
                <Tag
                  color={
                    resource.status === "ready"
                      ? "success"
                      : resource.status === "error"
                        ? "error"
                        : "default"
                  }
                >
                  {statusLabels[resource.status]}
                </Tag>
              </div>
              <p>{resource.description || "暂无说明"}</p>
              <div className="resource-meta">
                {kind === "skill"
                  ? `版本 ${resource.config.version || "1.0"}`
                  : kind === "mcp"
                    ? resource.config.transport
                    : resource.config.url}
              </div>
              <div
                className={`connection-message ${resource.status === "error" ? "connection-message--error" : ""}`}
              >
                {resource.message}
              </div>
              {kind === "knowledge" && !!resource.discovery.chats?.length && (
                <details>
                  <summary>
                    {resource.discovery.chats.length} 个聊天助手与关联知识库
                  </summary>
                  {resource.discovery.chats.map((chat) => (
                    <p key={chat.id}>
                      {chat.name} · {chat.datasets.join("、") || "未关联知识库"}
                    </p>
                  ))}
                </details>
              )}
              {kind === "mcp" && !!resource.discovery.tools?.length && (
                <details>
                  <summary>
                    {resource.discovery.tools.length} 个可用工具
                  </summary>
                  {resource.discovery.tools.map((tool) => (
                    <div className="tool-description" key={tool.name}>
                      <strong>{tool.name}</strong>
                      <p>{tool.description}</p>
                      <pre>{JSON.stringify(tool.inputSchema, null, 2)}</pre>
                    </div>
                  ))}
                </details>
              )}
              {kind === "skill" && (
                <details className="skill-source">
                  <summary>查看技能内容与附属文件</summary>
                  <pre>{resource.config.content}</pre>
                  {Object.entries(resource.config.files || {}).map(
                    ([path, content]) => (
                      <details key={path}>
                        <summary>{path}</summary>
                        <pre>{content}</pre>
                      </details>
                    ),
                  )}
                </details>
              )}
              <footer className="field-row">
                <Button
                  icon={<EditOutlined />}
                  onClick={() => setEditing(resource)}
                >
                  编辑
                </Button>
                <Button
                  icon={<ReloadOutlined />}
                  loading={probing === resource.id}
                  onClick={() => void test(resource)}
                >
                  {kind === "skill" ? "校验技能" : "测试 / 刷新连接"}
                </Button>
              </footer>
            </article>
          ))}
        </div>
      </div>
      {editing && (
        <ResourceForm
          key={editing === "new" ? kind : editing.id + editing.revision}
          kind={kind}
          resource={editing === "new" ? undefined : editing}
          onClose={() => setEditing(null)}
          onSaved={(saved) => {
            setEditing(saved);
            void onRefresh();
          }}
        />
      )}
    </main>
  );
}
