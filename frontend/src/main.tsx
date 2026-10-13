import "antd/dist/reset.css";
import { App as AntApp, ConfigProvider, theme } from "antd";
import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "./styles.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <ConfigProvider
      theme={{
        algorithm: theme.defaultAlgorithm,
        token: {
          colorPrimary: "#0f766e",
          colorSuccess: "#168062",
          colorWarning: "#a66a16",
          colorError: "#c83e55",
          colorInfo: "#5964bd",
          colorBgBase: "#f4f7fa",
          colorBgContainer: "#ffffff",
          colorBorder: "#dbe4eb",
          colorText: "#243446",
          colorTextSecondary: "#627386",
          borderRadius: 8,
          fontFamily:
            "'IBM Plex Sans', 'PingFang SC', 'Microsoft YaHei', system-ui, sans-serif",
          fontFamilyCode:
            "'JetBrains Mono', 'SFMono-Regular', Consolas, 'Liberation Mono', monospace"
        },
        components: {
          Button: {
            controlHeightLG: 46,
            primaryShadow: "0 4px 12px rgba(15, 118, 110, 0.16)"
          },
          Input: {
            activeBorderColor: "#0f766e",
            hoverBorderColor: "#168062"
          }
        }
      }}
    >
      <AntApp>
        <App />
      </AntApp>
    </ConfigProvider>
  </React.StrictMode>
);
