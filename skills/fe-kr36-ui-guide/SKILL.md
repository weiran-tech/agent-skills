---
name: lc-kr36-ui-guide
description: kr36-ui 组件库 API 参考指南。kr36-ui 是对 TDesign Vue Next 的深度封装组件库，用于氪金兽（Kejinshou）系列项目。当涉及 kr36-ui 组件使用、KrForm schema 配置、KrTable 列定义、KrDialog 弹窗、KrCard 布局等场景时，必须加载此技能获取准确的 Props/Slots/Events 文档。适用于所有使用 kr36-ui 的项目（backend-kejinshou、h5-nuxt、kejinshou_m 等）。当你在写 Vue 页面并使用 Kr* 前缀组件、配置 KrForm schema、渲染 KrTable columns 时，都应该参考此技能。
---

# kr36-ui 组件库 API 参考

kr36-ui 是对 TDesign Vue Next v1.9 的深度封装组件库，为氪金兽（Kejinshou）系列项目提供统一的 UI 组件。所有组件均以 `Kr` 前缀命名，底层透传 TDesign 属性，同时收窄 API 以保持项目一致性。

**源码位置：** `/Users/gaochunfa/project/project_develop/kr36-ui`

---

## 1. KrCard 卡片容器

对 TDesign `t-card` 的封装，提供统一的内容容器样式。

**Props：**

| 名称 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| title | `string` | `''` | 卡片标题 |
| subtitle | `string` | `''` | 副标题 |
| description | `string` | `''` | 描述文字 |
| bordered | `boolean` | `true` | 是否显示外边框 |
| size | `small \| medium \| large` | `medium` | 内边距尺寸 |
| headerBordered | `boolean` | `true` | 头部和内容区之间是否显示分割线 |
| hoverShadow | `boolean` | `true` | 鼠标悬浮时是否添加投影 |
| loading | `boolean` | `false` | 加载状态，开启时内容区显示骨架屏 |

**Slots：**

| 名称 | 说明 |
|------|------|
| default | 卡片内容区域（Body） |
| actions | 头部右侧操作区，通常放按钮 |
| footer | 底部区域 |

**布局结构：**
```
┌─────────────────────────────────────────┐
│  Header（title/subtitle/#actions）       │
├─────────────────────────────────────────┤
│  Body（default 插槽）                    │
├─────────────────────────────────────────┤
│  Footer（#footer 插槽，可选）             │
└─────────────────────────────────────────┘
```

若 `title`、`subtitle`、`description`、`#actions` 全部为空，头部区域不渲染。

---

## 2. KrForm 动态表单

对 TDesign `t-form` 的封装，通过 `schema` 配置驱动表单渲染，无需手写大量 template。

**Props：**

| 名称 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| schema | `Record<string, SchemaItem>` 或 `SchemaItem[]` | `{}` | 表单字段配置 |
| rules | `Record<string, any[]>` | `{}` | 校验规则（async-validator 格式），key 与 schema 的 `prop` 对应 |
| labelAlign | `left \| right \| top` | `right` | 标签对齐方式 |
| labelWidth | `string \| number` | `0` | 标签宽度，`0` 时自动计算 |
| layout | `vertical \| inline` | `vertical` | 表单布局，`inline` 时所有字段行内排列 |
| readonly | `boolean` | `false` | 整个表单只读 |
| scrollToFirstError | `'' \| smooth \| auto` | `''` | 校验失败后自动滚动到第一个错误字段 |
| submit | `(data: Record<string, any>) => void` | — | 校验通过后的提交回调 |
| reset | `() => void` | — | 重置完成后的回调 |

**SchemaItem 配置项：**

```typescript
interface SchemaItem {
    component: string       // 子组件名（见下方「支持的 component 值」）
    prop: string            // 绑定到表单数据的字段名
    label?: string          // 字段标签文字
    help?: string           // 标签旁帮助提示文字
    default?: any           // 字段初始值，优先级高于组件默认值
    props?: Record<string, any>        // 透传给子组件的 props
    methods?: Record<string, Function> // 透传给子组件的事件
    show?: boolean | ((item, modelValue) => boolean)    // 控制字段显示/隐藏
    disable?: boolean | ((item, modelValue) => boolean) // 控制字段禁用
    visible?: boolean       // 同 show（兼容旧版），show 优先级更高
    event?: (item, modelValue) => void  // 点击事件
}
```

