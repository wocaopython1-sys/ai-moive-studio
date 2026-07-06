<template>
  <section class="works-library-page">
    <header class="works-header">
      <div>
        <h1>作品库</h1>
        <p>归档后的 Canvas final 作品元数据列表</p>
      </div>
      <el-button :loading="loading" @click="loadWorks">刷新</el-button>
    </header>

    <el-card class="works-card" shadow="never">
      <template #header>
        <div class="works-card__header">
          <div>
            <h2>我的作品</h2>
            <span>{{ total }} 个作品</span>
          </div>
        </div>
      </template>

      <div v-if="loading" class="works-state">正在加载作品...</div>
      <el-empty v-else-if="!works.length" description="暂无作品" />

      <template v-else>
        <el-table :data="works" class="works-table" row-key="id">
          <el-table-column prop="title" label="标题" min-width="180">
            <template #default="{ row }">
              <div class="work-title">{{ row.title || '未命名作品' }}</div>
              <div class="work-id">{{ shortText(row.id, 18) }}</div>
            </template>
          </el-table-column>
          <el-table-column prop="status" label="状态" width="110">
            <template #default="{ row }">
              <el-tag :type="statusTagType(row.status)" effect="plain">
                {{ statusLabel(row.status) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="final_object_key" label="最终对象" min-width="240">
            <template #default="{ row }">
              <span class="object-key">{{ shortText(row.final_object_key, 42) || '-' }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="created_at" label="创建时间" width="170">
            <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
          </el-table-column>
          <el-table-column prop="updated_at" label="更新时间" width="170">
            <template #default="{ row }">{{ formatDate(row.updated_at) }}</template>
          </el-table-column>
          <el-table-column label="操作" width="180" fixed="right">
            <template #default="{ row }">
              <el-button size="small" @click="openDetail(row)">查看详情</el-button>
              <el-button
                size="small"
                type="danger"
                :loading="deletingId === row.id"
                @click="deleteWork(row)"
              >
                删除
              </el-button>
            </template>
          </el-table-column>
        </el-table>

        <div class="works-pagination">
          <el-pagination
            v-model:current-page="page"
            v-model:page-size="pageSize"
            background
            layout="total, sizes, prev, pager, next"
            :page-sizes="[10, 20, 50]"
            :total="total"
            @current-change="loadWorks"
            @size-change="handlePageSizeChange"
          />
        </div>
      </template>
    </el-card>

    <el-drawer
      v-model="detailVisible"
      title="作品详情"
      size="560px"
      :destroy-on-close="true"
    >
      <div v-if="detailLoading" class="works-state">正在加载详情...</div>
      <div v-else-if="selectedWork" class="work-detail">
        <el-alert
          title="媒体预览待接入"
          type="info"
          :closable="false"
          show-icon
        />

        <dl class="work-detail__meta">
          <div>
            <dt>ID</dt>
            <dd>{{ selectedWork.id }}</dd>
          </div>
          <div>
            <dt>标题</dt>
            <dd>{{ selectedWork.title || '未命名作品' }}</dd>
          </div>
          <div>
            <dt>描述</dt>
            <dd>{{ selectedWork.description || '-' }}</dd>
          </div>
          <div>
            <dt>状态</dt>
            <dd>
              <el-tag :type="statusTagType(selectedWork.status)" effect="plain">
                {{ statusLabel(selectedWork.status) }}
              </el-tag>
            </dd>
          </div>
          <div>
            <dt>final_object_key</dt>
            <dd class="object-key">{{ shortText(selectedWork.final_object_key, 64) || '-' }}</dd>
          </div>
          <div>
            <dt>source_canvas_id</dt>
            <dd>{{ selectedWork.source_canvas_id || '-' }}</dd>
          </div>
          <div>
            <dt>source_canvas_item_id</dt>
            <dd>{{ selectedWork.source_canvas_item_id || '-' }}</dd>
          </div>
          <div>
            <dt>source_generation_id</dt>
            <dd>{{ selectedWork.source_generation_id || '-' }}</dd>
          </div>
          <div>
            <dt>created_at</dt>
            <dd>{{ formatDate(selectedWork.created_at) }}</dd>
          </div>
          <div>
            <dt>updated_at</dt>
            <dd>{{ formatDate(selectedWork.updated_at) }}</dd>
          </div>
        </dl>

        <section class="work-items">
          <h3>关联素材</h3>
          <el-empty
            v-if="!selectedWork.items?.length"
            description="暂无关联素材"
            :image-size="80"
          />
          <el-table v-else :data="selectedWork.items" row-key="id" size="small">
            <el-table-column prop="role" label="角色" width="90" />
            <el-table-column prop="media_type" label="类型" width="90" />
            <el-table-column prop="object_key" label="对象">
              <template #default="{ row }">
                <span class="object-key">{{ shortText(row.object_key, 48) }}</span>
              </template>
            </el-table-column>
          </el-table>
        </section>
      </div>
    </el-drawer>
  </section>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { worksService } from '@/services/works'

const works = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const loading = ref(false)
const detailLoading = ref(false)
const detailVisible = ref(false)
const selectedWork = ref(null)
const deletingId = ref('')

const normalizeWorks = (response = {}) => {
  works.value = Array.isArray(response.works) ? response.works : []
  total.value = Number(response.total || 0)
}

const loadWorks = async () => {
  loading.value = true
  try {
    const response = await worksService.listWorks({
      page: page.value,
      size: pageSize.value
    })
    normalizeWorks(response)
  } catch (error) {
    ElMessage.error(error?.response?.data?.detail || '作品列表加载失败')
  } finally {
    loading.value = false
  }
}

const handlePageSizeChange = () => {
  page.value = 1
  void loadWorks()
}

const openDetail = async (work) => {
  detailVisible.value = true
  detailLoading.value = true
  selectedWork.value = work
  try {
    selectedWork.value = await worksService.getWork(work.id)
  } catch (error) {
    ElMessage.error(error?.response?.data?.detail || '作品详情加载失败')
  } finally {
    detailLoading.value = false
  }
}

const deleteWork = async (work) => {
  await ElMessageBox.confirm(`确认删除「${work.title || '未命名作品'}」？`, '删除作品', {
    type: 'warning',
    confirmButtonText: '删除',
    cancelButtonText: '取消'
  })

  deletingId.value = work.id
  try {
    await worksService.deleteWork(work.id)
    ElMessage.success('作品已删除')
    if (works.value.length === 1 && page.value > 1) {
      page.value -= 1
    }
    await loadWorks()
  } catch (error) {
    ElMessage.error(error?.response?.data?.detail || '作品删除失败')
  } finally {
    deletingId.value = ''
  }
}

const statusLabel = (status) =>
  ({
    archived: '已归档',
    hidden: '已隐藏',
    deleted: '已删除'
  })[status] || status || '未知'

const statusTagType = (status) =>
  ({
    archived: 'success',
    hidden: 'info',
    deleted: 'danger'
  })[status] || 'warning'

const shortText = (value, maxLength = 32) => {
  const text = String(value || '').trim()
  if (!text) return ''
  if (text.length <= maxLength) return text
  return `${text.slice(0, Math.max(0, maxLength - 3))}...`
}

const formatDate = (value) => {
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString()
}

onMounted(loadWorks)
</script>

<style scoped>
.works-library-page {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.works-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
}

.works-header h1 {
  margin: 0;
  font-size: 28px;
}

.works-header p {
  margin: 8px 0 0;
  color: var(--text-secondary);
}

.works-card {
  border-radius: 12px;
}

.works-card__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.works-card__header h2 {
  margin: 0;
  font-size: 18px;
}

.works-card__header span {
  display: inline-block;
  margin-top: 6px;
  color: var(--text-tertiary);
  font-size: 13px;
}

.works-state {
  padding: 48px 0;
  text-align: center;
  color: var(--text-secondary);
}

.works-table {
  width: 100%;
}

.work-title {
  font-weight: 600;
  color: var(--text-primary);
}

.work-id {
  margin-top: 4px;
  color: var(--text-tertiary);
  font-size: 12px;
}

.object-key {
  display: inline-block;
  max-width: 100%;
  color: var(--text-secondary);
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 12px;
  word-break: break-all;
}

.works-pagination {
  display: flex;
  justify-content: flex-end;
  padding-top: 18px;
}

.work-detail {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.work-detail__meta {
  display: grid;
  gap: 14px;
  margin: 0;
}

.work-detail__meta div {
  display: grid;
  grid-template-columns: 150px minmax(0, 1fr);
  gap: 12px;
  align-items: start;
}

.work-detail__meta dt {
  color: var(--text-tertiary);
  font-size: 13px;
}

.work-detail__meta dd {
  min-width: 0;
  margin: 0;
  color: var(--text-primary);
  word-break: break-word;
}

.work-items h3 {
  margin: 0 0 12px;
  font-size: 16px;
}

@media (max-width: 768px) {
  .works-header {
    align-items: flex-start;
    flex-direction: column;
  }

  .work-detail__meta div {
    grid-template-columns: 1fr;
    gap: 4px;
  }
}
</style>
