<template>
  <div class="frame-selector">
    <el-card class="folder-panel">
      <template #header>
        <div class="card-header">
          <span>文件夹选择</span>
        </div>
      </template>
      
      <div class="folder-input-group">
        <el-input
          v-model="folderPath"
          placeholder="输入帧图像所在的文件夹路径"
          class="folder-input"
          clearable
        />
        <el-button 
          type="primary" 
          :loading="scanning" 
          @click="handleScanFolder"
          class="scan-button"
        >
          扫描文件夹
        </el-button>
      </div>

      <div v-if="frames.length > 0" class="frames-info">
        找到 {{ frames.length }} 张帧图像
      </div>

      <!-- 将缩略图部分移动到文件夹选择面板内 -->
      <div class="thumbnails-section" v-if="frames.length > 0">
        <div class="thumbnails-header">
          <span>帧缩略图</span>
          <div class="pagination-info">
            第 {{ currentPage }} 页，共 {{ totalPages }} 页
          </div>
        </div>

        <div class="thumbnails-grid">
          <div
            v-for="frame in currentPageFrames"
            :key="`frame-${frame.index}-${frame.filename}`"
            :class="['thumbnail-item', { active: selectedFrameIndex === frame.index }]"
            @click="handleSelectFrame(frame)"
          >
            <div class="thumbnail-wrapper">
              <!-- 缩略图 -->
              <img
                v-if="frame.thumbnailUrl && !frame.thumbnailError"
                :src="frame.thumbnailUrl"
                :alt="`Frame ${frame.index}`"
                class="thumbnail-img"
                @load="handleImageLoad(frame)"
                @error="handleImageError(frame)"
              />
              
              <!-- 加载中 -->
              <div v-else-if="!frame.thumbnailError" class="thumbnail-loading">
                <el-icon class="loading-icon"><Loading /></el-icon>
                <span class="loading-text">加载中...</span>
              </div>

              <!-- 加载失败 -->
              <div v-if="frame.thumbnailError" class="thumbnail-error">
                <el-icon><Picture /></el-icon>
                <span class="error-text">加载失败</span>
              </div>
            </div>

            <div class="frame-info">
              <div class="frame-index">帧 {{ frame.index }}</div>
              <div class="frame-filename">{{ frame.filename }}</div>
            </div>
          </div>

          <!-- 填充空位保证网格整齐 -->
          <div 
            v-for="i in emptySlots" 
            :key="`empty-${i}`" 
            class="thumbnail-item empty-slot"
          ></div>
        </div>

        <div class="pagination-controls">
          <el-pagination
            v-model:current-page="currentPage"
            :page-size="pageSize"
            :total="frames.length"
            :pager-count="5"
            layout="prev, pager, next, jumper"
            background
            @current-change="handlePageChange"
          />
        </div>
      </div>

      <!-- 空状态也移动到文件夹选择面板内 -->
      <div class="empty-state" v-if="scanned && frames.length === 0">
        <el-icon class="empty-icon"><FolderOpened /></el-icon>
        <p>未找到帧图像</p>
        <p class="empty-tip">请检查文件夹路径是否正确</p>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, defineEmits, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import { Picture, Loading, FolderOpened } from '@element-plus/icons-vue'
import { api } from '../services/api'

const emit = defineEmits(['frame-selected', 'folder-update'])

const folderPath = ref('不支持相对路径，只能用绝对路径')
const frames = ref([])
const selectedFrameIndex = ref(null)
const scanning = ref(false)
const scanned = ref(false)
const currentPage = ref(1)
const pageSize = ref(9)

const totalPages = computed(() => Math.ceil(frames.value.length / pageSize.value))
const currentPageFrames = computed(() => {
  const start = (currentPage.value - 1) * pageSize.value
  const end = start + pageSize.value
  return frames.value.slice(start, end)
})
const emptySlots = computed(() => {
  const remainder = currentPageFrames.value.length % 3
  return remainder === 0 ? 0 : 3 - remainder
})

// 扫描文件夹
const handleScanFolder = async () => {
  if (!folderPath.value) {
    ElMessage.error('请输入文件夹路径')
    return
  }
  scanning.value = true
  scanned.value = true

  try {
    const response = await api.scanFolder(folderPath.value)
    if (response.success) {
      frames.value = response.frames.map(frame => ({
        ...frame,
        thumbnailLoaded: false,
        thumbnailError: false,
        thumbnailUrl: null,
        index: Number(frame.index) || 0
      }))

      ElMessage.success(`成功扫描到 ${response.frame_count} 张帧图像`)
      emit('folder-update', folderPath.value)
      currentPage.value = 1

      // 异步加载每个帧的缩略图 URL
      frames.value.forEach(frame => loadThumbnail(frame))
      await nextTick()
    } else {
      ElMessage.error('扫描文件夹失败')
    }
  } catch (error) {
    console.error('扫描文件夹失败:', error)
    ElMessage.error(`扫描失败: ${error.response?.data?.detail || error.message}`)
  } finally {
    scanning.value = false
  }
}

