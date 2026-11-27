<template>
  <div class="console-page">
  <tvue-crud
    ref="crudRef"
    :option="option"
    :data="data"
    :permission="permission"
    v-model:search="search"
    :before-open="onBeforeOpen"
    :before-close="onBeforeClose"
    @on-load="onLoad"
    @search-change="onSearchChange"
    @search-reset="onSearchReset"
    @selection-change="onSelectionChange"
    @refresh-change="reload"
    @row-del="onRowDel"
    @row-save="onRowSave"
    @row-update="onRowUpdate"
    @change="onFormChange"
  >
    <!-- crud 没有内置“批量删除”，用官方插槽追加，保持同一按钮组 -->
    <template #menu-left="{ size }">
      <el-button v-permission="'system:menu:delete'" type="danger" plain :size="size"
                 :disabled="!selectedRows.length" :loading="deleting" @click="doBatchDelete">
        <el-icon><Delete /></el-icon><span>删除</span>
      </el-button>
    </template>

    <!-- 图标列：Element Plus / FontAwesome / iconfont / SVG 统一预览 -->
    <template #icon="{ row }">
      <AppIcon v-if="resolveIcon((row as MenuItem).icon).kind !== 'none'" :name="(row as MenuItem).icon" :size="16" />
      <span v-else style="color: var(--el-text-color-placeholder)">—</span>
    </template>

    <!-- 类型 / 状态 / 显示 用标签呈现 -->
    <template #type="{ row }">
      <el-tag :type="typeTag[(row as MenuItem).type]" size="small" effect="plain">
        {{ typeText[(row as MenuItem).type] }}
      </el-tag>
    </template>
    <template #enabled="{ row }">
      <el-tag :type="(row as MenuItem).enabled ? 'success' : 'warning'" size="small" effect="plain">
        {{ (row as MenuItem).enabled ? '启用' : '停用' }}
      </el-tag>
    </template>
    <template #visible="{ row }">
      <el-tag :type="(row as MenuItem).visible ? 'info' : 'danger'" size="small" effect="plain">
        {{ (row as MenuItem).visible ? '显示' : '隐藏' }}
      </el-tag>
    </template>

    <!-- crud 没有内置“新增子级”，用官方插槽追加在原生编辑/删除之前 -->
    <template #menu-before="{ row, size }">
      <el-button v-if="(row as MenuItem).type === 'DIR'" v-permission="'system:menu:create'"
                 type="primary" plain :size="size" @click="openAddChild(row as MenuItem)">新增子级</el-button>
    </template>

    <!-- 复用 crud 自带弹窗的字段插槽：父级只读 -->
    <template #parentId-form>
      <el-tag type="info" effect="plain" size="small">{{ parentPathText }}</el-tag>
    </template>

    <!-- 菜单弹窗底部的按钮动态列表，增删按钮不建菜单树节点 -->
    <template #buttons-form="{ value }">
      <div class="button-editor">
        <el-button v-if="!value || !value.length" class="button-add-empty" @click="addButton(-1)">
          <el-icon><Plus /></el-icon><span>新增</span>
        </el-button>
        <div v-for="(item, index) in (value || [])" :key="index" class="button-row">
          <el-input v-model="item.code" placeholder="请输入按钮编码" />
          <el-input v-model="item.desc" placeholder="请输入按钮描述" />
          <el-button size="small" @click="addButton(index)"><el-icon><Plus /></el-icon></el-button>
          <el-button size="small" @click="removeButton(index)"><el-icon><Minus /></el-icon></el-button>
        </div>
      </div>
    </template>
  </tvue-crud>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { createMenu, deleteMenu, listMenus, updateMenu, type MenuButton, type MenuItem } from '../../api'
import AppIcon from '../../components/AppIcon.vue'
import { iconList, normalizeIcon, resolveIcon } from '../../utils/icons'

type MenuType = MenuItem['type']
type OperateType = 'add' | 'addChild' | 'edit'

type FormColumn = {
  prop: string
  label: string
  hide?: boolean
  display?: boolean
  disabled?: boolean
  rules?: Array<Record<string, unknown>>
  dicData?: Array<{ label: string; value: unknown }>
  [key: string]: unknown
}

const typeText: Record<MenuType, string> = { DIR: '目录', MENU: '菜单', BUTTON: '按钮' }
const typeTag: Record<MenuType, 'info' | 'primary' | 'warning'> = {
  DIR: 'info', MENU: 'primary', BUTTON: 'warning',
}
const yesNo = [{ label: '是', value: true }, { label: '否', value: false }]

