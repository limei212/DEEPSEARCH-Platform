import { DeleteOutlined, PlusOutlined } from "@ant-design/icons";
import { Button, Checkbox, Input, Select } from "antd";
import { useState } from "react";
import type { AgentConfig, InputField, Schema } from "./types";

export function JsonEditor({
  value,
  onChange,
  label,
}: {
  value: Schema;
  onChange: (value: Schema) => void;
  label: string;
}) {
  const [text, setText] = useState(JSON.stringify(value, null, 2));
  const [error, setError] = useState("");
  return (
    <div className="json-editor">
      <Input.TextArea
        aria-label={label}
        className="code-input"
        rows={10}
        value={text}
        onChange={(e) => {
          setText(e.target.value);
          try {
            const parsed = JSON.parse(e.target.value);
            if (!parsed || Array.isArray(parsed) || typeof parsed !== "object")
              throw new Error();
            onChange(parsed);
            setError("");
          } catch {
            setError("请输入有效的 JSON 对象；修正前不能保存或测试。");
          }
        }}
      />
      {error && (
        <div className="field-error" role="alert">
          {error}
        </div>
      )}
    </div>
  );
}

export function IOEditor({
  agent,
  update,
}: {
  agent: AgentConfig;
  update: (patch: Partial<AgentConfig>) => void;
}) {
  const updateField = (index: number, patch: Partial<InputField>) =>
    update({
      input_fields: agent.input_fields.map((field, i) =>
        i === index ? { ...field, ...patch } : field,
      ),
    });
  return (
    <div className="settings-stack">
      <section className="settings-card">
        <div className="settings-heading">
          <div>
            <h3>输入字段</h3>
            <p>
              主 Agent 会按这些字段下发任务，必填项和字段类型会在运行前校验。
            </p>
          </div>
          <Select
            aria-label="输入配置方式"
            value={agent.input_schema ? "schema" : "fields"}
            options={[
              { value: "fields", label: "可视化字段" },
              { value: "schema", label: "JSON Schema" },
            ]}
            onChange={(v) =>
              update({
                input_schema:
                  v === "schema"
                    ? {
                        type: "object",
                        properties: { query: { type: "string" } },
                        required: ["query"],
                      }
                    : null,
              })
            }
          />
        </div>
        {agent.input_schema ? (
          <JsonEditor
            key={agent.id + "input" + agent.revision}
            label="输入 JSON Schema"
            value={agent.input_schema}
            onChange={(input_schema) => update({ input_schema })}
          />
        ) : (
          <>
            {agent.input_fields.map((field, index) => (
              <div className="input-field-card" key={index}>
                <div className="field-grid">
                  <label>
                    字段名称
                    <Input
                      aria-label={`字段名称 ${index + 1}`}
                      value={field.name}
                      onChange={(e) =>
                        updateField(index, { name: e.target.value })
                      }
                    />
                  </label>
                  <label>
                    字段类型
                    <Select
                      value={field.type}
                      options={[
                        "string",
                        "number",
                        "boolean",
                        "array",
                        "object",
                      ].map((value) => ({ value, label: value }))}
                      onChange={(type) => updateField(index, { type })}
                    />
                  </label>
                  <label>
                    输入来源
                    <Select
                      value={field.source}
                      options={[
                        { value: "query", label: "任务问题" },
                        { value: "files", label: "任务附件" },
                        { value: "context", label: "任务上下文" },
                        { value: "manual", label: "主 Agent 提供" },
                      ]}
                      onChange={(source) => updateField(index, { source })}
                    />
                  </label>
                </div>
                <div className="field-grid">
                  <label>
                    字段说明
                    <Input
                      value={field.description}
                      onChange={(e) =>
                        updateField(index, { description: e.target.value })
                      }
                    />
                  </label>
                  <label>
                    默认值（JSON）
                    <Input
                      defaultValue={
                        field.default === null
                          ? ""
                          : JSON.stringify(field.default)
                      }
                      placeholder='例如 "电商"、3、[]'
                      onChange={(e) => {
                        try {
                          e.target.removeAttribute("data-invalid");
                          updateField(index, {
                            default: e.target.value
                              ? JSON.parse(e.target.value)
                              : null,
                          });
                        } catch {
                          e.target.setAttribute("data-invalid", "true");
                        }
                      }}
                    />
                  </label>
                  <label>
                    可选值（文本，逗号分隔）
                    <Input
                      value={field.enum.join(",")}
                      onChange={(e) =>
                        updateField(index, {
                          enum: e.target.value
                            .split(",")
                            .map((v) => v.trim())
                            .filter(Boolean),
                        })
                      }
                    />
                  </label>
                </div>
                <div className="field-row">
                  <Checkbox
                    checked={field.required}
                    onChange={(e) =>
                      updateField(index, { required: e.target.checked })
                    }
                  >
                    必填
                  </Checkbox>
                  <Button
                    danger
                    type="text"
                    icon={<DeleteOutlined />}
                    onClick={() =>
                      update({
                        input_fields: agent.input_fields.filter(
                          (_, i) => i !== index,
                        ),
                      })
                    }
                  >
                    删除字段
                  </Button>
                </div>
              </div>
            ))}
            <Button
              icon={<PlusOutlined />}
              onClick={() =>
                update({
                  input_fields: [
                    ...agent.input_fields,
                    {
                      name: `field_${agent.input_fields.length + 1}`,
                      type: "string",
                      required: false,
                      description: "",
                      source: "manual",
                      default: null,
                      enum: [],
                    },
                  ],
                })
              }
            >
              添加输入字段
            </Button>
          </>
        )}
      </section>
      <section className="settings-card">
        <h3>返回结果</h3>
        <p>结果交给主 Agent 汇总；选择 JSON 时，返回内容会按 Schema 校验。</p>
        <label className="form-label">
          输出格式
          <Select
            value={agent.output_format}
            options={[
              { value: "text", label: "自然语言" },
              { value: "markdown", label: "Markdown" },
              { value: "json", label: "结构化 JSON" },
            ]}
            onChange={(output_format) => update({ output_format })}
          />
        </label>
        {agent.output_format === "json" && (
          <JsonEditor
            key={agent.id + "output" + agent.revision}
            label="输出 JSON Schema"
            value={agent.output_schema}
            onChange={(output_schema) => update({ output_schema })}
          />
        )}
        <label className="form-label">
          必需标题 / JSON 字段
          <Input.TextArea
            rows={3}
            placeholder="每行一个，例如：结论、依据、行动建议"
            value={agent.required_sections.join("\n")}
            onChange={(e) =>
              update({ required_sections: e.target.value.split("\n") })
            }
            onBlur={() =>
              update({
                required_sections: agent.required_sections
                  .map((item) => item.trim())
                  .filter(Boolean),
              })
            }
          />
        </label>
      </section>
      <section className="settings-card">
        <h3>交付文件</h3>
        <p>需要文件时，请在基本设置中连接生成 Markdown、转换 PDF 工具。</p>
        <Checkbox.Group
          value={agent.artifacts}
          options={[
            { value: "markdown", label: "Markdown 文件" },
            { value: "pdf", label: "PDF 文件" },
          ]}
          onChange={(values) =>
            update({ artifacts: values as AgentConfig["artifacts"] })
          }
        />
      </section>
    </div>
  );
}
