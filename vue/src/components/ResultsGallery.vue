<template>
  <div class="results-gallery">

    <div class="debug-info" v-if="false"> <!-- 设置为 true 来显示调试信息 -->
      <el-alert
        :title="`调试信息: ${results.length} 个结果`"
        :description="debugInfo"
        type="info"
        :closable="false"
      />
    </div>

    <el-card class="gallery-card">
      <template #header>
        <div class="gallery-header">
          <span>分割结果</span>
          <el-button 
            type="danger" 
            size="small" 
            @click="clearAllResults"
            :disabled="results.length === 0"
          >
            清空所有结果
          </el-button>
        </div>
      </template>

      <div class="gallery-container">
        <div 
          v-for="(result, index) in results" 
          :key="result.id"
          class="gallery-item"
        >
          <div class="result-card">
            <div class="result-header">
              <span class="result-title">帧 {{ result.frameIndex }}</span>
              <el-button 
                type="danger" 
                size="small" 
                text 
                @click="removeResult(index)"
                class="close-btn"
              >
                <el-icon><Close /></el-icon>
              </el-button>
            </div>
            <img 
              :src="'data:image/jpeg;base64,' + result.imageData" 
              :alt="`分割结果 - 帧 ${result.frameIndex}`"
              class="result-thumbnail"
              @click="handleViewResult(result)"
            />
            <div class="result-info">
              <el-tag :type="getResultTagType(result.status)" size="small">
                {{ getResultStatusText(result.status) }}
              </el-tag>
              <span class="result-time">{{ result.timestamp }}</span>
            </div>
            <div class="result-actions">
              <el-button 
                size="mini" 
                @click="handleViewResult(result)"
              >
                查看大图
              </el-button>
              <el-button 
                size="mini" 
                type="primary" 
                @click="handleDownloadResult(result)"
              >
                下载
              </el-button>
            </div>
          </div>
        </div>
      </div>
    </el-card>

    <!-- 结果查看模态框 -->
    <el-dialog
      v-model="resultDialogVisible"
      :title="`分割结果 - 帧 ${selectedResult?.frameIndex}`"
      width="70%"
      top="5vh"
    >
      <div class="result-dialog-content" v-if="selectedResult">
        <img 
          :src="'data:image/jpeg;base64,' + selectedResult.imageData" 
          :alt="`分割结果 - 帧 ${selectedResult.frameIndex}`"
          class="result-dialog-image"
        />
      </div>
      <template #footer>
        <el-button @click="resultDialogVisible = false">关闭</el-button>
        <el-button type="primary" @click="handleDownloadDialogResult">
          下载图片
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, defineProps, defineEmits, toRefs} from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Close } from '@element-plus/icons-vue'

const props = defineProps({
  results: {
    type: Array,
    default: () => []
  }
})
const { results } = toRefs(props)


const emit = defineEmits(['remove-result', 'view-result', 'download-result', 'clear-all'])

const resultDialogVisible = ref(false)
const selectedResult = ref(null)

const removeResult = (index) => {
  emit('remove-result', index)
}

const clearAllResults = async () => {
  try {
    await ElMessageBox.confirm(
      '确定要清空所有分割结果吗？此操作不可撤销。',
      '清空确认',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )
    
    // 发射清空所有结果的事件，由父组件处理
    emit('clear-all')
    ElMessage.success('已清空所有结果')
  } catch (error) {
    if (error !== 'cancel') {
      console.error('清空结果失败:', error)
    }
  }
}

const handleViewResult = (result) => {
  selectedResult.value = result
  resultDialogVisible.value = true
  emit('view-result', result)
}

const handleDownloadResult = (result) => {
  emit('download-result', result)
}

const handleDownloadDialogResult = () => {
  if (selectedResult.value) {
    handleDownloadResult(selectedResult.value)
  }
  resultDialogVisible.value = false
}

const getResultTagType = (status) => {
  const typeMap = {
    'success': 'success',
    'error': 'danger',
    'processing': 'warning'
  }
  return typeMap[status] || 'info'
}

const getResultStatusText = (status) => {
  const textMap = {
    'success': '成功',
    'error': '失败',
    'processing': '处理中'
  }
  return textMap[status] || status
}
</script>

<style scoped lang="scss">
.results-gallery {
  height: 100%; /* 填充父容器 */
}

.gallery-card {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.gallery-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-shrink: 0; /* 头部不收缩 */
}

.gallery-container {
  flex: 1; /* 画廊容器占用剩余空间 */
  display: flex;
  gap: 16px;
  overflow-x: auto;
  overflow-y: hidden; /* 只在水平方向滚动 */
  padding: 8px 0;
  scrollbar-width: thin;
  scrollbar-color: #c0c4cc #f5f7fa;

  &::-webkit-scrollbar {
    height: 8px;
  }

  &::-webkit-scrollbar-track {
    background: #f5f7fa;
    border-radius: 4px;
  }

  &::-webkit-scrollbar-thumb {
    background: #c0c4cc;
    border-radius: 4px;
    
    &:hover {
      background: #909399;
    }
  }
}

.gallery-item {
  flex: 0 0 auto;
}

.result-card {
  width: 200px;
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  overflow: hidden;
  background: white;
  transition: all 0.3s ease;
  
  &:hover {
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
    transform: translateY(-2px);
  }
}

.result-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  background: #fafafa;
  border-bottom: 1px solid #e4e7ed;
}

.result-title {
  font-size: 14px;
  font-weight: 600;
  color: #303133;
}

.close-btn {
  padding: 4px;
  min-height: auto;
  
  &:hover {
    background: #fef0f0;
    color: #f56c6c;
  }
}

.result-thumbnail {
  width: 100%;
  height: 120px;
  object-fit: cover;
  cursor: pointer;
  transition: transform 0.2s;
  
  &:hover {
    transform: scale(1.05);
  }
}

.result-info {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  font-size: 12px;
}

.result-time {
  color: #909399;
}

.result-actions {
  display: flex;
  gap: 8px;
  padding: 8px 12px;
  border-top: 1px solid #f0f0f0;
  
  .el-button {
    flex: 1;
  }
}

.result-dialog-content {
  text-align: center;
}

.result-dialog-image {
  max-width: 100%;
  max-height: 70vh;
  border: 1px solid #e4e7ed;
  border-radius: 4px;
}

// 响应式设计
@media (max-width: 768px) {
  .gallery-container {
    gap: 12px;
  }
  
  .result-card {
    width: 180px;
  }
  
  .result-actions {
    flex-direction: column;
    gap: 4px;
  }
}
</style>