backend-kejinshou 标准页面生成规范
生成 backend-kejinshou 项目的页面时，必须严格遵循以下规范。该项目使用 Vue 3 + TypeScript + TDesign + kr36-ui 封装组件。

1. 整体结构规范
   使用 <script setup lang="jsx">（必须是 jsx，表格列需要 JSX 渲染）
   组件优先级：优先使用 kr36-ui 封装组件（KrCard、KrForm、KrTable、KrDialog、KrButton、KrTabs），仅在封装组件无法满足时才用 tdesign 原生组件，绝不引入 ElementPlus 等其他库
   样式使用 <style lang="less" scoped>，禁止内联样式，通过 class 控制
   代码需包含清晰的中文注释
2. 核心组件规范
   外层容器

<KrCard title="页面标题">
    <template #actions>
        <!-- 操作按钮放在右上角 -->
        <KrButton v-isAuth="['kjs_backend.xxx.add']" @click="handleAdd('add', {})">新增</KrButton>
    </template>
    <!-- 内容 -->
</KrCard>
搜索表单

<KrForm :layout="'inline'" :schema="searchSchema" :submit="submitSearch" :reset="resetSearch">
    <KrButton type="submit">搜索</KrButton>
    <KrButton theme="default" variant="base" type="reset">重置</KrButton>
</KrForm>
数据表格（class="table-wrapper" 直接加在 KrTable 上，保持与搜索表单 8px 间距）

<KrTable
class="table-wrapper"
row-key="id"
:data="dataList"
:columns="columns"
:pagination="pagination"
:max-height="maxHeight"
@page-change="onPageChange"
>
    <template #empty>暂无数据</template>
</KrTable>
弹窗表单

<KrDialog :visible="dialog.visible" :footer="false" :header="dialog.header" :close="dialog.close">
    <KrForm label-align="top" :label-width="60" :rules="dialog.rules" :schema="dialog.schema" :submit="dialog.submit">
        <div class="dialog-footer">
            <KrButton theme="default" @click="dialog.close">取消</KrButton>
            <KrButton type="submit">确定</KrButton>
        </div>
    </KrForm>
</KrDialog>
3. 完整页面模板
<template>
    <KrCard title="页面标题">
        <!-- 操作栏 -->
        <template #actions>
            <KrButton v-isAuth="['kjs_backend.example.add']" @click="handleAdd('add', {})">新增</KrButton>
        </template>

        <!-- 搜索表单 -->
        <KrForm :layout="'inline'" :schema="searchSchema" :submit="submitSearch" :reset="resetSearch">
            <KrButton type="submit">搜索</KrButton>
            <KrButton theme="default" variant="base" type="reset">重置</KrButton>
        </KrForm>

        <!-- 数据表格 -->
        <KrTable
            row-key="id"
            :data="dataList"
            :columns="columns"
            :pagination="pagination"
            :max-height="maxHeight"
            @page-change="onPageChange"
        >
            <template #empty>暂无数据</template>
        </KrTable>

        <!-- 新增/编辑弹窗 -->
        <KrDialog :visible="dialog.visible" :footer="false" :header="dialog.header" :close="dialog.close">
            <KrForm label-align="top" :label-width="60" :rules="dialog.rules" :schema="dialog.schema" :submit="dialog.submit">
                <div class="dialog-footer">
                    <KrButton theme="default" @click="dialog.close">取消</KrButton>
                    <KrButton type="submit">确定</KrButton>
                </div>
            </KrForm>
        </KrDialog>
    </KrCard>
</template>

<script setup lang="jsx">
import { get } from 'lodash';
import { DialogPlugin } from 'tdesign-vue-next';
import { onMounted, reactive, ref } from 'vue';

// 导入接口（按实际业务替换）
import { reqXxxAdd, reqXxxDelete, reqXxxEdit, reqXxxPage } from '@/services/xxx/xxxApi';
import { Perms } from '@/services/permissions';
import { toast } from '@/utils/helper';
import { isPermission, WindowHeight } from '@/utils/utils';

// 表格最大高度，适配屏幕
const maxHeight = WindowHeight() - 260;

// --- 搜索相关 ---
const searchValue = ref({});

// 搜索表单字段配置
const searchSchema = reactive([
    {
        component: 'Input',
        prop: 'keyword',
        props: {
            clearable: true,
            placeholder: '请输入关键字',
        },
    },
    {
        component: 'Select',
        prop: 'status',
        props: {
            clearable: true,
            placeholder: '请选择状态',
            options: [
                { label: '启用', value: 1 },
                { label: '禁用', value: 0 },
            ],
            style: { width: '160px' },
        },
    },
]);