const data = ref<MenuItem[]>([])
const crudRef = ref<{
  tableForm?: Record<string, unknown>
  rowAdd?: () => void
  clearSelection?: () => void
}>()
const componentWhitelist = ref<string[]>([])
const pathMap = new Map<number, string>()
const loading = ref(false)
const search = reactive<Record<string, unknown>>({})
const selectedRows = ref<MenuItem[]>([])
const deleting = ref(false)

// crud 原生按钮（新增/编辑/删除）的权限交给组件内置的 v-permission 指令校验
const permission = {
  addBtn: 'system:menu:create',
  editBtn: 'system:menu:update',
  delBtn: 'system:menu:delete',
}

const option = reactive<Record<string, unknown>>({
  card: true, border: false, stripe: true,
  selection: true, selectionWidth: 46, selectionFixed: 'left',
  rowKey: 'id', tree: true, treeProps: { children: 'children' }, defaultExpandAll: false,
  page: false, menuType: 'button', menuWidth: 300, menuAlign: 'right',
  header: true, tip: false,
  // 原生搜索表单：由 column 上的 search:true 自动生成，搜索/清空按钮用组件默认
  searchShow: true, searchSpan: 6, searchBtnText: '搜索', emptyBtnText: '重置',
  // 启用 crud 原生按钮：顶部新增/刷新/列设置，行内编辑/删除
  addBtn: true, editBtn: true, delBtn: true,
  refreshBtn: true, columnBtn: true,
  viewBtn: false, copyBtn: false,
  gridBtn: false, dataToolsBtn: false, queryViewBtn: false, excelBtn: false, importBtn: false,
  addBtnText: '新增', editBtnText: '编辑', delBtnText: '删除',
  dialogTop: '6vh', searchLabelWidth: 140, labelWidth: 140, span: 12,
  saveBtnText: '确定', updateBtnText: '确定', cancelBtnText: '取消',
  addTitle: '新增菜单', editTitle: '编辑菜单',
  column: [
    { label: 'ID', prop: 'id', width: 70, add: false, edit: false, view: false, display: false },
    {
      label: '菜单类型', prop: 'type', width: 100, type: 'radio', span: 12,
      dicData: [
        { label: '目录', value: 'DIR' }, { label: '菜单', value: 'MENU' },
      ],
      rules: [{ required: true, message: '请选择菜单类型', trigger: 'change' }],
    },
    {
      label: '菜单名称 / 编码', prop: 'title', minWidth: 210, span: 12,
      search: true, searchSpan: 6,
      rules: [{ required: true, message: '请输入菜单名称', trigger: 'blur' }],
    },
    { label: '菜单编码', prop: 'code', minWidth: 150, span: 12,
      rules: [{ required: true, message: '请输入菜单编码', trigger: 'blur' }] },
    {
      label: '图标', prop: 'icon', width: 100, span: 12,
      // tvue 原生图标选择器：支持 el-icon-xxx / fa-solid fa-house / iconfont icon-home / #icon-home
      type: 'icon', iconList, clearable: true, placeholder: '请选择图标',
    },
    { label: '路由路径', prop: 'path', minWidth: 180, span: 12 },
    { label: '组件标识', prop: 'componentKey', width: 180, span: 12, type: 'select', dicData: [] },
    { label: '权限码', prop: 'permission', minWidth: 180, span: 12 },
    {
      label: '状态', prop: 'enabled', width: 90, span: 12, type: 'radio',
      dicData: [{ label: '启用', value: true }, { label: '停用', value: false }],
    },
    { label: '显示', prop: 'visible', width: 90, span: 12, type: 'radio', dicData: yesNo },
    { label: '父级菜单', prop: 'parentId', width: 100, span: 24, disabled: true },
    { label: '排序', prop: 'sortNo', width: 70, span: 12, type: 'number' },
    { label: '缓存页面', prop: 'cache', hide: true, span: 12, type: 'radio', dicData: yesNo },
    { label: '按钮', prop: 'buttons', hide: true, span: 24, display: false },
  ],
})

const columns = option.column as FormColumn[]
const columnOf = (prop: string): FormColumn | undefined => columns.find(c => c.prop === prop)

const operateType = ref<OperateType>('add')
const editingData = ref<MenuItem | null>(null)
const parentPathText = ref('顶级（无父级）')

const allowedTypes = computed<MenuType[]>(() => {
  if (operateType.value === 'edit') return editingData.value ? [editingData.value.type] : []
  if (operateType.value === 'addChild') {
    const parentType = editingData.value?.type
    return parentType === 'DIR' ? ['DIR', 'MENU'] : []
  }
  return ['DIR', 'MENU']
})