**支持的 component 值（不区分大小写）：**

| component 值 | 对应组件 | 默认初始值 |
|-------------|---------|----------|
| `Input` | KrInput | `''` |
| `Select` | KrSelect | `''`（multiple 时为 `[]`） |
| `Radio` | KrRadio | `''` |
| `Checkbox` | KrCheckbox | `[]` |
| `Switch` | KrSwitch | `false` |
| `DatePicker` | KrDatePicker | `''`（range 时为 `[]`） |
| `TimePicker` | KrTimePicker | `''` |
| `Textarea` / `textarea` | KrTextarea | `''` |
| `Upload` | KrUpload | `[]` |
| `Upload2` | KrUpload2 | `[]` |
| `Editor` | KrEditor | `''` |
| `Choose` | KrChoose | 根据 type 不同 |
| `Dropdown` | KrDropdown | `''` |
| `Button` | KrButton | `''` |

> **不存在 `DateRangePicker`**，日期范围必须用 `DatePicker` + `range: true`
> **不存在 `InputNumber`**，数字输入必须用 `Input` + `type: 'number'`
> **不存在 `title`/`Image`/`Time` 等表单组件**，schema 中只能使用上表列出的 component 值，否则运行时抛异常

**Slots：**

| 名称 | 说明 |
|------|------|
| default | 表单底部插槽，通常放提交/重置按钮 |

**工作原理：**
1. 遍历 schema，为每个字段根据 component 类型确定初始值
2. 渲染时通过 `show` 函数决定是否显示，`disable` 函数决定是否禁用
3. 提交时执行 `t-form.validate()`，校验通过后调用 `submit(modelValue)` 回调
4. 重置时将每个字段还原为初始值，然后调用 `reset()` 回调

**联动函数签名（show / disable）：**
```typescript
(item: SchemaItem, modelValue: Record<string, any>) => boolean
```

**默认值规则：**
- 多选 Select `default` 必须为 `[]`
- Checkbox `default` 必须为 `[]`
- DatePicker `range: true` 时 `default` 必须为 `[]`
- Upload/Upload2 `default` 必须为 `[]`
- Choose `default` 必须为二维数组如 `[['']`]
- Switch `default` 为 `false`

---

## 3. KrTable 数据表格

对 TDesign `t-enhanced-table` 的封装，默认开启虚拟滚动。

**Props：**

| 名称 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| data | `Record<string, any>[]` | `[]` | 表格数据源 |
| columns | `TableColumn[]` | `[]` | 列配置 |
| rowKey | `string` | `'id'` | 行数据唯一标识字段名 |
| stripe | `boolean` | `false` | 斑马纹 |
| bordered | `boolean` | `true` | 边框 |
| hover | `boolean` | `true` | 悬浮高亮 |
| tableLayout | `auto \| fixed` | `fixed` | 表格布局算法 |
| size | `small \| medium \| large` | `small` | 行高/字体尺寸 |
| showHeader | `boolean` | `true` | 是否显示表头 |
| pagination | `TablePagination \| null` | `null` | 分页配置，`null` 不显示分页 |
| resizable | `boolean` | `false` | 是否可拖拽调整列宽 |
| lazyLoad | `boolean` | `true` | 懒加载 |
| maxHeight | `string \| number` | `0` | 最大高度，`0` 时自动计算 |
| cellEmptyContent | `string` | `'-'` | 单元格为空时的占位内容 |
| selectedRowKeys | `(string \| number)[]` | — | 已选行 key 列表（受控） |
| sort | `object \| object[]` | `[]` | 排序状态 |
| multipleSort | `boolean` | `true` | 是否多列排序 |
| editableCellState | `(params) => boolean` | — | 控制单元格是否可编辑 |
| filterValue | `Record<string, any>` | — | 列筛选值 |
| fixedRows | `[number, number]` | `[0, 0]` | 固定顶部/底部行数 |
| scroll | `TableScrollConfig` | `{ type: 'virtual', rowHeight: 48, bufferSize: 10 }` | 虚拟滚动配置 |