// 提交搜索：重置到第一页再查询
const submitSearch = async (value) => {
    pagination.current = 1;
    searchValue.value = JSON.parse(JSON.stringify(value));
    await fetchData();
};

// 重置搜索
const resetSearch = async () => {
    pagination.current = 1;
    searchValue.value = {};
    await fetchData();
};

// --- 列表与分页 ---
const dataList = ref([]);
const pagination = reactive({
    current: 1,
    pageSize: 20,
    total: 0,
});

// 表格列定义
const columns = [
    {
        // 序号列：根据当前页码和页大小计算
        colKey: 'serial-number',
        title: '序号',
        width: 80,
        align: 'center',
        cell: (h, { rowIndex }) => (pagination.current - 1) * pagination.pageSize + rowIndex + 1,
    },
    {
        colKey: 'name',
        title: '名称',
        align: 'center',
    },
    {
        // 状态列：用 JSX 渲染标签/文字
        colKey: 'status',
        title: '状态',
        align: 'center',
        cell: (h, { row }) => {
            const status = get(row, 'status', -1);
            if (status === 1) return <t-tag theme="success">启用</t-tag>;
            if (status === 0) return <t-tag theme="danger">禁用</t-tag>;
            return '-';
        },
    },
    {
        colKey: 'operation',
        title: '操作',
        width: 150,
        align: 'center',
        fixed: 'right',
        cell: (h, { row }) => {
            // JSX 中用 isPermission 判断权限
            const hasEdit = isPermission(Perms.KjsBackendExampleEdit);
            const hasDel = isPermission(Perms.KjsBackendExampleDelete);
            return (
                <div>
                    {hasEdit && (
                        <KrButton size="small" variant="text" onClick={() => handleAdd('edit', row)}>编辑</KrButton>
                    )}
                    {hasDel && (
                        <KrButton size="small" variant="text" theme="danger" onClick={() => handleDelete(row)}>删除</KrButton>
                    )}
                </div>
            );
        },
    },
];

// 获取列表数据
const fetchData = async () => {
    try {
        const params = {
            page: pagination.current,
            size: pagination.pageSize,
            ...searchValue.value,
        };
        const { success, data, message } = await reqXxxPage(params);
        if (success) {
            dataList.value = data?.list || [];
            pagination.total = data?.pagination?.total || 0;
        } else {
            toast(message, success);
        }
    } catch (error) {
        console.error('Fetch data error:', error);
    }
};

// 分页变化
const onPageChange = (pageInfo) => {
    pagination.current = pageInfo.current;
    pagination.pageSize = pageInfo.pageSize;
    fetchData();
};

// --- 弹窗表单 ---
const dialog = reactive({
    row: null,
    type: '', // 'add' | 'edit'
    header: '',
    visible: false,
    rules: {},
    schema: [],
    close: () => {
        dialog.visible = false;
        dialog.row = null;
        dialog.schema = [];
        dialog.rules = {};
    },
    submit: async (value) => {
        const params = JSON.parse(JSON.stringify(value));
        try {
            const api = dialog.type === 'add' ? reqXxxAdd : reqXxxEdit;
            if (dialog.type === 'edit') params.id = dialog.row?.id;
            const { success, message } = await api(params);
            if (success) {
                dialog.close();
                fetchData();
            }
            toast(message, success);
        } catch (error) {
            console.error('Submit error:', error);
        }
    },
});

// 打开新增或编辑弹窗
const handleAdd = (type = 'add', row = {}) => {
    dialog.row = row;
    dialog.type = type;
    dialog.header = type === 'add' ? '新增' : '编辑';
    dialog.rules = {
        name: [{ required: true, message: '请输入名称', type: 'error' }],
    };
    dialog.schema = [
        {
            component: 'Input',
            label: '名称',
            prop: 'name',
            default: get(row, 'name', ''), // lodash get 安全取值，避免 undefined
            props: { placeholder: '请输入名称' },
        },
        {
            component: 'Select',
            label: '状态',
            prop: 'status',
            default: get(row, 'status', 1),
            props: {
                options: [
                    { label: '启用', value: 1 },
                    { label: '禁用', value: 0 },
                ],
            },
        },
    ];
    dialog.visible = true;
};

