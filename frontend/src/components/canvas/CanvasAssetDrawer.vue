<template>
  <el-drawer
    :model-value="visible"
    title="最近素材"
    size="420px"
    append-to-body
    @close="emit('update:visible', false)"
  >
    <template #default>
      <div class="asset-drawer">
        <div class="asset-drawer__actions">
          <el-button text :loading="loading" @click="emit('refresh')">刷新</el-button>
        </div>

        <div v-loading="loading" class="asset-drawer__body">
          <el-empty v-if="!items.length" description="暂无图片或视频素材" />
          <div v-else class="asset-list">
            <article v-for="item in items" :key="item.object_key" class="asset-card">
              <div class="asset-card__preview">
                <img v-if="item.media_type === 'image'" :src="item.preview_url" :alt="item.filename" />
                <video
                  v-else-if="item.media_type === 'video'"
                  :src="item.preview_url"
                  controls
                  playsinline
                  preload="metadata"
                ></video>
              </div>
              <div class="asset-card__body">
                <div class="asset-card__title">{{ item.filename }}</div>
                <div class="asset-card__meta">{{ item.media_type === 'image' ? '图片' : '视频' }} · {{ item.size_mb || 0 }} MB</div>
                <div class="asset-card__ops">
                  <el-button size="small" type="primary" @click="emit('add-to-canvas', item)">
                    加入 Canvas
                  </el-button>
                  <el-button size="small" @click="emit('copy-url', item)">复制 URL</el-button>
                </div>
              </div>
            </article>
          </div>
        </div>
      </div>
    </template>
  </el-drawer>
</template>

<script setup>
  defineProps({
    visible: { type: Boolean, default: false },
    items: { type: Array, default: () => [] },
    loading: { type: Boolean, default: false }
  })

  const emit = defineEmits([
    'add-to-canvas',
    'copy-url',
    'refresh',
    'update:visible'
  ])
</script>

<style scoped>
  .asset-drawer {
    min-height: 100%;
    display: flex;
    flex-direction: column;
  }

  .asset-drawer__actions {
    display: flex;
    justify-content: flex-end;
    margin-bottom: 12px;
  }

  .asset-drawer__body {
    flex: 1;
    min-height: 240px;
  }

  .asset-list {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .asset-card {
    display: grid;
    grid-template-columns: 120px minmax(0, 1fr);
    gap: 12px;
    padding: 12px;
    border: 1px solid rgba(31, 49, 88, 0.12);
    border-radius: 14px;
    background: rgba(255, 255, 255, 0.96);
  }

  .asset-card__preview {
    min-height: 86px;
    border-radius: 10px;
    overflow: hidden;
    background: #eef1f4;
  }

  .asset-card__preview img,
  .asset-card__preview video {
    width: 100%;
    height: 100%;
    object-fit: cover;
  }

  .asset-card__body {
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .asset-card__title {
    color: #24314d;
    font-size: 13px;
    font-weight: 600;
    word-break: break-all;
  }

  .asset-card__meta {
    color: #71809c;
    font-size: 12px;
  }

  .asset-card__ops {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }
</style>