**TableColumn：**
```typescript
interface TableColumn {
    colKey?: string                          // 列标识，对应 data 字段名
    title?: string                           // 列表头文字
    width?: string | number                  // 列宽
    minWidth?: string | number               // 最小列宽
    fixed?: 'left' | 'right'                // 固定列
    align?: 'left' | 'center' | 'right'     // 对齐
    ellipsis?: boolean                       // 溢出省略
    sorter?: boolean                         // 是否排序
    filter?: object                          // 筛选配置
    cell?: string | ((h, { row, rowIndex }) => VNode) // 自定义渲染
    edit?: object                            // 编辑配置
}
```

**TablePagination：**
```typescript
interface TablePagination {
    current?: number         // 当前页，默认 1
    pageSize?: number        // 每页条数，默认 10
    total?: number           // 总条数
    showJumper?: boolean     // 跳页输入框
    pageSizeOptions?: number[] // 每页条数可选项
}
```

**注意：**
- `cellEmptyContent` 默认 `'-'`，纯展示字段无需写 `cell` 函数
- 分页为受控模式，需监听 `@page-change` 事件更新 `pagination.current`
- `maxHeight=0` 自动计算高度（视口高度 - 表格偏移量）

---

## 4. KrDialog 对话框

对 TDesign `t-dialog` 的封装，采用回调函数模式。

**Props：**

| 名称 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| visible | `boolean` | `false` | 是否显示（受控） |
| title | `string` | `''` | 标题（与 header 二选一，header 优先） |
| header | `string` | `''` | 自定义头部内容 |
| width | `string \| number` | `'50%'` | 宽度 |
| placement | `top \| center` | `top` | 垂直位置 |
| top | `string \| number` | `'5%'` | 距顶部距离 |
| confirmBtn | `string \| object \| null` | `'确认'` | 确认按钮，`null` 不显示 |
| cancelBtn | `string \| object \| null` | `'取消'` | 取消按钮，`null` 不显示 |
| footer | `boolean` | `true` | 是否显示底部操作栏 |
| closeBtn | `string \| boolean` | `true` | 关闭图标 |
| closeOnOverlayClick | `boolean` | `true` | 点击遮罩是否关闭 |
| showOverlay | `boolean` | `true` | 是否显示遮罩 |
| destroyOnClose | `boolean` | `true` | 关闭时是否销毁 DOM |
| body | `string \| null` | — | 对话框文本内容 |
| confirm | `() => void` | — | 确认回调 |
| close | `() => void` | — | 关闭/取消回调 |

**Slots：**

| 名称 | 说明 |
|------|------|
| default | 对话框内容区域 |

KrDialog 不自动关闭，`confirm` 和 `close` 回调都需手动将 `visible` 设为 `false`。

---

## 5. KrButton 按钮

对 TDesign `t-button` 的封装。

**Props：**

| 名称 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| theme | `default \| primary \| danger \| warning \| success` | `primary` | 主题色 |
| variant | `base \| outline \| dashed \| text` | `base` | 按钮形式 |
| shape | `rectangle \| square \| round \| circle` | `rectangle` | 形状 |
| size | `small \| medium \| large` | `medium` | 尺寸 |
| disabled | `boolean` | `false` | 禁用 |
| ghost | `boolean` | `false` | 幽灵按钮（背景透明） |
| block | `boolean` | `false` | 块级（撑满父容器） |
| href | `string` | `''` | 设置后渲染为 `<a>` 标签 |

所有未声明属性（如 `onClick`、`loading`）透传给 TDesign `<t-button>`。

---

## 6. KrInput 输入框

对 TDesign `t-input` / `t-input-number` / `t-range-input` 的统一封装，根据 `type` 切换渲染。

**Props：**

| 名称 | 类型 | 默认值 | 适用 type | 说明 |
|------|------|--------|----------|------|
| modelValue | `string \| number` | `''` | 全部 | v-model 绑定值 |
| type | `text \| password \| number \| range` | `text` | — | 决定渲染哪种子组件 |
| placeholder | `string` | `'请输入'` | text/password | 占位文字 |
| label | `string` | `''` | text/password | 输入框左侧标签（prefix） |
| suffix | `string` | `''` | text/password | 后置文字 |
| clearable | `boolean` | `false` | text/password | 清空按钮 |
| disabled | `boolean` | `false` | 全部 | 禁用 |
| readonly | `boolean` | `false` | 全部 | 只读 |
| maxlength | `number` | — | text/password | 最大字符数 |
| showLimitNumber | `boolean` | `false` | text/password | 字数统计（需配合 maxlength） |
| size | `small \| medium \| large` | `medium` | 全部 | 尺寸 |
| status | `default \| success \| warning \| error` | `default` | text/password | 状态色 |
| align | `left \| center \| right` | `left` | text/password | 文字对齐 |
| tips | `string` | `''` | text/password | 下方提示文字 |
| autoWidth | `boolean` | `false` | text/password | 宽度自适应 |
| borderless | `boolean` | `false` | 全部 | 无边框 |
| theme | `column \| row \| normal` | `normal` | **number** | 增减按钮布局 |
| min | `number` | `-Infinity` | **number** | 最小值 |
| max | `number` | `Infinity` | **number** | 最大值 |
| format | `string[]` | `[]` | **range** | 区间格式化 |

