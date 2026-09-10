# JZ-NNU-course-grabber

南京师范大学选课系统抢课脚本 —— 纯 Python 实现的本地选课工具，支持按课程名 / 老师 / 课程号智能检索，以及定时 / 监控 / 立即三种抢课模式。

[![Python](https://img.shields.io/badge/Python-3.8%2B-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

> ⚠️ **免责声明**
>
> 本项目仅供**学习与研究**网络请求、加密算法与自动化技术之用。使用本脚本抢课可能违反学校选课管理规定，并存在账号被限制的风险。
>
> - 请**遵守**所在学校的选课规章制度，理性使用；
> - 请勿用于恶意抢占课程资源、扰乱选课秩序等行为；
> - 使用者需自行承担由此产生的一切后果与责任，项目作者不承担任何责任。

## ✨ 特性

- **人工验证码登录**：登录时弹出验证码图片，手动输入一次即可
- **智能课程检索**：输入课程名 / 老师 / 课程号任意组合，自动检索并本地精确匹配教学班（搜不到时自动拉全量兜底）
- **三种抢课模式**：
  - `now` 立即抢 —— 进入即多线程高频提交
  - `timer` 定时抢 —— 设目标时间，到点自动开抢（适合正选开抢瞬间）
  - `monitor` 监控抢 —— 轮询余量，一有余量立即抢（适合捡漏/补选）
- **多线程并发 + 失败自动重试 + 成功播报**

## 🚀 快速开始

### 第一步：下载项目

```bash
git clone https://github.com/1113878425-alt/JZ-NNU-course-grabber.git
cd JZ-NNU-course-grabber
```

> 也可以直接在 GitHub 页面点 **Code → Download ZIP** 解压。

### 第二步：运行（三种方式，任选其一）

#### 方式一：一键脚本（最省事，推荐）

脚本会自动检测 Python、创建虚拟环境、安装依赖、启动程序，**无需手动配置环境**。

- **Windows**：双击 `run.bat`（或在命令行执行 `run.bat`）
- **macOS / Linux**：

  ```bash
  chmod +x run.sh
  ./run.sh
  ```

#### 方式二：uv 一行命令（无需手动安装 Python）

[uv](https://github.com/astral-sh/uv) 会自动下载 Python、创建环境、装依赖：

```bash
# 安装 uv（只需一次）
pip install uv          # 或 curl -LsSf https://astral.sh/uv/install.sh | sh

# 一行运行
uv run main.py
```

#### 方式三：手动安装（传统方式）

```bash
pip install -r requirements.txt
python main.py
```

> **国内网络慢？** 用清华镜像源加速：
> `pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple`

### 第三步：按提示操作

启动后按提示输入学号、密码、验证码，选择轮次后，脚本会**逐个询问**要抢的课程：

1. 输入 **课程名**（可留空）、**老师**（可留空）、**课程号**（可留空），至少填一项；
2. 脚本检索并列出所有匹配的教学班（课程名 / 课程号 / 教师 / 时间地点 / 余量 / 教学班ID，已满的标注【已满】）；
3. 手动勾选要抢的教学班编号（可多选，如 `1,3`）；
4. 可继续添加下一门，或输入 `n` 结束添加；
5. 选择抢课模式开始抢课。

### 环境要求

- Python 3.8+（用方式二 uv 时无需自行安装）

## ⚙️ 配置

脚本支持通过 `config.json` 预填账号、目标课程与抢课参数，实现无人值守定时抢课。

首次使用请复制模板：

```bash
cp config.example.json config.json
```

然后编辑 `config.json`：

```json
{
  "username": "你的学号",
  "password": "你的密码",
  "teaching_class_type": "XGXK",
  "targets": [
    { "name": "中国传统文化", "tc_id": "教学班ID", "campus": "" }
  ],
  "grab": {
    "mode": "timer",
    "start_time": "2026-09-10 13:29:58",
    "max_workers": 5,
    "retry_interval": 0.3,
    "max_retries": 300,
    "monitor_interval": 2
  }
}
```

> **注意**：`config.json` 含账号密码，已被 `.gitignore` 排除，请勿提交到仓库。

### 配置字段说明

| 字段 | 说明 |
|---|---|
| `teaching_class_type` | 课程类型：`XGXK` 校公选课、`FANKC` 方案内课程 |
| `targets[].tc_id` | 教学班ID（预填则跳过检索，留空走交互式检索） |
| `grab.mode` | `timer` 定时 / `monitor` 监控 / `now` 立即 |
| `grab.max_workers` | 并发线程数（建议 3-8，过高易触发风控） |
| `grab.retry_interval` | 失败重试间隔（秒） |
| `grab.max_retries` | 最大重试轮数 |
| `grab.monitor_interval` | 监控模式轮询余量间隔（秒） |

## 📁 项目结构

```
.
├── main.py              # 主程序（交互 + 检索 + 抢课逻辑）
├── nnu_client.py        # 登录 / 选课接口封装（含自动重试）
├── des.py               # 前端 3DES 加密算法的 Python 复刻
├── run.bat / run.sh     # 一键启动脚本（自动装依赖）
├── test_fixes.py        # 回归测试（加密 / 余量 / 抢课循环）
├── config.example.json  # 配置模板
├── requirements.txt     # 依赖清单
├── LICENSE              # MIT 许可证
└── README.md
```

## 🧪 测试

```bash
python test_fixes.py
```

覆盖：加密正确性（与前端原 JS 交叉验证）、余量计算、抢课循环下标与重试、网络层重试配置。

## ⚠️ 注意事项

1. **验证码**：登录时脚本会弹出验证码图片，看清输入即可；若为点选式验证码（少见），请改用浏览器登录。
2. **token 有效期**：登录后 token 一般可用一段时间；若抢课中提示登录失效，需重新运行脚本登录。
3. **合规**：请遵守学校选课管理规定，理性使用，避免对服务器造成过大压力，注意账号安全。
4. **网络重试**：脚本内置自动重试（HTTP 层 3 次 + 抢课循环 300 轮），网络抖动不会导致脚本崩溃。

## 📄 许可证

[MIT](LICENSE) © 2026 JustinZ
