# yuan_autosign — ycoo.net 自动签到

通过 GitHub Actions 每天定时登录 [ycoo.net](https://ycoo.net)（Discuz! `k_misign` 签到插件）自动签到。脚本仅使用 Python 标准库，无需安装任何依赖。

## 使用步骤

### 1. 配置 Secrets

仓库页面 → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**，添加：

| Secret 名称 | 必填 | 说明 |
|---|---|---|
| `YCOO_USERNAME` | ✅ | 论坛用户名 |
| `YCOO_PASSWORD` | ✅ | 论坛密码 |
| `YCOO_QUESTION_ID` | ❌ | 安全提问编号（未设置安全提问则不填） |
| `YCOO_ANSWER` | ❌ | 安全提问答案 |

安全提问编号对照：`1`=母亲的名字，`2`=爷爷的名字，`3`=父亲出生的城市，`4`=您其中一位老师的名字，`5`=您个人计算机的型号，`6`=您最喜欢的餐馆名称，`7`=驾驶执照的最后四位数字。

> ⚠️ 如果站点开启了登录验证码，此方案不可用（脚本无法自动识别验证码）；目前测试登录接口未强制验证码。

### 2. 运行

- **自动运行**：工作流每天 UTC 00:30（北京时间 08:30）自动触发。注意 GitHub Actions 的 cron 有约 5–30 分钟的调度延迟，属正常现象。
- **手动运行**：仓库 → **Actions** → 选择 **ycoo auto sign** → **Run workflow**。

### 3. 查看结果

进入对应的 workflow run 查看日志：

- `[SUCCESS] 签到成功` / `[SUCCESS] 今日已签到` —— 正常
- `[FATAL] 登录失败` —— 检查 Secrets 是否正确、账号是否被站点限制
- `[FATAL] 签到失败` —— 站点签到接口可能改版，参考下方本地调试

### 本地调试

```bash
# Windows (PowerShell)
$env:YCOO_USERNAME = "你的用户名"
$env:YCOO_PASSWORD = "你的密码"
python sign.py

# Linux / macOS
YCOO_USERNAME="你的用户名" YCOO_PASSWORD="你的密码" python sign.py
```

需要走本地代理时，可在 `sign.py` 顶部按需加 `urllib.request.ProxyHandler`，或设置系统代理环境变量。

## 工作原理

1. `GET member.php?mod=logging&action=login` 拿到 cookie 与 `formhash`
2. `POST member.php?...&loginsubmit=yes` 登录（标准 Discuz 表单）
3. `GET plugin.php?id=k_misign:sign` 取签到页 `formhash`
4. 依次尝试 `k_misign` 常见签到端点（`operation=qiandao` 等），识别「签到成功 / 今日已签」

## 免责声明

仅供个人学习与自动化个人账号操作使用，请遵守目标站点的服务条款，勿用于任何商业或批量用途。