---

## 7. KrSelect 选择器

对 TDesign `t-select` 的封装，内置虚拟滚动（默认开启）。

**Props：**

| 名称 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| modelValue | `string \| number \| (string\|number)[]` | `''` | 绑定值，多选为数组 |
| options | `SelectOption[]` | `[]` | 选项列表 |
| placeholder | `string` | `'请选择'` | 占位符 |
| multiple | `boolean` | `false` | 开启多选 |
| clearable | `boolean` | `false` | 清空按钮 |
| filterable | `boolean` | `false` | 搜索过滤 |
| disabled | `boolean` | `false` | 禁用 |
| loading | `boolean` | `false` | 加载状态 |
| size | `small \| medium \| large` | `medium` | 尺寸 |
| minCollapsedNum | `number` | `0` | 多选折叠阈值，超出显示 `+N` |
| max | `number` | `0` | 多选最大可选数，`0` 不限 |
| autoWidth | `boolean` | `false` | 宽度自适应 |
| borderless | `boolean` | `false` | 无边框 |
| scroll | `{ type?: 'lazy' \| 'virtual' }` | `{ type: 'virtual' }` | 虚拟滚动配置 |

**SelectOption：** `{ label: string, value: string | number, disabled?: boolean }`

---

## 8. KrRadio 单选框

对 TDesign `t-radio-group` 的封装。

| 名称 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| checkedValue | `string \| number \| boolean` | — | v-model:checkedValue 绑定 |
| options | `RadioOption[]` | `[]` | 选项列表 |
| variant | `outline \| primary-filled \| default-filled` | `outline` | 外观形式 |
| readonly | `boolean` | `false` | 只读 |
| allowUncheck | `boolean` | `true` | 是否允许取消选中 |

**RadioOption：** `{ label: string, value: string | number, disabled?: boolean }`

---

## 9. KrCheckbox 多选框

对 TDesign `t-checkbox-group` 的封装。

| 名称 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| checkedValue | `(string \| number)[]` | `[]` | v-model:checkedValue 绑定 |
| options | `CheckboxOption[]` | `[]` | 选项列表 |
| readonly | `boolean` | `false` | 只读 |

**CheckboxOption：** `{ label: string, value: string | number, disabled?: boolean }`

---

## 10. KrSwitch 开关

对 TDesign `t-switch` 的封装。

| 名称 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| modelValue | `boolean` | `false` | v-model 绑定 |
| size | `small \| medium \| large` | `medium` | 尺寸 |
| loading | `boolean` | `false` | 加载状态 |
| label | `[string, string]` | `['', '']` | 文字标签 `[开启文字, 关闭文字]` |
| beforeChange | `() => Promise<boolean> \| boolean` | — | 切换前钩子，可异步阻止切换 |

---

## 11. KrTextarea 多行文本

对 TDesign `t-textarea` 的封装。

| 名称 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| modelValue | `string` | `''` | v-model 绑定 |
| placeholder | `string` | `'请输入内容'` | 占位文字 |
| autosize | `boolean \| { minRows, maxRows }` | `{ minRows: 3, maxRows: 5 }` | 高度自适应 |
| disabled | `boolean` | `false` | 禁用 |
| readonly | `boolean` | `false` | 只读 |
| maxlength | `string \| number` | — | 最大字符数 |
| status | `default \| success \| warning \| error` | `default` | 状态色 |
| tips | `string` | `''` | 下方提示文字 |

---

## 12. KrDatePicker 日期选择器

对 TDesign `t-date-picker` / `t-date-range-picker` 的封装。

