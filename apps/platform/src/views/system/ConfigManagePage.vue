<template>
  <div class="console-page">
<!--  <div class="flex justify-end gap-2 mb-2">-->
<!--      <el-button v-permission="'system:config:refresh'" size="small" :loading="refreshing" @click="doRefreshCache">-->
<!--        刷新参数缓存-->
<!--      </el-button>-->
<!--    </div>-->
    <tvue-crud
        :option="option"
        :data="data"
        :page="page"
        v-model:search="search"
        @on-load="onLoad"
        @row-save="onSave"
        @row-update="onUpdate"
        @row-del="onDelete"
    />
  </div>
</template>

<script setup lang="ts">
import {reactive, ref} from 'vue'
import {ElMessage, ElMessageBox} from 'element-plus'
import {
  createConfig, deleteConfig, listConfigs, refreshConfigCache, updateConfig,
  type ConfigItem,
} from '../../api'
import {useAuthStore} from '../../stores/auth'

const auth = useAuthStore()
const can = (code: string): boolean =>
    Boolean(auth.user?.permissions?.includes('*') || auth.user?.permissions?.includes(code))

const data = ref<ConfigItem[]>([])
const search = reactive<Record<string, unknown>>({})
const page = reactive({currentPage: 1, pageSize: 10, total: 0})
const refreshing = ref(false)
const valueTypes = [
  {label: '字符串', value: 'string'},
  {label: '数字', value: 'number'},
  {label: '布尔', value: 'bool'},
  {label: 'JSON', value: 'json'},
]

const option = reactive<Record<string, unknown>>({
  card: true, border: true, stripe: true, menuWidth: 150, index: true, height: 'auto',
  addBtn: can('system:config:create'),
  editBtn: can('system:config:update'),
  delBtn: can('system:config:delete'),
  column: [
    {label: '参数键', prop: 'key', search: true, width: 190},
    {label: '参数值', prop: 'value', span: 24},
    {label: '分组', prop: 'group', search: true, span: 12, value: 'system'},
    {
      label: '值类型', prop: 'valueType', type: 'select', dicData: valueTypes,
      props: {label: 'label', value: 'value'}, span: 12, value: 'string',
    },
    {label: '参与缓存', prop: 'cache', type: 'switch', span: 12, value: true},
    {label: '内核参数', prop: 'builtIn', add: false, edit: false, width: 90},
    {label: '备注', prop: 'remark', span: 24},
  ],
})

const onLoad = async (paged: {
  currentPage: number;
  pageSize: number
}, params: Record<string, unknown>, done?: () => void): Promise<void> => {
  if (paged) {
    page.currentPage = paged.currentPage;
    page.pageSize = paged.pageSize
  }
  try {
    const result = await listConfigs({
      page: page.currentPage, pageSize: page.pageSize,
      keyword: params?.keyword, group: params?.group,
    })
    data.value = result.items
    page.total = result.total
  } finally {
    done?.()
  }
}

const onSave = async (form: Record<string, unknown>, done: () => void): Promise<void> => {
  try {
    await createConfig(form)
    ElMessage.success('参数已创建')
    done()
    await onLoad(page, search)
  } catch (error) {
    ElMessage.error((error as Error).message)
  }
}

const onUpdate = async (form: Record<string, unknown> & { id: number }, done: () => void): Promise<void> => {
  try {
    const {id, ...payload} = form
    await updateConfig(id, payload)
    ElMessage.success('参数已更新并刷新缓存')
    done()
    await onLoad(page, search)
  } catch (error) {
    ElMessage.error((error as Error).message)
  }
}

const onDelete = async (row: ConfigItem, done: () => void): Promise<void> => {
  try {
    await ElMessageBox.confirm(`确认删除参数「${row.key}」？`, '提示', {type: 'warning'})
    await deleteConfig(row.id)
    ElMessage.success('参数已删除并刷新缓存')
    done?.()
    await onLoad(page, search)
  } catch (error) {
    if ((error as Error).message !== 'cancel') ElMessage.error((error as Error).message)
  }
}

const doRefreshCache = async (): Promise<void> => {
  refreshing.value = true
  try {
    await refreshConfigCache()
    ElMessage.success('参数缓存已刷新')
  } catch (error) {
    ElMessage.error((error as Error).message)
  } finally {
    refreshing.value = false
  }
}
</script>
