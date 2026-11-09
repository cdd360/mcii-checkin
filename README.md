# MCII 每日自动签到

每天自动登录 https://proxy.mcii.cc ，点"签到并激活订阅"按钮，截图保存到
GitHub Actions 的 Artifacts 里。不发 Telegram，不需要机器人。

## 文件

| 文件 | 作用 |
| ---- | ---- |
| `checkin.py` | Playwright 脚本：打开网站 → 登录 → 点签到 → 处理二次确认 → 截图 |
| `.github/workflows/mcii-checkin.yml` | GitHub Actions 工作流：每天北京时间 00:30 自动跑，也可手动跑 |

## 部署步骤

### 1. 新建 GitHub 仓库

在 GitHub 上新建一个仓库（名字随便，比如 `mcii-checkin`），
把这两个文件按原样传上去（保持 `.github/workflows/` 这个目录结构）。

### 2. 加两个 Secrets

仓库页面 → **Settings** → **Secrets and variables** → **Actions** →
**New repository secret**，各加一条：

| Name | 值 |
| ---- | ---- |
| `MCII_EMAIL` | 登录邮箱 |
| `MCII_PASSWORD` | 登录密码 |

密码只存在 GitHub Secrets 里，代码里没有任何明文，
也不要把密码发到聊天记录里。

### 3. 手动跑一次测试

仓库页面 → **Actions** → 左边选 **MCII 每日签到** →
**Run workflow** → **Run workflow**，等 1-2 分钟看结果：

- 绿勾 = 成功，点进那次运行，底部的 **Artifacts** 里下载
  `checkin-screenshot`，能看到签到成功的截图。
- 红叉 = 失败，点进去看日志最后几行（会写失败原因），
  失败截图 `error.png` 也在 Artifacts 里。

### 4. 之后就不用管了

每天北京时间 00:30 自动跑一次。失败时 Actions 页面会显示红叉，
GitHub 默认也会给仓库所有者发失败提醒邮件。

## 费用

一次运行约 1-2 分钟，一个月约 30-60 分钟。
私有仓库每月免费额度 2000 分钟，够用；公开仓库 Actions 不计费。

## 常见问题

- **登录失败**：先确认 Secrets 里的邮箱密码没输错；
  再看失败截图，可能是网站改版导致登录框找不到了。
- **按钮文字变了**：网站改版后签到按钮改名，脚本找不到按钮会失败，
  把新的按钮文字告诉小茶，改一行选择器就行。
- **提示"今日已签到"**：当天已经签到过，脚本点的是"已签到 · 激活续期"，
  同样会续期订阅，也算成功。
- **二次确认**：签到有时会弹确认框（比如部分节点不可用），脚本会自动点确认。