// 异步加载缩略图 URL
const loadThumbnail = (frame) => {
  // 生成直接可用的 img src
  frame.thumbnailUrl = api.getFrameImageUrl(folderPath.value, frame.filename)
}

// 选择帧
const handleSelectFrame = (frame) => {
  selectedFrameIndex.value = frame.index
  emit('frame-selected', frame)
  ElMessage.success(`已选择帧 ${frame.index}`)
}

// 图片加载成功
const handleImageLoad = (frame) => {
  frame.thumbnailLoaded = true
  frame.thumbnailError = false
}

// 图片加载失败
const handleImageError = (frame) => {
  frame.thumbnailLoaded = false
  frame.thumbnailError = true
  console.warn(`帧 ${frame.index} 缩略图加载失败`)
}

// 翻页
const handlePageChange = (newPage) => {
  currentPage.value = newPage
}

</script>

<style scoped lang="scss">
.frame-selector {
  display: flex;
  flex-direction: column;
  gap: 16px;
  height: 100%;
}

.folder-panel {
  flex-shrink: 0;
}

.folder-input-group {
  display: flex;
  gap: 12px;
  align-items: flex-start;
}

.folder-input {
  flex: 1;
}

.scan-button {
  flex-shrink: 0;
}

.frames-info {
  color: #67c23a;
  font-size: 14px;
  margin-top: 12px;
  font-weight: 500;
}

.thumbnails-section {
  margin-top: 20px;
  border-top: 1px solid #e4e7ed;
  padding-top: 20px;
}

.thumbnails-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.pagination-info {
  color: #909399;
  font-size: 14px;
}

.thumbnails-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
  flex: 1;
  padding: 8px;
  align-content: start;
  min-height: 400px; /* 确保有最小高度 */
}

.thumbnail-item {
  display: flex;
  flex-direction: column;
  cursor: pointer;
  border: 2px solid #e4e7ed;
  border-radius: 8px;
  overflow: hidden;
  background: white;
  transition: all 0.3s ease;
  position: relative;
  min-height: 180px; /* 确保有最小高度 */

  &:hover {
    border-color: #409eff;
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
  }

  &.active {
    border-color: #67c23a;
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(102, 194, 58, 0.2);
    
    &::after {
      content: '✓';
      position: absolute;
      top: 8px;
      right: 8px;
      background: #67c23a;
      color: white;
      width: 20px;
      height: 20px;
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 12px;
      font-weight: bold;
      z-index: 10;
    }
  }

  &.empty-slot {
    visibility: hidden;
    pointer-events: none;
  }
}

.thumbnail-wrapper {
  width: 100%;
  aspect-ratio: 4/3;
  background: #f5f7fa;
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  overflow: hidden;
}

.thumbnail-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  transition: transform 0.3s ease;
}

.thumbnail-item:hover .thumbnail-img {
  transform: scale(1.05);
}

.thumbnail-loading,
.thumbnail-error {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: #c0c4cc;
  background: rgba(245, 247, 250, 0.8);
}

.loading-icon {
  animation: spin 1s linear infinite;
  font-size: 24px;
  margin-bottom: 8px;
}

.error-text,
.loading-text {
  font-size: 12px;
  margin-top: 4px;
}

@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}

.frame-info {
  padding: 8px;
  background: white;
  border-top: 1px solid #f0f0f0;
}

.frame-index {
  font-size: 14px;
  font-weight: 600;
  color: #303133;
  margin-bottom: 2px;
}

.frame-filename {
  font-size: 12px;
  color: #909399;
  word-break: break-all;
}

.pagination-controls {
  margin-top: 16px;
  display: flex;
  justify-content: center;
  flex-shrink: 0;
}

.empty-state {
  margin-top: 20px;
  border-top: 1px solid #e4e7ed;
  padding-top: 20px;
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: #909399;
  padding: 40px 0;
}

.empty-icon {
  font-size: 48px;
  margin-bottom: 16px;
}

.empty-tip {
  font-size: 14px;
  margin-top: 8px;
}

// 响应式设计
@media (max-width: 1200px) {
  .thumbnails-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 768px) {
  .thumbnails-grid {
    grid-template-columns: 1fr;
  }
  
  .folder-input-group {
    flex-direction: column;
  }
  
  .thumbnails-header {
    flex-direction: column;
    gap: 8px;
    align-items: flex-start;
  }
}
</style>