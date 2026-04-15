# docs/contracts.md 生成指南

contracts.md 记录所有跨服务的交互契约。这是其他服务负责人最需要查阅的文档。

**核心要求**：topic 名、consumerGroup 名、接口路径必须从代码中取真实值，不能写占位符或猜测值。

## 扫描要点

- 从 `@RocketMQMessageListener` 注解取 `topic`、`selectorExpression`（tag）、`consumerGroup`
- 从 MQ 发布调用取 topic 和 tag（通常是常量，去常量类找真实值）
- 从 `@FeignClient` 区分两类：本服务暴露的（`*-api` 模块）和调用外部的（`*-infrastructure/acl` 模块）
- 来源服务（哪个服务发布了这个事件）如果代码里看不出来，标注"待确认"

## 输出模板

```markdown
# 对外契约

## 消费的 MQ 事件
| 监听器类 | Tag | Topic | ConsumerGroup | 消费后的业务动作 |
|---------|-----|-------|---------------|----------------|
| {ListenerClass} | {tag-value} | {topic-name} | {group-name} | {调用了哪个 Service 方法，做了什么} |

## 发布的 MQ 事件（本服务对外发布）
| 发布类 | Tag | Topic | 触发时机 | 已知消费方 |
|--------|-----|-------|---------|----------|
| {PublisherClass} | {tag-value} | {topic-name} | {在哪个业务步骤触发} | {待确认 / 已知服务名} |

## 供其他服务调用的 SDK / Feign 接口
{如果本服务有 *-api 模块暴露了工具类或 Feign 接口，在这里描述}

| 类/接口 | 方法 | 说明 |
|--------|------|------|
| {ClassName} | {method(params)} | {用途和使用场景} |

## 依赖的外部 Feign / RPC 接口
| 客户端类 | 目标服务 | 用途 |
|---------|---------|------|
| {ClientClass} | {service-name} | {调用场景} |
```

## 多 Topic 时的组织方式

如果服务消费多个 Topic，按 Topic 分组展示，更清晰：

```markdown
## 消费的 MQ 事件

### Topic: `{topic-name-1}`（如：即时消息）
| 监听器类 | Tag | ConsumerGroup | 业务动作 |
...

### Topic: `{topic-name-2}`（如：延迟消息）
| 监听器类 | Tag | ConsumerGroup | 业务动作 |
...
```