// 删除操作（带二次确认）
const handleDelete = (row) => {
    const confirmDialog = DialogPlugin.confirm({
        header: '确认删除',
        body: '确定要删除该记录吗？',
        onConfirm: async () => {
            try {
                const { success, message } = await reqXxxDelete({ id: row.id });
                if (success) {
                    confirmDialog.hide();
                    fetchData();
                }
                toast(message, success);
            } catch (error) {
                console.error('Delete error:', error);
            }
        },
    });
};

onMounted(() => {
    fetchData();
});
</script>

<style lang="less" scoped>
.dialog-footer {
    display: flex;
    justify-content: flex-end;
    width: 100%;
    gap: 8px;
}

// 表格与搜索表单间距（8px）
.table-wrapper {
    margin-top: 8px;
}
</style>
⚠️ 操作列按钮规范 操作列按钮必须使用 KrButton size="small" variant="text"，禁止使用 t-link。 KrButton 自带间距，外层用普通 <div> 包裹即可，无需 Tailwind flex/gap：

cell: (h, { row }) => (
<div>
<KrButton size="small" variant="text" onClick={() => handleView(row)}>查看</KrButton>
<KrButton size="small" variant="text" theme="danger" onClick={() => handleDelete(row)}>删除</KrButton>
</div>
)
4. 常用 KrForm 字段组件示例
   项目中所有组件名称（区分大小写）：Input、Select、textarea、DatePicker、Radio、Switch、Textarea、Upload、Upload2、Editor、Choose、Time、Image、Checkbox

⚠️ DateRangePicker 是错误写法，禁止使用。日期范围必须用 DatePicker + range: true。 ⚠️ InputNumber 是错误写法，禁止使用。数字输入必须用 Input + type: 'number'。

// ── Input 文本输入 ─────────────────────────────────────────────
{ component: 'Input', label: '名称', prop: 'name', default: '',
props: { placeholder: '请输入', clearable: true, maxlength: 50 } }

// Input 数字类型
{ component: 'Input', label: '权重', prop: 'weight', default: '',
props: { type: 'number', clearable: true, maxlength: 50, placeholder: '请输入' } }

// ── Select 下拉选择 ───────────────────────────────────────────
// 基础静态选项
{ component: 'Select', label: '状态', prop: 'status', default: undefined,
props: { clearable: true, placeholder: '请选择', options: [{ label: '是', value: 1 }, { label: '否', value: 0 }], style: { width: '160px' } } }

// 可搜索 + 动态选项
{ component: 'Select', prop: 'launchKfId',
props: { clearable: true, filterable: true, placeholder: '上架客服', options: launchKfList } }

// 多选 + 折叠显示（multiple + minCollapsedNum + filterable）
{ component: 'Select', prop: 'optionFailReasonList',
props: { filterable: true, multiple: true, minCollapsedNum: 1, clearable: true,
placeholder: '请选择失败原因', options: optionReasonValue } }

// ── textarea 多行文本（注意：项目中为小写 textarea）─────────────
{ component: 'textarea', prop: 'failReason', default: '',
props: { clearable: true, placeholder: '请输入失败原因' } }

// ── DatePicker 日期 ───────────────────────────────────────────
// 单日期
{ component: 'DatePicker', label: '提交时间', prop: 'launchTime', default: '',
props: { clearable: true, placeholder: '请选择日期' } }

// 日期范围（range: true，这是项目主流写法）
// ⚠️ placeholder 必须带上业务语义前缀，不能仅写"开始时间/结束时间"，否则多个时间筛选时用户分不清
{ component: 'DatePicker', label: '审核时间', prop: 'shenheTime', default: [],
props: { clearable: true, range: true, placeholder: ['审核开始时间', '审核结束时间'] } }

// 更多示例：
// placeholder: ['支付开始时间', '支付结束时间']
// placeholder: ['创建开始时间', '创建结束时间']
// placeholder: ['退款开始时间', '退款结束时间']

// ── 数字输入（InputNumber 禁止使用，统一用 Input + type: 'number'）──
{ component: 'Input', label: '间隔天数', prop: 'minInterval', default: '',
props: { type: 'number', clearable: true, placeholder: '请输入' } }

// ── Radio 单选 ────────────────────────────────────────────────
{ component: 'Radio', label: '是否支持包赔', prop: 'isIndemnity', default: '0',
props: { options: [{ label: '不支持', value: '0' }, { label: '支持', value: '1' }] } }

