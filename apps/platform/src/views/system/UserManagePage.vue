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
      <template #top-menu>
        <div class="flex items-center gap-2 px-3 py-2">
          <el-button v-permission="'system:user:import'" type="primary" plain @click="openImport">导入用户</el-button>
          <el-button v-permission="'system:user:export'" type="success" plain @click="doExport">导出用户</el-button>
          <a :href="templateUrl" class="text-xs underline" style="color: var(--nf-text-sub)">下载模板</a>
        </div>
      </template>
      <template #roleCodes="{ row }">
        <el-tag v-for="code in row.roleCodes" :key="code" size="small" class="mr-1">{{ roleName(code) }}</el-tag>
      </template>
      <template #menu="{ row }">
        <el-button v-permission="'system:user:reset-pwd'" link type="warning" @click="openReset(row as SystemUser)">
          重置密码
        </el-button>
      </template>
    </tvue-crud>

    <el-dialog v-model="resetVisible" title="重置密码" width="420px">
      <div class="text-xs mb-3" style="color: var(--nf-text-sub)">
        {{ resetTarget?.username }} · 密码至少 {{ policy.minLength }} 位，需字母与数字混合
      </div>
      <el-input v-model="resetPassword" type="password" show-password placeholder="输入新密码"/>
      <template #footer>
        <el-button @click="resetVisible = false">取消</el-button>
        <el-button type="primary" @click="submitReset">确定重置</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="importVisible" title="导入用户" width="460px">
      <el-upload
          drag
          accept=".xlsx"
          :auto-upload="false"
          :limit="1"
          :on-change="onFileChange"
      >
        <div class="text-sm">选择 .xlsx 文件，或拖拽到此处</div>
      </el-upload>
      <div v-if="importResult" class="mt-3 text-xs" style="color: var(--nf-text-sub)">
        <div>成功 {{ importResult.success }} 条，失败 {{ importResult.failed.length }} 条</div>
        <div v-for="(item, index) in importResult.failed" :key="index" class="mt-1">
          第 {{ item.row || '-' }} 行：{{ item.reason }}
        </div>
      </div>
      <template #footer>
        <el-button @click="importVisible = false">关闭</el-button>
        <el-button type="primary" :loading="importing" @click="submitImport">开始导入</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import {computed, reactive, ref} from 'vue'
import {ElMessage, ElMessageBox} from 'element-plus'
import type {UploadFile} from 'element-plus'
import {
  createUser, deleteUser, exportUsersUrl, getFormOptions, importUsers, listUsers,
  resetUserPassword, updateUser, userImportTemplateUrl,
  type PasswordPolicy, type SystemUser, type UserPayload,
} from '../../api'

// 前端权限码 → 后端操作映射由 store 提供；此处只装配 tvue-crud 的 option。
const data = ref<SystemUser[]>([])
const search = reactive<Record<string, unknown>>({})
const page = reactive({currentPage: 1, pageSize: 10, total: 0})
const formOptions = reactive<{
  departments: Array<{ id: number; name: string }>;
  posts: Array<{ id: number; name: string }>;
  roles: Array<{ code: string; name: string }>
}>({
  departments: [], posts: [], roles: [],
})
const policy = reactive<PasswordPolicy>({
  minLength: 8, requireComplex: true, historyLimit: 3,
  lockThreshold: 5, lockMinutes: 15, expireDays: 90,
})
const templateUrl = userImportTemplateUrl()

const roleName = (code: string): string =>
    formOptions.roles.find((item) => item.code === code)?.name || code

const option = reactive<Record<string, unknown>>({
  card: true,
  border: true,
  stripe: true,
  index: true,
  selection: false,
  searchMenuSpan: 6,
  height: 'auto',
  overHidden: true,
  column: [
    {label: '用户名', prop: 'username', search: true, add: false, edit: false, width: 130},
    {label: '姓名', prop: 'displayName', search: true, span: 12},
    {
      label: '部门',
      prop: 'deptId',
      type: 'select',
      dicData: [],
      props: {label: 'name', value: 'id'},
      search: true,
      span: 12,
      hide: true
    },
    {
      label: '角色',
      prop: 'roleCodes',
      type: 'select',
      multiple: true,
      dicData: [],
      props: {label: 'name', value: 'code'},
      span: 24,
      minWidth: 160
    },
    {label: '手机号', prop: 'phone', span: 12},
    {label: '邮箱', prop: 'email', span: 12},
    {
      label: '岗位',
      prop: 'postIds',
      type: 'select',
      multiple: true,
      dicData: [],
      props: {label: 'name', value: 'id'},
      span: 24,
      hide: true
    },
    {label: '状态', prop: 'enabled', type: 'switch', span: 12, value: true},
    {label: '创建时间', prop: 'createdAt', add: false, edit: false, width: 160},
  ],
})

