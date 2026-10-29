<p align="center">
  <img src="assets/embedded-ddd.svg" alt="embedded-ddd — Deploy 部署 · Diagnostics 诊断 · Debug 调试" width="100%">
</p>

<p align="center">
  <strong>Deploy · Diagnostics · Debug</strong><br>
  从部署到诊断、调试，让 AI 参与完整的嵌入式 Linux 开发过程。
</p>

<p align="center">
  <a href="README.md">English</a> ·
  <a href="#快速开始">快速开始</a> ·
  <a href="#ddd-的工作方式">DDD 的工作方式</a> ·
  <a href="INSTALL.md">安装说明</a> ·
  <a href="LICENSE">MIT 许可证</a>
</p>

**embedded-ddd** 为 Codex 提供三项相互衔接的嵌入式开发技能。告诉 AI 设备地址和要完成的任务，它会通过 SSH、Telnet 或串口，结合项目已有工具完成部署、定位故障，并检查程序运行状态。

## DDD 的工作方式

DDD 表示 **Deploy（部署）、Diagnostics（诊断）、Debug（调试）**。部署时开始观察，用日志和状态缩小问题范围，再针对具体疑点进入调试，最后回到设备验证修复结果。可以从当前任务需要的任何一步开始。

| 阶段 | 解决的问题 | 技能 |
| --- | --- | --- |
| **Deploy · 部署** | 调用已有安装工具，采集部署前后的日志，核对实际运行的程序 | [embedded-linux-deploy](skills/embedded-linux-deploy/SKILL.md) |
| **Diagnostics · 诊断** | 结合串口、应用、内核日志和进程状态，找出异常发生的位置与条件 | [embedded-linux-diagnostics](skills/embedded-linux-diagnostics/SKILL.md) |
| **Debug · 调试** | 用 GDB 检查线程栈、断点、程序状态或 core 文件，并确认在线调试后的恢复 | [embedded-linux-debug](skills/embedded-linux-debug/SKILL.md) |

三项技能在同一任务中接续使用设备信息和已有证据。串口日志缺失时，继续查找其他可用日志；部署连接中断时，先核对设备实际状态；结束在线调试时，确认进程已经恢复。

## 快速开始

将下面这段话发给 Codex：

```text
请从 https://github.com/srymaker0/embedded_ddd 安装 embedded-ddd，
按照仓库中的 INSTALL.md，在当前项目中为 Codex 完成安装。
```

三个技能目录直接安装在当前项目的 `.agents/skills/` 下。也可以在项目目录执行：

```sh
npx --yes skills add srymaker0/embedded_ddd --agent codex \
  --skill embedded-linux-deploy embedded-linux-diagnostics embedded-linux-debug --copy --yes
```

默认只安装三项技能，优先使用项目已有工具；具体设备任务需要时，再安装辅助工具。工具安装、更新和卸载方法见 [INSTALL.md](INSTALL.md)。

随后在正在开发的应用项目中直接描述任务：

```text
把这次构建部署到 192.0.2.10，并检查启动日志。
```

```text
应用一直重启，帮我结合串口日志和板端日志定位原因。
```

```text
用 GDB 看一下哪些线程卡住了，查看完后解除附加，并确认进程恢复运行。
```

Codex 可以根据任务自动选择技能，也可以通过 `$embedded-linux-deploy`、`$embedded-linux-diagnostics` 或 `$embedded-linux-debug` 显式调用。

首次接入时可以说：“根据项目里的连接信息接入这块 Linux 设备，检查可以采集哪些证据，并保存可复用的本地配置。”诊断技能自带[首次接入说明和连接模板](skills/embedded-linux-diagnostics/references/first-connection.md)，会复用已知信息，补齐缺失的连接或项目事实。只有 IP 地址时，仍需从项目中确定安装工具和验收标准。

## 接入现有开发环境

继续使用已有的 SSH 别名、密钥、终端日志和部署脚本。设备信息可以来自对话、项目配置或私有的[连接配置](skills/embedded-linux-diagnostics/assets/profiles/)。

当前覆盖 **嵌入式 Linux**。调试支持板端 GDB、开发机 GDB 配合 gdbserver，以及离线 core 分析。在线调试会暂停所选进程。目前尚未覆盖 RTOS 和裸机。

### 可选命令行工具