// ── Switch 开关 ───────────────────────────────────────────────
{ component: 'Switch', label: '需要提供密码', prop: 'password', default: get(row, 'password', 1),
props: { customValue: [1, 0] } }

// ── Upload 图片上传 ───────────────────────────────────────────
{ component: 'Upload', label: '教程图片', prop: 'image',
default: get(row, 'image', '') ? [{ url: get(row, 'image', '') }] : [],
props: { max: 1, accept: 'image/png, image/gif, image/jpg',
sizeLimit: { size: 50, unit: 'MB' }, showImageFileName: false, requestMethod } }

// ── show 条件显示 ─────────────────────────────────────────────
// 写法一：箭头函数（简洁，推荐）
{
component: 'Select',
prop: 'optionFailReasonList',
props: { filterable: true, multiple: true, minCollapsedNum: 1, clearable: true,
placeholder: '请选择失败原因', options: optionReasonValue },
show: (e: any, value: any) => value.verifyStatus === 0,
}
// 写法二：具名方法
{
component: 'textarea',
prop: 'failReason',
default: '',
props: { clearable: true, placeholder: '请输入失败原因' },
show(itemConfig, _formData) {
return _formData?.verifyStatus === '0';
},
}
注意事项

日期范围优先用 DatePicker + range: true，DateRangePicker 较少使用
多行文本：组件名为小写 textarea（部分旧代码为大写 Textarea，统一用小写）
多选 Select 需同时加 multiple: true + minCollapsedNum: 1 + filterable: true
5. 常用列渲染模式
   // 枚举值映射（先定义字典再用）
   const TYPE_MAP = { 1: '正常', 2: '异常', 3: '未知' };
   { colKey: 'type', title: '类型', cell: (h, { row }) => TYPE_MAP[row.type] || '-' }

// 金额（分转元）
{ colKey: 'amount', title: '金额', cell: (h, { row }) => `¥${(get(row, 'amount', 0) / 100).toFixed(2)}` }

// 时间格式化（如果项目引入了 dayjs）
{ colKey: 'createdAt', title: '创建时间', cell: (h, { row }) => get(row, 'createdAt', '-') }

// 可点击链接
{ colKey: 'id', title: 'ID', cell: (h, { row }) => (
<t-link theme="primary" onClick={() => handleDetail(row)}>{row.id}</t-link>
) }
6. Service 文件规范
   服务文件放在 src/services/<模块名>/ 下，统一使用 req 前缀命名。所有接口 URL 必须先提取为顶部导出对象常量，函数体内引用对象属性，禁止在函数内硬编码 URL 字符串。

// src/services/xxx/xxxApi.ts
import { request } from '@/utils/request';

// ===== 接口地址 =====

export const xxx = {
page: '/api/xxx/v1/page',     // 分页查询
create: '/api/xxx/v1/create', // 新增
update: '/api/xxx/v1/update', // 编辑
delete: '/api/xxx/v1/delete', // 删除
detail: '/api/xxx/v1/detail', // 详情（GET 拼接 /{id}）
recordPage: '/api/xxx/v1/record_page', // 操作记录
};

// ===== 接口函数 =====

export async function reqXxxPage(data: any) {
return request.post({ url: xxx.page, data });
}

export async function reqXxxAdd(data: any) {
return request.post({ url: xxx.create, data });
}

export async function reqXxxEdit(data: any) {
return request.post({ url: xxx.update, data });
}

export async function reqXxxDelete(data: { id: number | string }) {
return request.post({ url: xxx.delete, data });
}

export async function reqXxxDetail(data: { id: number | string }) {
return request.get({ url: `${xxx.detail}/${data.id}` });
}
7. 路由配置规范
   路由文件放在 src/router/modules/<模块名>.ts，并在 src/router/modules/index.ts 中引入：

// src/router/modules/xxx.ts
import { Perms } from '@/services/permissions';
import { LAYOUT } from '@/utils/route/constant';