/** 只改表单字段的 display/rules，不影响表格列（表格列用 hide） */
const applyFormConfig = (type: MenuType): void => {
  const setDisplay = (prop: string, display: boolean): void => {
    const col = columnOf(prop)
    if (col) col.display = display
  }
  setDisplay('path', type !== 'BUTTON')
  setDisplay('componentKey', type === 'MENU')
  setDisplay('icon', type !== 'BUTTON')
  setDisplay('visible', type !== 'BUTTON')
  setDisplay('cache', type === 'MENU')
  setDisplay('buttons', type === 'MENU')

  const component = columnOf('componentKey')
  if (component) {
    component.dicData = componentWhitelist.value.filter(Boolean).map(v => ({ label: v, value: v }))
    component.rules = type === 'MENU'
      ? [{ required: true, message: '请选择页面组件', trigger: 'change' }] : []
  }
  const typeColumn = columnOf('type')
  if (typeColumn) {
    typeColumn.dicData = allowedTypes.value.map(t => ({ label: typeText[t], value: t }))
    typeColumn.disabled = operateType.value === 'edit'
  }
}

const resetFormDefaults = (): void => {
  Object.assign(crudRef.value?.tableForm || {}, {
    parentId: 0, type: 'DIR', code: '', title: '', path: '', componentKey: '',
    icon: '', permission: '', sortNo: 0, visible: true, cache: false, enabled: true,
    buttons: [],
  })
}

const onBeforeOpen = (callback: () => void, boxType: string): void => {
  const form = crudRef.value?.tableForm || {}
  if (boxType === 'edit') {
    operateType.value = 'edit'
    editingData.value = { ...form } as unknown as MenuItem
    parentPathText.value = form.parentId ? (pathMap.get(Number(form.parentId)) || '未知父级') : '顶级（无父级）'
    option.editTitle = '编辑菜单'
  } else {
    // 原生“新增”按钮：operateType 已在 beforeClose 复位为 add
    if (operateType.value !== 'addChild') resetFormDefaults()
    option.addTitle = operateType.value === 'addChild' ? '新增子菜单' : '新增菜单'
  }
  if (!Array.isArray(form.buttons)) form.buttons = []
  form.buttons = (form.buttons as MenuButton[]).map(b => ({ ...b }))
  // 存量菜单的 gear/user 等短名映射到 Element Plus；FA / iconfont 显式值补齐为可渲染 class
  form.icon = normalizeIcon(form.icon) || form.icon
  applyFormConfig((form.type as MenuType) || 'DIR')
  callback()
}

const onBeforeClose = (callback: () => void): void => {
  option.addTitle = '新增菜单'
  option.editTitle = '编辑菜单'
  operateType.value = 'add'
  editingData.value = null
  callback()
}

const onFormChange = (form: Record<string, unknown>): void => {
  const type = form?.type as MenuType | undefined
  if (type && ['DIR', 'MENU'].includes(type)) applyFormConfig(type)
}

const onLoad = async (_paged: unknown, params: Record<string, unknown>, done?: () => void): Promise<void> => {
  loading.value = true
  try {
    const res = await listMenus()
    componentWhitelist.value = res.componentWhitelist || []
    pathMap.clear()
    const walk = (nodes: MenuItem[], prefix: string): void => {
      nodes.forEach(n => {
        const full = prefix ? `${prefix} / ${n.title}` : n.title
        pathMap.set(n.id, full)
        walk(n.children || [], full)
      })
    }
    walk(res.items, '')
    // 原生搜索表单字段为 title；与菜单编码、按钮编码/描述一并做前端匹配
    const kw = String(params?.title ?? params?.code ?? '').trim()
    data.value = kw ? filterTree(res.items, kw) : res.items
    selectedRows.value = []
    void nextTick(() => crudRef.value?.clearSelection?.())
  } finally {
    loading.value = false
    done?.()
  }
}

const filterTree = (nodes: MenuItem[], kw: string): MenuItem[] => {
  const result: MenuItem[] = []
  nodes.forEach(n => {
    const children = filterTree(n.children || [], kw)
    const hitButton = (n.buttons || []).some(b => b.code.includes(kw) || b.desc.includes(kw))
    if (n.title.includes(kw) || n.code.includes(kw) || hitButton || children.length) {
      result.push({ ...n, children })
    }
  })
  return result
}

/** 原生搜索表单提交：form 是过滤后的搜索值，done 用于结束提交 loading */
const onSearchChange = (form: Record<string, unknown>, done?: () => void): void => {
  void onLoad(null, form, done)
}
const onSearchReset = (): void => { void onLoad(null, {}) }
const onSelectionChange = (rows: MenuItem[]): void => { selectedRows.value = rows || [] }
const reload = (): void => { void onLoad(null, search) }

