# 安全说明

Daybreak 依赖用户自己配置的 DeepSeek API Key。请勿把 API Key 提交到仓库、写进日志或在公开渠道分享。

如果发现安全漏洞，请不要公开讨论，先通过私有渠道联系维护者；在修复发布前避免透露细节。

本地单用户模式下数据仅保存在程序同目录的 `planagent.db`，请自行做好备份。

## 代码签名

官方发布的桌面包默认未签名：Windows 首次运行时可能提示“未知发布者”，macOS 可能提示“无法验证开发者”。这不影响程序本身的安全，属于操作系统对新发布软件的常规拦截。

维护者（或自行 fork 发布的人）可以在仓库设置中配置签名 secrets 后重新构建，构建工作流会自动跳过未配置的签名步骤：

- macOS：`AC_CERTIFICATE_BASE64`（Developer ID 证书 p12 的 Base64）、`AC_P12_PASSWORD`、`APPLE_CERT_NAME`（证书名称，如 `Developer ID Application: Example (TEAMID)`）。
- Windows（Azure 受信任签名）：`AZURE_TENANT_ID`、`AZURE_CLIENT_ID`、`AZURE_CLIENT_SECRET`、`AZURE_ENDPOINT`（如 `https://eus.codesigning.azure.net/`）、`AZURE_SIGNING_ACCOUNT`、`AZURE_CERT_PROFILE`。
- Windows（自签名证书，仅减少“未知发布者”提示，无法消除 SmartScreen）：`WINDOWS_PFX_BASE64`、`WINDOWS_PFX_PASSWORD`。

签名 secrets 属于机密信息，请勿写入日志、提交到仓库或在公开渠道分享。
