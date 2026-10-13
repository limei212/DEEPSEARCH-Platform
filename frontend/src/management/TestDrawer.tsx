import { App, Alert, Button, Drawer, Input, Upload } from "antd";
import { UploadOutlined } from "@ant-design/icons";
import { useState } from "react";
import { testAgent } from "./api";
import { getDownloadUrl, uploadSessionFiles } from "../lib/api";
import { createThreadId } from "../lib/thread";
import { MarkdownRenderer } from "../components/MarkdownRenderer";
import type { AgentConfig, TestResult } from "./types";

export function TestDrawer({
  agent,
  onClose,
}: {
  agent: AgentConfig;
  onClose: () => void;
}) {
  const { message } = App.useApp();
  const [threadId] = useState(createThreadId);
  const [values, setValues] = useState(
    JSON.stringify(
      Object.fromEntries(
        agent.input_fields.map((field) => [
          field.name,
          field.default ??
            (field.type === "array"
              ? []
              : field.type === "number"
                ? 0
                : field.type === "boolean"
                  ? false
                  : field.type === "object"
                    ? {}
                    : field.source === "query"
                      ? "请分析本季度品类策略"
                      : ""),
        ]),
      ),
      null,
      2,
    ),
  );
  const [result, setResult] = useState<TestResult>();
  const [busy, setBusy] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [files, setFiles] = useState<string[]>([]);
  async function run() {
    setBusy(true);
    setResult(undefined);
    try {
      const payload = JSON.parse(values);
      if (!payload || Array.isArray(payload) || typeof payload !== "object")
        throw new Error("测试输入需要是 JSON 对象");
      setResult(await testAgent(agent, payload, threadId));
    } catch (error) {
      message.error(error instanceof Error ? error.message : "测试失败");
    } finally {
      setBusy(false);
    }
  }
  return (
    <Drawer
      title={"测试助手 · " + (agent.name || "新助手")}
      open
      width={560}
      onClose={onClose}
      maskClosable={!busy}
      closeIcon={busy ? null : undefined}
    >
      <div className="settings-stack">
        <Alert
          type="info"
          message="测试当前草稿，不改变启用版本。运行会调用已配置的模型与资源。"
        />
        <label className="form-label">
          测试输入（JSON）
          <Input.TextArea
            aria-label="测试输入"
            className="code-input"
            value={values}
            onChange={(e) => setValues(e.target.value)}
            rows={7}
          />
        </label>
        <Upload
          showUploadList={false}
          beforeUpload={(file) => {
            setUploading(true);
            void uploadSessionFiles([file], threadId)
              .then(() => {
                setFiles((previous) => [...previous, file.name]);
                message.success("测试附件已上传");
              })
              .catch((error) => message.error(error.message))
              .finally(() => setUploading(false));
            return false;
          }}
        >
          <Button icon={<UploadOutlined />} loading={uploading} disabled={busy}>
            上传测试附件
          </Button>
        </Upload>
        {!!files.length && (
          <p className="resource-meta">附件：{files.join("、")}</p>
        )}
        <Button
          type="primary"
          loading={busy}
          disabled={uploading}
          onClick={() => void run()}
        >
          运行测试
        </Button>
        {busy && (
          <p className="resource-meta" role="status">
            正在执行草稿测试，请等待模型和工具返回结果…
          </p>
        )}
        {result && (
          <>
            <Alert
              showIcon
              type={result.status === "success" ? "success" : "error"}
              message={
                result.status === "success" ? "输出校验通过" : result.message
              }
            />
            {result.result !== undefined && (
              <section className="settings-card">
                <h3>最终输出</h3>
                {typeof result.result === "string" ? (
                  <MarkdownRenderer content={result.result} />
                ) : (
                  <pre>{JSON.stringify(result.result, null, 2)}</pre>
                )}
              </section>
            )}
            <section className="settings-card">
              <h3>执行记录 · 草稿修订 {agent.revision}</h3>
              {result.events.length === 0 ? (
                <p>尚未产生工具调用记录。</p>
              ) : (
                result.events.map((event, index) => (
                  <details key={index}>
                    <summary>{event.message}</summary>
                    <pre>{JSON.stringify(event.data, null, 2)}</pre>
                  </details>
                ))
              )}
            </section>
            {!!result.files.length && (
              <section className="settings-card">
                <h3>交付文件</h3>
                {result.files.map((file) => (
                  <p key={file.path}>
                    <a
                      href={getDownloadUrl(file.path)}
                      target="_blank"
                      rel="noreferrer"
                    >
                      {file.name}
                    </a>
                  </p>
                ))}
              </section>
            )}
          </>
        )}
      </div>
    </Drawer>
  );
}