const addButton = (rawIndex: number | string): void => {
  const form = crudRef.value?.tableForm
  if (!form) return
  if (!Array.isArray(form.buttons)) form.buttons = []
  const index = Number(rawIndex)
  ;(form.buttons as MenuButton[]).splice(index + 1, 0, { id: 0, code: '', desc: '' })
}

const removeButton = (rawIndex: number | string): void => {
  const form = crudRef.value?.tableForm
  if (!form || !Array.isArray(form.buttons)) return
  ;(form.buttons as MenuButton[]).splice(Number(rawIndex), 1)
}

/** 行内“新增子级”：组件无原生按钮，注入父级上下文后再走 crud 的 rowAdd 流程 */
const openAddChild = (row: MenuItem): void => {
  operateType.value = 'addChild'
  editingData.value = { ...row }
  parentPathText.value = pathMap.get(row.id) || row.title
  Object.assign(crudRef.value?.tableForm || {}, {
    id: undefined, parentId: row.id, type: 'MENU',
    code: '', title: '', path: '', componentKey: '', icon: '', permission: '',
    sortNo: 0, visible: true, cache: false, enabled: true, buttons: [],
  })
  crudRef.value?.rowAdd?.()
}

const buildPayload = (row: Record<string, unknown>): Record<string, unknown> => ({
  code: String(row.code || '').trim(),
  title: String(row.title || '').trim(),
  type: row.type,
  parentId: Number(row.parentId) || 0,
  path: String(row.path || '').trim(),
  componentKey: row.type === 'MENU' ? String(row.componentKey || '') : '',
  icon: normalizeIcon(row.icon),
  permission: String(row.permission || '').trim(),
  sortNo: Number(row.sortNo) || 0,
  visible: Boolean(row.visible),
  cache: Boolean(row.cache),
  enabled: Boolean(row.enabled),
  redirectPath: '', linkUrl: '',
  buttons: row.type === 'MENU'
    ? ((row.buttons as MenuButton[]) || []).map(b => ({
      id: Number(b.id) || 0, code: String(b.code || '').trim(), desc: String(b.desc || '').trim(),
    }))
    : [],
})

const onRowSave = async (row: Record<string, unknown>, done: () => void, hide?: () => void): Promise<void> => {
  try {
    await createMenu(buildPayload(row))
    ElMessage.success('菜单已创建')
    done()
    await onLoad(null, search)
  } catch (error) {
    ElMessage.error((error as Error).message)
    hide?.()
  }
}

const onRowUpdate = async (row: Record<string, unknown>, _index: number, done: () => void, hide?: () => void): Promise<void> => {
  try {
    await updateMenu(Number(row.id), buildPayload(row))
    ElMessage.success('菜单已更新')
    done()
    await onLoad(null, search)
  } catch (error) {
    ElMessage.error((error as Error).message)
    hide?.()
  }
}

/** 原生删除按钮：crud 只负责 emit，确认与接口调用在这里完成 */
const onRowDel = (row: MenuItem, _index: number, done: () => void): void => {
  ElMessageBox.confirm('确认删除该菜单？其下按钮会一并删除', '提示',
    { type: 'warning', confirmButtonText: '确认', cancelButtonText: '取消' })
    .then(async () => {
      try {
        await deleteMenu(row.id)
        ElMessage.success('菜单已删除')
        done()
        await onLoad(null, search)
      } catch (error) {
        ElMessage.error((error as Error).message)
      }
    })
    .catch(() => { /* 取消删除不做处理 */ })
}

const doBatchDelete = async (): Promise<void> => {
  const rows = [...selectedRows.value]
  if (!rows.length) return
  try {
    await ElMessageBox.confirm(`确认删除选中的 ${rows.length} 项菜单？存在子菜单的项会被跳过。`, '提示',
      { type: 'warning', confirmButtonText: '确认', cancelButtonText: '取消' })
  } catch { return }
  const depthOf = (row: MenuItem): number => (pathMap.get(row.id) || '').split(' / ').length
  const ordered = rows.sort((a, b) => depthOf(b) - depthOf(a))
  deleting.value = true
  let success = 0
  let failed = 0
  try {
    for (const row of ordered) {
      try { await deleteMenu(row.id); success += 1 } catch { failed += 1 }
    }
    if (failed) ElMessage.warning(`已删除 ${success} 项，${failed} 项删除失败（请先删除其子菜单）`)
    else ElMessage.success(`已删除 ${success} 项菜单`)
    await onLoad(null, search)
  } finally { deleting.value = false }
}
</script>

<style scoped>
.button-editor { width: 100%; }
.button-add-empty {
  width: 100%;
  border-style: dashed;
  color: var(--el-color-primary);
}
.button-row {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 8px;
}
.button-row :deep(.el-input) { flex: 1; }
</style>