const loadOptions = async (): Promise<void> => {
  const [options, result] = await Promise.all([getFormOptions(), listUsers({page: 1, pageSize: 1})])
  formOptions.departments = options.departments
  formOptions.posts = options.posts
  formOptions.roles = options.roles
  if (result.pwdPolicy) Object.assign(policy, result.pwdPolicy)
  const columns = option.column as Array<Record<string, unknown>>
  const dept = columns.find((item) => item.prop === 'deptId')
  const roles = columns.find((item) => item.prop === 'roleCodes')
  const posts = columns.find((item) => item.prop === 'postIds')
  if (dept) dept.dicData = options.departments
  if (roles) roles.dicData = options.roles
  if (posts) posts.dicData = options.posts
}

const onLoad = async (paged: {
  currentPage: number;
  pageSize: number
}, params: Record<string, unknown>, done?: () => void): Promise<void> => {
  if (paged) {
    page.currentPage = paged.currentPage
    page.pageSize = paged.pageSize
  }
  try {
    const result = await listUsers({
      page: page.currentPage, pageSize: page.pageSize,
      keyword: params?.keyword, deptId: params?.deptId, enabled: params?.enabled,
    })
    data.value = result.items
    page.total = result.total
  } finally {
    done?.()
  }
}

const onSave = async (form: UserPayload, done: () => void): Promise<void> => {
  try {
    await createUser(form)
    ElMessage.success('用户已创建')
    done()
    await onLoad(page, search)
  } catch (error) {
    ElMessage.error((error as Error).message)
  }
}

const onUpdate = async (form: UserPayload & { id: number }, done: () => void): Promise<void> => {
  try {
    const {id, ...payload} = form
    await updateUser(id, payload)
    ElMessage.success('用户已更新')
    done()
    await onLoad(page, search)
  } catch (error) {
    ElMessage.error((error as Error).message)
  }
}

const onDelete = async (row: SystemUser, done: () => void): Promise<void> => {
  try {
    await ElMessageBox.confirm(`确认删除用户「${row.username}」？`, '提示', {type: 'warning'})
    await deleteUser(row.id)
    ElMessage.success('用户已删除')
    done?.()
    await onLoad(page, search)
  } catch (error) {
    if ((error as Error).message !== 'cancel') ElMessage.error((error as Error).message)
  }
}

const resetVisible = ref(false)
const resetTarget = ref<SystemUser | null>(null)
const resetPassword = ref('')
const openReset = (row: SystemUser): void => {
  resetTarget.value = row
  resetPassword.value = ''
  resetVisible.value = true
}
const submitReset = async (): Promise<void> => {
  if (!resetTarget.value) return
  try {
    await resetUserPassword(resetTarget.value.id, resetPassword.value, true)
    ElMessage.success('密码已重置')
    resetVisible.value = false
  } catch (error) {
    ElMessage.error((error as Error).message)
  }
}

const importVisible = ref(false)
const importing = ref(false)
const importFile = ref<File | null>(null)
const importResult = ref<{ success: number; failed: Array<{ row: number; reason: string }> } | null>(null)
const openImport = (): void => {
  importFile.value = null
  importResult.value = null
  importVisible.value = true
}
const onFileChange = (file: UploadFile): void => {
  importFile.value = file.raw || null
}
const submitImport = async (): Promise<void> => {
  if (!importFile.value) {
    ElMessage.warning('请先选择文件')
    return
  }
  importing.value = true
  try {
    importResult.value = await importUsers(importFile.value)
    if (!importResult.value.failed.length) ElMessage.success(`成功导入 ${importResult.value.success} 条`)
    await onLoad(page, search)
  } catch (error) {
    ElMessage.error((error as Error).message)
  } finally {
    importing.value = false
  }
}
const doExport = (): void => {
  window.location.assign(exportUsersUrl({keyword: search.keyword, deptId: search.deptId}))
}

void loadOptions()
</script>