技能优先使用开发环境中已有的工具。现有工具无法满足具体设备任务时，可按需使用 `embedded-ddd` 辅助工具，在 Linux 开发机上执行连接、传输、日志采集、部署观察和板端 GDB 快照。已有适用的运行环境时直接复用，需要另行安装时见[安装方法](INSTALL.md#command-line-tool)。

选择 [SSH](skills/embedded-linux-diagnostics/assets/profiles/ssh.json)、[Telnet](skills/embedded-linux-diagnostics/assets/profiles/telnet.json) 或[串口](skills/embedded-linux-diagnostics/assets/profiles/serial.json)配置示例，复制到私有路径并替换占位信息，然后在应用项目目录执行：

```sh
.agents/skills/.embedded-ddd/bin/embedded-ddd --profile /path/to/board.json inspect
.agents/skills/.embedded-ddd/bin/embedded-ddd --profile /path/to/board.json inspect --local --for collect
.agents/skills/.embedded-ddd/bin/embedded-ddd --profile /path/to/board.json inspect --for collect
.agents/skills/.embedded-ddd/bin/embedded-ddd --profile /path/to/board.json collect --output output/logs-001 --duration 30
.agents/skills/.embedded-ddd/bin/embedded-ddd --profile /path/to/board.json deploy --output output/deploy-001
.agents/skills/.embedded-ddd/bin/embedded-ddd --profile /path/to/board.json gdb-snapshot --pid 1234 --output output/debug-001
```

每次运行使用新的输出目录。配置可以执行其中指定的命令，应使用可信的本机配置。凭据通过 SSH 配置或单独的私有密码文件保存，分享日志前先移除私人信息。

命令连接和文件传输分别配置，文件传输支持 SFTP、SCP、SSH 文件流和 HTTP 上传，并校验 SHA256。部署沿用项目安装工具已有的升级与回滚行为。远程 GDB 和 core 分析由技能指导使用标准调试工具。

`inspect --for` 按 `connect`、`collect`、`put`、`deploy` 或 `gdb-snapshot` 检查前提条件，输出 JSON。串口日志缺失与应用日志可读会分别报告。`--local` 不连接设备，也不宣称设备已就绪。检查不会执行安装或附加调试器，输出会注明仍需通过实际操作确认的条件。

## 体验完整流程

[Linux 示例](examples/README.md)会编译小型应用，在 localhost 启动临时 SSH 服务，通过示例项目的安装工具部署两个版本，并校验哈希和心跳。随后注入工作线程阻塞，在串口文件缺失的情况下采集应用日志，用 GDB 定位阻塞位置，再验证应用恢复。结束时会停止示例应用和 SSH 服务，移除临时密钥。

```sh
.venv/bin/python examples/linux_lab.py run --output output/linux-lab-001
```

在开发仓库中完成下方环境准备后执行，无需实体板卡。示例验证的是 Linux 软件行为；真实板卡架构、串口接线、看门狗和固件更新仍需在目标设备验收。

## 开发与贡献

在用于开发 embedded-ddd 的仓库副本中创建虚拟环境，然后运行主机测试：

```sh
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e '.[console,serial]'
.venv/bin/python -m unittest discover -s tests -v
```

完整测试需要 GCC、GDB、OpenSSH 客户端与服务端、Telnet 客户端和 curl；缺少可选工具时会显示跳过。测试覆盖连接、传输、就绪检查、日志连续性、部署生命周期和调试后的恢复。CI 还会运行完整的 localhost 示例。

[真实技能评估](evals/README.md)通过四个独立 Codex 会话操作临时目标，根据工具调用记录、保存的证据和最终进程状态判断结果。它会消耗模型额度，只在明确执行时运行，与主机测试分开，CI 不会自动调用模型。其余[场景清单](evals/scenarios.json)标明了仍需人工评估的情况。

[2026-10-29 的评估记录](evals/results/2026-10-29.json)为三项通过、一项超时。首次接入的行为检查通过，但会话未在时限内结束，整体仍记为失败。

欢迎通过 [GitHub Issues](https://github.com/srymaker0/embedded_ddd/issues) 和 pull request 反馈问题或贡献改进。反馈时请提供开发机与设备环境、复现步骤，以及移除私人信息后的相关日志。

## 许可证

[MIT](LICENSE)。
