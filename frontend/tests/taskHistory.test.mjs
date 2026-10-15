import assert from "node:assert/strict";
import test from "node:test";
import { createTaskHistory, taskHistoryReducer, taskTitle } from "../src/lib/taskHistory.ts";

test("task names preserve the full question and normalize whitespace for width-based display", () => {
  const fixtures = [
    ["  请查询公司白皮书中的品类策略  ", "请查询公司白皮书中的品类策略"],
    ["整理本季度销售数据并生成报告", "整理本季度销售数据并生成报告"],
    ["😀请查询公司白皮书", "😀请查询公司白皮书"],
    ["短任务", "短任务"],
    ["abcdefghijk", "abcdefghijk"],
    ["  分析\n\t文档  风险  ", "分析 文档 风险"]
  ];
  for (const [query, expected] of fixtures) assert.equal(taskTitle(query), expected);
});

test("every sent task gets its own entry even when its first eight characters repeat", () => {
  let history = createTaskHistory("workspace-a");
  history = taskHistoryReducer(history, {
    type: "submitted", id: "first", workspaceId: "workspace-a", content: "请查询公司白皮书中的品类策略"
  });
  history = taskHistoryReducer(history, {
    type: "submitted", id: "second", workspaceId: "workspace-a", content: "请查询公司白皮书中的库存策略"
  });
  assert.deepEqual(history.tasks.map(({ id, title }) => ({ id, title })), [
    { id: "second", title: "请查询公司白皮书中的库存策略" },
    { id: "first", title: "请查询公司白皮书中的品类策略" }
  ]);
  assert.equal(history.activeTaskId, "second");
});

test("restoring old eight-character titles derives complete names from saved questions", () => {
  const content="请查询公司白皮书中的品类策略";
  let history=createTaskHistory("draft");
  history=taskHistoryReducer(history,{type:"restore",tasks:[{id:"old",workspaceId:"chat",content,title:"请查询公司白皮书"}]});
  assert.equal(history.tasks[0].title,content);
  history=taskHistoryReducer(history,{type:"restore",tasks:[]});
  assert.equal(history.tasks[0].title,content);
});

test("new task opens an empty workspace and keeps previously sent tasks available", () => {
  let history = createTaskHistory("workspace-a");
  history = taskHistoryReducer(history, {
    type: "submitted", id: "first", workspaceId: "workspace-a", content: "查询品类策略"
  });
  history = taskHistoryReducer(history, { type: "new", workspaceId: "workspace-b" });
  assert.equal(history.activeWorkspaceId, "workspace-b");
  assert.equal(history.activeTaskId, null);
  assert.equal(history.tasks.length, 1);
  assert.deepEqual(history.workspaceIds, ["workspace-a", "workspace-b"]);
});

test("selecting a task restores its workspace without adding a new task", () => {
  let history = createTaskHistory("workspace-a");
  history = taskHistoryReducer(history, {
    type: "submitted", id: "first", workspaceId: "workspace-a", content: "查询品类策略"
  });
  history = taskHistoryReducer(history, { type: "new", workspaceId: "workspace-b" });
  history = taskHistoryReducer(history, {
    type: "submitted", id: "second", workspaceId: "workspace-b", content: "分析库存变化"
  });
  history = taskHistoryReducer(history, { type: "select", taskId: "first" });
  assert.equal(history.activeWorkspaceId, "workspace-a");
  assert.equal(history.activeTaskId, "first");
  assert.deepEqual(history.tasks.map(({ id }) => id), ["second", "first"]);
});

test("repeated new task clicks discard unused drafts without creating task entries", () => {
  let history = createTaskHistory("empty-a");
  history = taskHistoryReducer(history, { type: "new", workspaceId: "empty-b" });
  history = taskHistoryReducer(history, { type: "new", workspaceId: "empty-c" });
  assert.deepEqual(history.workspaceIds, ["empty-c"]);
  assert.deepEqual(history.tasks, []);
});

test("blank messages do not create sidebar entries", () => {
  const history = createTaskHistory("workspace-a");
  const next = taskHistoryReducer(history, {
    type: "submitted", id: "blank", workspaceId: "workspace-a", content: "  \n "
  });
  assert.equal(next.tasks.length, 0);
  assert.equal(next.activeTaskId, null);
});

test("restoring saved tasks keeps existing tasks and mounts only the selected workspace", () => {
  let history = createTaskHistory("draft");
  const tasks = Array.from({length:123}, (_,i)=>({id:`task-${i}`,workspaceId:`chat-${i}`,content:`问题${i}`,title:`问题${i}`}));
  history = taskHistoryReducer(history,{type:"restore",tasks,selectedTaskId:"task-10"});
  assert.equal(history.tasks.length,123);
  assert.equal(history.activeTaskId,"task-10");
  assert.deepEqual(history.workspaceIds,["draft","chat-10"]);
  history = taskHistoryReducer(history,{type:"restore",tasks:tasks.slice(0,50)});
  assert.equal(history.tasks.length,123);
});

test("opening a saved older task lazily adds its workspace", () => {
  let history=createTaskHistory("draft");
  history=taskHistoryReducer(history,{type:"restore",tasks:[{id:"old",workspaceId:"old-chat",content:"历史问题",title:"历史问题"}]});
  history=taskHistoryReducer(history,{type:"select",taskId:"old"});
  assert.deepEqual(history.workspaceIds,["draft","old-chat"]);
  assert.equal(history.activeWorkspaceId,"old-chat");
});
