# 诊断前端与 DSL runtime 的 retry 合同

本次只读核对基线：`runtime.c` 的 `publish()`、`begin_generation()`、主循环，以及修复前 `m77-dsl-diagnostics/diagnostics.c` 的 `rpc_call("retry")`。本文不修改前端或运行服务。

## 最小正确客户端

1. 以真实 root 凭证调用；在 root0700 的 `mkdtemp()` 目录中创建唯一客户端路径。建立 `AF_UNIX/SOCK_DGRAM|SOCK_CLOEXEC` socket，**先 bind 客户端路径，再 chmod0600**。每次 RPC 使用一个新 socket，仅保留一个未完成请求，最终只清理自己的路径和目录。
2. 客户端可设置 `SO_PASSCRED` 并 `connect()` 到 `/var/run/ponwrt-dsl-control.sock`，使回包来自预期服务。daemon 已设置 `SO_PASSCRED`：内核自动附带发送者的 `SCM_CREDENTIALS`，无需手工伪造/附加凭证，也不可发送 `SCM_RIGHTS` 等其他控制消息。
3. 先读取当前原始 DSL 状态，确认同一启动、新鲜且 `can_retry=true`，记录当前代次；随后发送**恰好五字节** `retry`，无 NUL、换行或 JSON。`send()==5` 只证明数据报已提交，不能返回 `accepted=true`。
4. 用有限的单调时钟截止时间等待完整数据报；拒绝截断、额外字符及异常控制消息。若启用接收凭证，核对唯一 `SCM_CREDENTIALS.uid==0`；关闭任何意外接收的文件描述符。
5. 仅接受精确的 `ACK ` 加非零十进制代次，或精确 `NACK`。解析时检查范围及**整个报文长度**，不可让内嵌 NUL 或尾随字符被 `strtoull()` 静默忽略。收到合法 ACK 才返回 `accepted=true,generation=N`；这表示新尝试已开始，**不表示 DSL/认证成功**。
6. ACK 后直接读取当前原始 DSL 状态，核对同一 `boot_id`、新鲜时间及 `generation>=N`；随后刷新前端缓存。不要要求状态仍是 `running`：输入失败可在 ACK 后立即变成 `blocked`。若已经是更大代次，说明另一尝试已替代它。

| 结果 | 正确含义 |
| --- | --- |
| `ACK N` | daemon 已成功落盘新代次，然后开始尝试；网络结果仍需阶段/会话证据 |
| `NACK` | 未得到一次被确认启动的新尝试；刷新状态，不宣称连接成功 |
| 超时、断开、无效回包 | 提交结果不确定；报告未收到确认，**不可自动重发** |

协议目前没有 request-id 或去重。daemon 同步执行旧 `attempt()` 时，新请求可能排队，故 ACK 可能延迟。超时后新尝试仍可能执行；另一个客户端也可能推进代次，仅看到代次变化不能归因于自己的无 ACK 请求。

## daemon 返回路径与持久化顺序

`runtime.c:224` 的正向分支为：凭证/命令/`can_retry` 校验 → `begin_generation()` → `publish()` 的文件 `fflush/fsync`、`renameat`、目录 `fsync` 全部成功 → `sendto(ACK, recvmsg 得到的客户端地址)` → `attempt()`。写入失败不会进入硬件尝试；此处是 `/tmp` RAM 状态文件的原子发布，不是跨断电保存。

两个当前边界不能被客户端误读：

- daemon 尚未验证返回地址或检查 ACK `sendto()` 的结果。隔离 host 实测确认：**unnamed root sendto 也能推进代次，但收不到 ACK**；并非“unnamed 一定不会执行”。前端必须使用 named client，不能把成功发送当成确认。
- 若 `renameat` 成功而目录 `fsync` 失败，可能返回 NACK，但新代次文件已可见。因此 NACK 不保证代次绝对不变，代次变化也不能代替成功 ACK。

## 其他已发现的投影缺口

修复前 `diagnostics.c` 有三处与真实输出不一致：

- `project_dsl()` 仅接收 double 型 `events.uptime_s`；runtime 输出整数。应同时接受有限、非负的 int/double。
- `safe_state()` 缺少 runtime 使用的 `error`、`stopped`；应接纳或显式映射为 `failed`、`offline`，避免把释放失败显示成普通 unknown。
- `status_snapshot()` 只检查二级缓存的 `system.uptime_s`，可能延长底层 DSL 证据的有效期。ACK 后应重新投影原始 DSL 状态；普通 RPC 也应再次核对原始 `updated_uptime_s`，或携带该证据时间并独立执行30秒门禁。

`events` 可以包含较早尝试的历史；当前进度和联网判断使用当前代次的 `stages`、showtime、认证及地址证据，不能从旧事件推断成功。

## 无硬件的 root host 回归

在没有 `/dev/ponwrt-dsl` 的隔离 Linux build host 上运行，**不要在路由器上运行**：

```sh
make BUILD=/tmp/ponwrt-m77-host all test
sudo python3 host-runtime-test.py /tmp/ponwrt-m77-host/ponwrt-dsl
```

现有测试已覆盖 named root ACK、落盘代次、NACK、未知命令、非 root 凭证、意外 FD 关闭和空闲时间戳刷新；缺失固件使尝试停在输入阶段，不访问 provider。增加前端 client 的黑盒测试时，将内部 helper 的路径参数指向测试专用 socket，并检查：

- `accepted=true` 只能来自合法 root `ACK N`，且读回代次已持久化；ACK 后快速 blocked 仍属于重试已受理。
- 假服务器的 NACK、延迟/丢弃 ACK、错代次、尾随字符和截断都不能返回 accepted=true，也不能自动再发一次。
- 原始 DSL 时间已过期、但诊断缓存时间仍新鲜时，联网证据必须失效；整数事件时间和 error/stopped 映射保留。

本次额外隔离实测：named root 客户端收到 `ACK 2` 及服务端 uid0，读回 generation2；unnamed root 请求随后推进代次但没有回包。该测试只使用缺失输入和私有临时目录，硬件操作为零。