| 名称 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| modelValue | `string \| number \| string[] \| Date` | `''` | 日期值，范围模式为 `[start, end]` |
| mode | `year \| quarter \| month \| week \| date` | `date` | 选择粒度 |
| format | `string` | `'YYYY-MM-DD'` | 日期格式 |
| placeholder | `string \| string[]` | `'请选择日期'` | 占位符 |
| label | `string` | `''` | 输入框左侧标签 |
| range | `boolean` | `false` | 是否范围选择模式 |
| enableTimePicker | `boolean` | `false` | 是否显示时间选择面板 |
| time | `boolean` | `true` | 范围模式下自动补全时间（起始 00:00:00，结束 23:59:59） |
| clearable | `boolean` | `true` | 清空按钮 |
| allowInput | `boolean` | `true` | 允许键入日期 |
| disabled | `boolean` | `false` | 禁用 |
| disableDate | `object \| function \| Date[]` | — | 禁用日期配置 |
| size | `small \| medium \| large` | `medium` | 尺寸 |
| status | `default \| success \| warning \| error` | `default` | 状态色 |
| tips | `string` | `''` | 下方提示文字 |

---

## 13. KrTimePicker 时间选择器

对 TDesign `t-time-picker` / `t-time-range-picker` 的封装。

| 名称 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| modelValue | `string \| string[]` | `''` | 时间值，范围模式为 `[start, end]` |
| range | `boolean` | `false` | 范围模式 |
| format | `string` | `'HH:mm:ss'` | 时间格式 |
| placeholder | `string \| string[]` | `'请选择时间'` | 占位符 |
| presets | `Record<string, string>` | `{}` | 快捷预设 |
| clearable | `boolean` | `true` | 清空按钮 |
| allowInput | `boolean` | `true` | 允许键入 |
| disabled | `boolean` | `false` | 禁用 |
| readonly | `boolean` | `false` | 只读 |
| size | `small \| medium \| large` | `medium` | 尺寸 |

---

## 14. KrUpload 文件上传

对 TDesign `t-upload` 的封装。

| 名称 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| modelValue | `UploadFile[]` | `[]` | 文件列表，v-model 绑定 |
| theme | `file \| file-input \| file-flow \| image \| image-flow \| custom` | `image` | 展示风格 |
| action | `string` | — | 上传地址（与 requestMethod 二选一） |
| method | `POST \| PUT \| PATCH` | `POST` | HTTP 方法 |
| headers | `Record<string, string>` | `{}` | 请求头 |
| accept | `string` | `''` | 允许的文件类型 |
| max | `number` | `0` | 最大文件数，`0` 不限 |
| multiple | `boolean` | `true` | 多文件上传 |
| draggable | `boolean` | `false` | 拖拽上传 |
| disabled | `boolean` | `false` | 禁用 |
| placeholder | `string` | `''` | 提示文字 |
| sizeLimit | `number \| { size, unit }` | `{ size: 50, unit: 'MB' }` | 大小限制 |
| requestMethod | `(file) => Promise<{ status, response: { url } }>` | — | 自定义上传方法 |

---

## 15. KrUpload2 增强上传

在 KrUpload 基础上增加批量操作能力。Props 同 KrUpload。

**额外特性：** 图片选择勾选、全选/取消全选、批量删除、拖拽排序、全屏预览。

---

## 16. KrEditor 富文本编辑器

基于 WangEditor 封装。

| 名称 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| modelValue | `string` | `''` | HTML 内容，v-model 绑定 |
| mode | `default \| simple` | `default` | 工具栏模式 |
| toolbarConfig | `object` | `{ excludeKeys: ['emotion', 'uploadVideo'] }` | 工具栏配置 |
| editorConfig | `object` | `{ readOnly: false, autoFocus: false, scroll: true, placeholder: '请输入内容...' }` | 编辑器配置 |

---

## 17. KrChoose 聚合选择器

复合组件，通过 `type` 在多种交互模式间切换，管理"用户输入/选择多条数据"场景。

**Props：**