export default [
{
path: '/xxx',
name: 'xxxConfig',
component: LAYOUT,
redirect: '/',
meta: { title: 'XXX管理', icon: 'setting', orderNo: 130 },
children: [
{
path: 'xxxList',
name: 'xxxList',
component: () => import('@/pages/xxx/xxxList.vue'),
meta: {
title: 'XXX列表',
permissions: Perms.KjsBackendXxxPage, // 若用户提供了对应权限枚举则使用，否则用 Perms.PAGE_VIEW 兜底
},
},
],
},
];
8. 权限对接规范
   8.1 权限使用方式
   模板中按钮：用 v-isAuth="['kjs_backend.xxx.add']" 指令（字符串数组）
   JSX/JS 中判断：用 isPermission(Perms.KjsBackendXxxEdit) 函数
   路由权限：在 router meta.permissions 里引用 Perms 枚举
   权限 key 格式为 kjs_backend.<模块>.<子模块>.<操作>，如 kjs_backend.support.contract_shunt_config.add
   8.2 权限自动检测与添加（严禁自行编造权限）
   核心原则：只添加后端已注册的权限，严禁自行新增不存在的权限。新增页面若后端未注册对应权限，一律使用 Perms.PAGE_VIEW 兜底。

检测步骤：

获取后端全部权限 通过 WebFetch 或 Bash curl 请求测试环境接口获取最新权限列表：

GET https://test-backend.kejinshou.com/__core/permissions
返回格式：{ status: 0, data: [{ url, permission, name }] }

更新本地权限快照 将接口返回的完整 JSON 内容写入 src/services/permissionsCur.json（覆盖写入，确保是合法 JSON）

对比发现新增权限 参考 src/pages/test/permsCheck.vue 的对比逻辑：

读取旧的 permissionsCur.json（对比前的版本）
与新获取的接口数据对比
找出 newOnly（新增权限）列表
忽略 curOnly（移除的权限，暂不处理）
在 permissions.ts 末尾追加新增权限 仅追加 newOnly 中的权限，格式参照 permsCheck.vue 中 printNewPermissions 的输出逻辑：

// ✅ 资金交易单分页：/api/finance/order/v1/trade_order_page
KjsBackendFinanceTradeOrderPage: 'kjs_backend.finance.trade_order.page',
Key 生成规则：去掉 kjs_backend. 前缀 → 按 . 分割 → 每段首字母大写驼峰 → 拼接为 KjsBackend{...}
已对接的标注 // ✅
未对接的标注 //（不加 ✅）
新增页面的权限选择

如果新增权限列表中包含当前页面对应的权限 → 使用该权限
如果新增权限列表中不包含 → 使用 Perms.PAGE_VIEW 兜底，严禁自行编造权限常量
8.3 权限格式约定
// ✅ {接口描述}：{接口URL}
KjsBackendXxxYyy: 'kjs_backend.xxx.yyy',
✅ 表示该权限已在页面/按钮中对接使用
无 ✅ 表示权限已注册但尚未在前端使用
9. toast 使用说明
   import { toast } from '@/utils/helper';

toast('操作成功', true);   // 成功提示（绿色）
toast('操作失败', false);  // 警告提示（黄色）
toast('操作失败');         // 错误提示（红色）

// 接口返回后通用写法
const { success, message } = await reqXxx(params);
toast(message, success);   // success=true 显示成功，false 显示警告
禁止直接使用 MessagePlugin.error、MessagePlugin.success 等原生方法。

10. 关键注意事项
    get() 全场景使用：不论是表单默认值、模板绑定、还是 JSX cell 渲染，一律用 get(obj, 'field', defaultValue) 取值，禁止用 obj?.field 可选链。默认值本身即最终兜底，禁止叠加 || '--'。字符串字段默认值用 '--'，数组字段用 []
<!-- 模板绑定：默认值直接兜底，不加 || '--' -->
{{ get(detailDrawer.data, 'gameTitle', '--') }}
{{ get(detailDrawer.data, 'orderId', '--') }}

<!-- v-if 判断数组 -->
<div v-if="get(row, 'negatives', []).length">
    <div v-for="item in get(row, 'negatives', [])">...</div>
</div>
表格列纯展示字段无需 cell 函数：KrTable 空值默认显示 -，只有需要自定义渲染（枚举映射、JSX、按钮等）时才加 cell
fetchData 中的接口响应结构固定为 { success, data: { list, pagination: { total } }, message }
弹窗 close 时要清空 schema 和 rules，避免切换时残留旧数据
删除操作必须使用 DialogPlugin.confirm 做二次确认
搜索重置时要将 pagination.current 重置为 1
搜索表单字段禁止手动设置 style: { width: '...' }，让组件自适应宽度，不要强制固定宽度
操作列按钮统一使用 KrButton size="small" variant="text"，禁止使用 t-link