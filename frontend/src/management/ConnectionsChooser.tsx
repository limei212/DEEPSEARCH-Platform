import { PlusOutlined } from "@ant-design/icons";
import { Alert, Button, Checkbox, Empty, Select, Tag } from "antd";
import type { AgentConfig, Resource, ResourceKind } from "./types";
import { kindLabels, statusLabels } from "./types";

export function ConnectionsChooser({
  kind,
  agent,
  resources,
  update,
  onAdd,
}: {
  kind: ResourceKind;
  agent: AgentConfig;
  resources: Resource[];
  update: (patch: Partial<AgentConfig>) => void;
  onAdd: () => void;
}) {
  const items = resources.filter((resource) => resource.kind === kind);
  const isSelected = (id: string) =>
    kind === "skill"
      ? agent.skill_ids.includes(id)
      : kind === "knowledge"
        ? agent.knowledge.some((item) => item.resource_id === id)
        : agent.mcp.some((item) => item.resource_id === id);
  function toggle(id: string, checked: boolean) {
    if (kind === "skill")
      update({
        skill_ids: checked
          ? [...agent.skill_ids, id]
          : agent.skill_ids.filter((value) => value !== id),
      });
    if (kind === "knowledge")
      update({
        knowledge: checked
          ? [...agent.knowledge, { resource_id: id, chat_ids: [] }]
          : agent.knowledge.filter((value) => value.resource_id !== id),
      });
    if (kind === "mcp")
      update({
        mcp: checked
          ? [...agent.mcp, { resource_id: id, tools: [] }]
          : agent.mcp.filter((value) => value.resource_id !== id),
      });
  }
  return (
    <section className="settings-card">
      <div className="settings-heading">
        <div>
          <h3>连接{kindLabels[kind]}</h3>
          <p>
            {kind === "knowledge"
              ? "选择服务及其中的聊天助手，查询范围以所选助手关联的知识库为准。"
              : kind === "skill"
                ? "选择可加载的技能指令，脚本和附属资料可以查看，脚本不会自动执行。"
                : "选择服务，再勾选允许这个助手调用的具体工具。"}
          </p>
        </div>
        <Button icon={<PlusOutlined />} onClick={onAdd}>
          新增{kindLabels[kind]}
        </Button>
      </div>
      {!items.length && (
        <Empty
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          description="尚无资源，先新增一个连接"
        />
      )}
      <div className="connection-list">
        {items.map((resource) => (
          <div
            className={`connection-card ${isSelected(resource.id) ? "connection-card--selected" : ""}`}
            key={resource.id}
          >
            <div className="settings-heading">
              <Checkbox
                checked={isSelected(resource.id)}
                onChange={(e) => toggle(resource.id, e.target.checked)}
              >
                <strong>{resource.name}</strong>
              </Checkbox>
              <Tag color={resource.status === "ready" ? "success" : "default"}>
                {statusLabels[resource.status]}
              </Tag>
            </div>
            <p>{resource.description || resource.message}</p>
            {isSelected(resource.id) && resource.status !== "ready" && (
              <Alert
                type="warning"
                showIcon
                message="资源尚未连接成功，可保存草稿；启用前请到资源中心测试连接。"
              />
            )}
            {isSelected(resource.id) && kind === "knowledge" && (
              <label className="form-label">
                RAGFlow 聊天助手
                <Select
                  mode="multiple"
                  placeholder="选择允许查询的助手"
                  value={
                    agent.knowledge.find(
                      (item) => item.resource_id === resource.id,
                    )?.chat_ids
                  }
                  options={(resource.discovery.chats || []).map((chat) => ({
                    value: chat.id,
                    label:
                      chat.name +
                      " · " +
                      (chat.datasets.join("、") || "未绑定知识库"),
                  }))}
                  onChange={(chat_ids) =>
                    update({
                      knowledge: agent.knowledge.map((item) =>
                        item.resource_id === resource.id
                          ? { ...item, chat_ids }
                          : item,
                      ),
                    })
                  }
                />
              </label>
            )}
            {isSelected(resource.id) && kind === "skill" && (
              <>
                <div className="resource-meta">
                  版本 {resource.config.version || "1.0"} · 附属文件{" "}
                  {Object.keys(resource.config.files || {}).length} 个
                </div>
                <details className="skill-source">
                  <summary>查看 SKILL.md 与附属文件</summary>
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
                {!!resource.config.required_tools?.length && (
                  <Alert
                    type="info"
                    message={
                      "所需工具：" + resource.config.required_tools.join("、")
                    }
                  />
                )}
              </>
            )}
            {isSelected(resource.id) && kind === "mcp" && (
              <div className="tool-choice-list">
                {(resource.discovery.tools || []).map((tool) => (
                  <div key={tool.name}>
                    <Checkbox
                      checked={agent.mcp
                        .find((item) => item.resource_id === resource.id)
                        ?.tools.includes(tool.name)}
                      onChange={(e) =>
                        update({
                          mcp: agent.mcp.map((item) =>
                            item.resource_id === resource.id
                              ? {
                                  ...item,
                                  tools: e.target.checked
                                    ? [...item.tools, tool.name]
                                    : item.tools.filter(
                                        (name) => name !== tool.name,
                                      ),
                                }
                              : item,
                          ),
                        })
                      }
                    >
                      <strong>{tool.name}</strong>
                    </Checkbox>
                    <p>{tool.description}</p>
                    <details>
                      <summary>输入参数</summary>
                      <pre>{JSON.stringify(tool.inputSchema, null, 2)}</pre>
                    </details>
                  </div>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </section>
  );
}