| 名称 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| modelValue | `any[][]` | `[]` | 数据行列表，每项为一行的列值数组 |
| type | `input \| select \| radio \| SelectAll \| InputAll \| select-input` | `input` | 交互类型 |
| options | `ChooseOption[] \| ChooseOption[][]` | `[]` | 选项（多列时为二维数组） |
| placeholder | `string \| string[]` | `''` | 占位符 |
| multiple | `boolean \| boolean[]` | `false` | 多选 |
| clearable | `boolean` | `true` | 清空按钮 |
| disabled | `boolean` | `false` | 禁用 |
| readonly | `boolean` | `false` | 只读 |
| filterable | `boolean` | `false` | 搜索 |
| minCollapsedNum | `number` | `0` | 多选折叠 |
| maxlength | `number` | — | 最大字符数 |
| maximum | `number` | `Infinity` | 最大行数 |
| length | `number` | `3` | 列数（SelectAll/InputAll） |
| draggable | `boolean` | `false` | 行拖拽排序 |
| showAll | `boolean` | `false` | 级联显示 |

**type 类型说明：**
| type | 适用场景 | 每行结构 |
|------|---------|---------|
| `input` | 自由输入多条文本 | `[text]` |
| `select` | 固定选项选多条 | `[value]` |
| `radio` | 标签+值键值对 | `[label, value]` |
| `InputAll` | 多列输入（如坐标） | `[v1, v2, ..., vN]` |
| `SelectAll` | 多列下拉（如分类） | `[v1, v2, ..., vN]` |
| `select-input` | 先选类型再填值 | `[selectVal, inputVal]` |

`modelValue` 始终是二维数组，即使只有一列也是 `[[v1], [v2]]`。

---

## 18. KrTabs 选项卡

对 TDesign `t-tabs` 的封装，额外提供搜索组合模式。

| 名称 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| active | `string \| number` | `''` | 当前激活 Tab 值 |
| list | `TabItem[]` | `[]` | 选项卡列表 |
| theme | `normal \| card` | `normal` | 风格 |
| placement | `top \| bottom \| left \| right` | `top` | Tab 栏位置 |
| size | `small \| medium \| large` | `medium` | 尺寸 |
| lazy | `boolean` | `false` | 懒加载 |
| scrollPosition | `auto \| start \| center \| end` | `center` | 滚动停留位置 |
| disabled | `boolean` | `false` | 全局禁用 |
| addable | `boolean` | `false` | 新增 Tab 按钮 |
| dragSort | `boolean` | `false` | 拖拽排序 |
| type | `string` | `''` | 非空时追加搜索 Select |
| placeholder | `string` | `'请选择或输入'` | 搜索框占位符 |

**TabItem：** `{ label: string, value: string | number, disabled?: boolean }`

**Events：** `change(value, activeInfo?: TabItem)`

---

## 19. KrDivider 分割线

对 TDesign `t-divider` 的封装。

| 名称 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| layout | `horizontal \| vertical` | `horizontal` | 方向 |
| content | `string` | — | 中间文字 |
| align | `left \| center \| right` | `center` | 文字对齐 |
| dashed | `boolean` | `false` | 虚线 |

---

## 20. KrImage 图片

对 TDesign `t-image` / `t-image-viewer` 的封装，双模式组件。

| 名称 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| type | `'view' \| string` | `'view'` | `'view'` 为预览模式，其他为普通图片 |
| src | `string \| Array \| File` | `''` | 图片地址（普通模式） |
| images | `(string \| ImageItem)[]` | `[]` | 图片列表（预览模式） |
| fit | `contain \| cover \| fill \| none \| scale-down` | `fill` | object-fit |
| shape | `circle \| round \| square` | `square` | 圆角形状 |
| alt | `string` | `'氪金兽::img'` | alt 属性 |
| lazy | `boolean` | `true` | 懒加载 |
| mode | `modal \| modeless` | `modal` | 预览弹窗模式 |
| title | `string` | `''` | 预览标题 |
| zIndex | `number` | `2000` | 层级 |

---

## 21. KrAlert 警告提示

| 名称 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| theme | `success \| info \| warning \| error` | `info` | 提示类型 |
| title | `string` | `''` | 标题 |
| message | `string` | `''` | 内容 |
| close | `boolean` | `false` | 是否显示关闭按钮 |
| maxLine | `number` | `0` | 最大行数，`0` 不限 |

---

## 22. KrLoading 加载

| 名称 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| loading | `boolean` | `false` | 是否显示 |
| text | `string` | — | 加载文字 |
| size | `string` | `medium` | 尺寸 |
| fullscreen | `boolean` | `false` | 全屏 |
| zIndex | `number` | `3500` | 层级 |
| delay | `number` | `1` | 延迟显示（ms） |

---

## 23. KrTooltip 文字提示

