<template>
  <div class="console-page">
    <tvue-crud
      :option="option"
      :data="data"
      :page="page"
      v-model:search="search"
      @on-load="onLoad"
      @row-save="onSave"
      @row-update="onUpdate"
      @row-del="onDelete"
    >
      <template #menu="{ row }">
        <el-button v-permission="'system:role:assign'" link type="primary" @click="openGrant(row as SystemRole)">分配权限</el-button>
      </template>
    </tvue-crud>

    <el-dialog v-model="grantVisible" :title="`分配权限 · ${grantTarget?.roleName || ''}`" width="640px">
      <el-tabs v-model="grantTab">
        <el-tab-pane label="菜单与按钮" name="menus">
          <el-tree
            ref="menuTreeRef"
            :data="menuTree"
            show-checkbox
            node-key="id"
            :default-checked-keys="checkedMenus"
            :props="{ label: 'title', children: 'children' }"
            style="max-height: 340px; overflow: auto"
          />
        </el-tab-pane>
        <el-tab-pane label="数据范围部门" name="depts">
          <div class="text-xs mb-2" style="color: var(--nf-text-sub)">仅 data_scope = CUSTOM 时生效；当前 {{ grantTarget?.dataScope }}</div>
          <el-tree
            ref="deptTreeRef"
            :data="deptTree"
            show-checkbox
            node-key="id"
            :default-checked-keys="checkedDepts"
            :props="{ label: 'name', children: 'children' }"
            style="max-height: 340px; overflow: auto"
          />
        </el-tab-pane>
      </el-tabs>
      <template #footer>
        <el-button @click="grantVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submitGrant">保存授权</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  assignRoleDepts, assignRoleMenus, createRole, deleteRole, getRoleDepts, getRoleMenus,
  listDepartments, listMenus, listRoles, updateRole,
  type DeptItem, type MenuItem, type SystemRole,
} from '../../api'

const data = ref<SystemRole[]>([])
const search = reactive<Record<string, unknown>>({})
const page = reactive({ currentPage: 1, pageSize: 10, total: 0 })
const scopeOptions = [
  { label: '全部数据', value: 'ALL' },
  { label: '本部门', value: 'DEPT' },
  { label: '本部门及下级', value: 'DEPT_TREE' },
  { label: '仅本人', value: 'SELF' },
  { label: '自定义部门', value: 'CUSTOM' },
]

const option = reactive<Record<string, unknown>>({
  card: true, border: true, stripe: true, index: true,
  column: [
    { label: '角色编码', prop: 'roleCode', search: true, edit: false, width: 130 },
    { label: '角色名称', prop: 'roleName', search: true, span: 12 },
    { label: '数据范围', prop: 'dataScope', type: 'select', dicData: scopeOptions, props: { label: 'label', value: 'value' }, span: 12 },
    { label: '排序', prop: 'sortNo', type: 'number', span: 12, hide: true },
    { label: '用户数', prop: 'userCount', add: false, edit: false, width: 90 },
    { label: '状态', prop: 'enabled', type: 'switch', span: 12, value: true },
    { label: '内置', prop: 'builtIn', add: false, edit: false, width: 80 },
    { label: '备注', prop: 'remark', span: 24 },
  ],
})

const onLoad = async (paged: { currentPage: number; pageSize: number }, params: Record<string, unknown>, done?: () => void): Promise<void> => {
  if (paged) { page.currentPage = paged.currentPage; page.pageSize = paged.pageSize }
  try {
    const result = await listRoles({ page: page.currentPage, pageSize: page.pageSize, keyword: params?.keyword })
    data.value = result.items
    page.total = result.total
  } finally { done?.() }
}

const onSave = async (form: Record<string, unknown>, done: () => void): Promise<void> => {
  try {
    await createRole(form)
    ElMessage.success('角色已创建')
    done()
    await onLoad(page, search)
  } catch (error) { ElMessage.error((error as Error).message) }
}
const onUpdate = async (form: Record<string, unknown> & { id: number }, done: () => void): Promise<void> => {
  try {
    const { id, ...payload } = form
    await updateRole(id, payload)
    ElMessage.success('角色已更新')
    done()
    await onLoad(page, search)
  } catch (error) { ElMessage.error((error as Error).message) }
}
const onDelete = async (row: SystemRole, done: () => void): Promise<void> => {
  try {
    await ElMessageBox.confirm(`确认删除角色「${row.roleName}」？`, '提示', { type: 'warning' })
    await deleteRole(row.id)
    ElMessage.success('角色已删除')
    done?.()
    await onLoad(page, search)
  } catch (error) {
    if ((error as Error).message !== 'cancel') ElMessage.error((error as Error).message)
  }
}

const grantVisible = ref(false)
const grantTarget = ref<SystemRole | null>(null)
const grantTab = ref('menus')
const menuTree = ref<MenuItem[]>([])
const deptTree = ref<DeptItem[]>([])
const checkedMenus = ref<number[]>([])
const checkedDepts = ref<number[]>([])
const menuTreeRef = ref<{ getCheckedKeys: () => number[]; getHalfCheckedKeys: () => number[] } | null>(null)
const deptTreeRef = ref<{ getCheckedKeys: () => number[] } | null>(null)
const saving = ref(false)

const openGrant = async (row: SystemRole): Promise<void> => {
  grantTarget.value = row
  grantTab.value = 'menus'
  const [menus, depts, grantedMenus, grantedDepts] = await Promise.all([
    listMenus(), listDepartments(), getRoleMenus(row.id), getRoleDepts(row.id),
  ])
  menuTree.value = menus.items.filter((item) => item.type !== 'BUTTON')
  deptTree.value = depts.items
  checkedMenus.value = grantedMenus.items.filter((item) => item.granted).map((item) => item.id)
  checkedDepts.value = grantedDepts.items.filter((item) => item.granted).map((item) => item.id)
  grantVisible.value = true
}

const submitGrant = async (): Promise<void> => {
  if (!grantTarget.value) return
  saving.value = true
  try {
    const menuIds = [
      ...(menuTreeRef.value?.getCheckedKeys() || []),
      ...(menuTreeRef.value?.getHalfCheckedKeys() || []),
    ]
    await assignRoleMenus(grantTarget.value.id, menuIds)
    await assignRoleDepts(grantTarget.value.id, deptTreeRef.value?.getCheckedKeys() || [])
    ElMessage.success('授权已保存')
    grantVisible.value = false
  } catch (error) { ElMessage.error((error as Error).message) }
  finally { saving.value = false }
}
</script>