| 名称 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| content | `string` | — | 提示内容 |
| placement | `top \| bottom \| left \| right` 等 12 个方位 | `top` | 弹出方向 |
| trigger | `hover \| focus \| click \| context-menu` | `hover` | 触发方式 |
| showArrow | `boolean` | `true` | 是否显示箭头 |
| destroyOnClose | `boolean` | `true` | 关闭时销毁 |

---

## 24. KrDropdown 下拉菜单

| 名称 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| options | `DropdownOption[]` | `[]` | 选项列表 |
| trigger | `hover \| click \| focus \| context-menu` | `hover` | 触发方式 |
| click | `function \| null` | — | 点击回调 |
| width | `number` | `100` | 宽度 |
| height | `number` | `300` | 最大高度 |
| hideAfterItemClick | `boolean` | `true` | 点击后收起 |
| disabled | `boolean` | `false` | 禁用 |

**DropdownOption：** `{ content, value, disabled?, divider?, children? }`

---

## 25. KrPopconfirm 确认弹窗

| 名称 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| content | `string` | — | 确认文字 |
| theme | `string` | `default` | 主题 |
| confirm | `function \| null` | — | 确认回调 |
| showArrow | `boolean` | `true` | 是否显示箭头 |

---

## 26. KrPagination 分页

| 名称 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| total | `number` | `0` | 总数 |
| current | `number` | `1` | 当前页 |
| pageSize | `number` | `10` | 每页条数 |
| size | `small \| medium \| large` | `medium` | 尺寸 |
| theme | `default \| simple` | `default` | 风格 |
| change | `function \| null` | — | 变化回调 |

---

## 27. KrTree 树形控件

对 TDesign `t-tree` 的封装，内置搜索过滤。

| 名称 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| height | `string` | `'200'` | 高度 |
| width | `string \| number` | `'100%'` | 宽度 |
| dataSource | `TreeNode[]` | — | 树数据 |
| defaultValue | `(string \| number)[]` | `[]` | 默认选中值 |

**Events：** `treeFunc(value, context)`

---

## 28. KrSkeleton 骨架屏

| 名称 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| loading | `boolean` | `false` | 是否显示骨架屏 |
| rowCol | `Array` | — | 骨架形状配置 |
| delay | `number` | — | 延迟显示 |
| theme | `string` | — | 主题 |

---

## 29. KrOperation 操作按钮组

表格操作列专用，超过 5 项自动折叠。

| 名称 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| row | `object` | `{}` | 当前行数据 |
| items | `OperationItem[]` | `[]` | 操作项列表 |
| click | `(data) => void` | — | 点击回调 |

**OperationItem：** `{ label, value, theme?, disabled? }`
**click 回调参数：** `{ label, value, row }`

---

## 30. KrIcon 图标组

| 名称 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| dataSource | `IconItem[] \| string[]` | `[]` | 图标数据 |
| parentValue | `object` | `{}` | 行数据 |
| count | `number` | `10` | 最大显示数 |
| dropList | `boolean` | `false` | 超出时折叠下拉 |

**Events：** `iconFunc(data)`

---

## 31. KrAction 操作图标组

| 名称 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| dataSource | `ActionItem[]` | `[]` | 操作项列表 |
| parentValue | `object` | `{}` | 行数据 |
| count | `number` | `10` | 最大直接显示数 |

**Events：** `iconAction(data)`

---

## 32. KrGather 聚合树

左侧树导航 + 右侧内容区域布局。

| 名称 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| title | `string` | `''` | 左侧面板标题 |
| data | `any[]` | — | 静态树数据（与 request 二选一） |
| actived | `any[]` | `[]` | 默认选中节点 |
| request | `string` | `''` | 远程数据接口地址 |
| params | `object` | `{}` | 请求参数 |
| maxHeight | `string \| number` | `'100vh'` | 最大高度 |

**Events：** `treeChange(data)`
**Slots：** default（右侧内容区域）

---

## 33. KrList / KrListItem / KrListItemMeta 列表

对 TDesign `t-list` 的封装。

**KrList Props：**
| 名称 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| split | `boolean` | `false` | 显示分割线 |
| stripe | `boolean` | `false` | 斑马纹 |

---

## 34. KrDescriptions 描述列表

对 TDesign `t-descriptions` 的封装。

---

## 35. 其他辅助组件

- **KrRow / KrCol**：TDesign 栅格布局封装
- **KrLayout**：布局容器
- **KrDrawer**：抽屉组件
- **KrNotification**：通知组件
- **KrIconFont**：图标字体
- **KrGameTable / KrGameTree / KrGameTabs**：游戏业务专用变体

---

## 36. KrForm schema 常用示例

```js
// ── Input 文本输入 ─────────────────────────────────────────────
{ component: 'Input', label: '名称', prop: 'name', default: '',
  props: { placeholder: '请输入', clearable: true, maxlength: 50 } }

// Input 数字类型（底层渲染 t-input-number）
{ component: 'Input', label: '权重', prop: 'weight', default: '',
  props: { type: 'number', placeholder: '请输入' } }

// Input 带前后缀文字
{ component: 'Input', label: '天数', prop: 'days', default: '',
  props: { type: 'number', prefix: '最近', suffix: '天' } }

// ── Select 下拉选择 ───────────────────────────────────────────
// 基础静态选项
{ component: 'Select', label: '状态', prop: 'status', default: undefined,
  props: { clearable: true, placeholder: '请选择', options: [{ label: '是', value: 1 }, { label: '否', value: 0 }] } }

// 可搜索 + 动态选项
{ component: 'Select', prop: 'launchKfId',
  props: { clearable: true, filterable: true, placeholder: '上架客服', options: launchKfList } }

// 多选 + 折叠显示
{ component: 'Select', prop: 'reasonList',
  props: { filterable: true, multiple: true, minCollapsedNum: 1, clearable: true,
           placeholder: '请选择', options: optionList } }

// ── Textarea 多行文本 ─────────────────────────────────────────
{ component: 'Textarea', prop: 'remark', default: '',
  props: { placeholder: '请输入备注' } }

// ── DatePicker 日期 ───────────────────────────────────────────
// 单日期
{ component: 'DatePicker', label: '日期', prop: 'date', default: '',
  props: { clearable: true, placeholder: '请选择日期' } }

// 日期范围（range: true）
{ component: 'DatePicker', label: '时间范围', prop: 'dateRange', default: [],
  props: { clearable: true, range: true, placeholder: ['开始时间', '结束时间'] } }

// ── Radio 单选 ────────────────────────────────────────────────
{ component: 'Radio', label: '类型', prop: 'type', default: '0',
  props: { options: [{ label: '类型A', value: '0' }, { label: '类型B', value: '1' }] } }

// ── Checkbox 多选 ─────────────────────────────────────────────
{ component: 'Checkbox', label: '范围', prop: 'scope', default: [],
  props: { options: [{ label: '选项A', value: 'a' }, { label: '选项B', value: 'b' }] } }

// ── Switch 开关 ───────────────────────────────────────────────
{ component: 'Switch', label: '启用', prop: 'enabled', default: false,
  props: { customValue: [1, 0] } }

// ── Upload 图片上传 ───────────────────────────────────────────
{ component: 'Upload', label: '图片', prop: 'image',
  default: get(row, 'image', '') ? [{ url: get(row, 'image', '') }] : [],
  props: { max: 1, accept: 'image/*', sizeLimit: { size: 50, unit: 'MB' }, requestMethod } }

// ── Choose 聚合选择器 ─────────────────────────────────────────
{ component: 'Choose', label: '标签', prop: 'tags', default: [['']],
  props: { type: 'input', placeholder: '请输入', maxlength: 20 } }

// ── Editor 富文本 ─────────────────────────────────────────────
{ component: 'Editor', label: '详情', prop: 'content', default: get(row, 'content', '') }

// ── show 条件显示 ─────────────────────────────────────────────
{
    component: 'Input', prop: 'extra',
    props: { placeholder: '请输入' },
    show: (item, modelValue) => modelValue.type === '1',
}

// ── disable 条件禁用 ──────────────────────────────────────────
{
    component: 'Input', prop: 'code',
    props: { placeholder: '请输入编码' },
    disable: (item, modelValue) => modelValue.locked === true,
}
```

---

## 共享类型

```typescript
type ComponentSize = 'small' | 'medium' | 'large'
type ComponentStatus = 'default' | 'success' | 'warning' | 'error'
type ComponentAlign = 'left' | 'center' | 'right'
type ComponentVariant = 'base' | 'outline' | 'dashed' | 'text'
type ComponentTheme = 'default' | 'primary' | 'danger' | 'warning' | 'success'
```
