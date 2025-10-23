<template>
  <div class="control-panel">
    <el-card class="panel-card">
      <template #header>
        <div class="card-header">
          <span>分割控制面板</span>
        </div>
      </template>

      <!-- 当前选择信息 -->
      <div class="selection-info" v-if="selectedFrame && isBboxValid">
        <el-descriptions title="当前选择" :column="1" border size="small">
          <el-descriptions-item label="帧索引">
            <el-tag type="primary">{{ selectedFrame.index }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="文件名">
            <span class="filename">{{ selectedFrame.filename }}</span>
          </el-descriptions-item>
          <el-descriptions-item label="框选区域">
            <span class="bbox-info">
              [{{ Math.round(bbox[0]) }}, {{ Math.round(bbox[1]) }}, 
               {{ Math.round(bbox[2]) }}, {{ Math.round(bbox[3]) }}]
            </span>
          </el-descriptions-item>
          <el-descriptions-item label="目标ID">
            <el-input-number 
              v-model="segmentationParams.obj_id" 
              :min="1" 
              :max="10" 
              size="small"
              controls-position="right"
            />
          </el-descriptions-item>
        </el-descriptions>
      </div>

      <!-- 空状态提示 -->
      <div v-else class="empty-selection">
        <el-alert
          :title="getEmptyStateTitle"
          :description="getEmptyStateDescription"
          type="info"
          :closable="false"
          show-icon
        />
      </div>

      <!-- 分割参数设置 -->
      <div class="segmentation-params" v-if="selectedFrame && isBboxValid">
        <el-divider content-position="left">分割参数</el-divider>
        
        <div class="param-group">
          <el-form label-width="120px" size="small">
            <el-form-item label="置信度阈值">
              <el-slider
                v-model="segmentationParams.conf_threshold"
                :min="0.0"
                :max="1.0"
                :step="0.1"
                show-input
                :format-tooltip="formatConfidence"
              />
            </el-form-item>

            <el-form-item label="输出格式">
              <el-radio-group v-model="segmentationParams.output_format">
                <el-radio label="overlay">叠加显示</el-radio>
                <el-radio label="mask">二值掩模</el-radio>
                <el-radio label="both">两者都输出</el-radio>
              </el-radio-group>
            </el-form-item>

            <el-form-item label="随机颜色">
              <el-switch
                v-model="segmentationParams.random_color"
                active-text="启用"
                inactive-text="关闭"
              />
            </el-form-item>

            <el-form-item label="透明度" v-if="segmentationParams.output_format !== 'mask'">
              <el-slider
                v-model="segmentationParams.alpha"
                :min="0.1"
                :max="1.0"
                :step="0.1"
                show-input
              />
            </el-form-item>
          </el-form>
        </div>
      </div>

      <!-- 操作按钮 -->
      <div class="action-buttons" v-if="selectedFrame && isBboxValid">
        <el-divider content-position="left">操作控制</el-divider>
        
        <div class="button-group">
          <el-button 
            type="primary" 
            :loading="singleSegmentLoading" 
            @click="handleSingleSegment"
            class="action-button"
          >
            <template #icon>
              <el-icon><Camera /></el-icon>
            </template>
            分割当前帧
          </el-button>

          <el-button 
            type="success" 
            :loading="batchSegmentLoading" 
            @click="handleBatchSegment"
            class="action-button"
          >
            <template #icon>
              <el-icon><VideoCamera /></el-icon>
            </template>
            批量分割帧
          </el-button>

          <el-button 
            type="warning" 
            @click="handleResetSelection"
            class="action-button"
          >
            <template #icon>
              <el-icon><Refresh /></el-icon>
            </template>
            重置选择
          </el-button>
        </div>
      </div>

      <!-- 任务状态 -->
      <div class="task-status" v-if="taskStatus.active">
        <el-divider content-position="left">任务状态</el-divider>
        
        <div class="status-content">
          <el-alert
            :title="taskStatus.title"
            :type="taskStatus.type"
            :description="taskStatus.description"
            :closable="false"
            show-icon
          />
          
          <div class="progress-section" v-if="taskStatus.progress > 0">
            <div class="progress-info">
              <span>处理进度</span>
              <span class="processed-frames" v-if="taskStatus.processedFrames">
                {{ taskStatus.processedFrames }} 帧已完成
              </span>
            </div>
            <el-progress 
              :percentage="taskStatus.progress" 
              :status="taskStatus.progress === 100 ? 'success' : undefined"
              :stroke-width="8"
            />
          </div>

          <div class="task-actions" v-if="taskStatus.taskId">
            <el-button 
              size="small" 
              @click="handleCheckStatus"
              :loading="checkingStatus"
            >
              刷新状态
            </el-button>
          </div>
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, defineProps, defineEmits } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Camera, VideoCamera, Refresh } from '@element-plus/icons-vue'
import { api } from '../services/api'

const props = defineProps({
  selectedFrame: {
    type: Object,
    default: null
  },
  bbox: {
    type: Array,
    default: () => [0, 0, 0, 0]
  },
  folderPath: {
    type: String,
    default: ''
  }
})

const emit = defineEmits(['reset-selection', 'segment-single', 'segment-batch'])

// 响应式数据
const segmentationParams = ref({
  obj_id: 1,
  conf_threshold: 0.0,
  output_format: 'overlay',
  random_color: false,
  alpha: 0.6
})

const singleSegmentLoading = ref(false)
const batchSegmentLoading = ref(false)
const checkingStatus = ref(false)

const taskStatus = ref({
  active: false,
  title: '',
  type: 'info',
  description: '',
  progress: 0,
  processedFrames: 0,
  taskId: null
})

// 计算属性
const isBboxValid = computed(() => {
  return props.bbox && props.bbox[2] > 5 && props.bbox[3] > 5
})

const getEmptyStateTitle = computed(() => {
  if (!props.selectedFrame) return '请先选择帧图像'
  if (!isBboxValid.value) return '请设置有效的框选区域'
  return '准备就绪'
})

const getEmptyStateDescription = computed(() => {
  if (!props.selectedFrame) return '在左侧选择一帧图像并在画布上进行框选'
  if (!isBboxValid.value) return '框选区域太小，请选择更大的区域进行分割'
  return '可以开始分割操作了'
})

// 方法
const formatConfidence = (value) => {
  return value === 0 ? '0 (无阈值)' : value.toFixed(1)
}

const convertBboxToBackendFormat = (bbox) => {
  const [x1, y1, x2, y2] = bbox
  return [x1, y1, x2, y2]
}

const handleSingleSegment = async () => {
  if (!props.selectedFrame || !isBboxValid.value || !props.folderPath) {
    ElMessage.error('请先选择帧图像、设置有效的框选区域并确保文件夹路径正确')
    return
  }

  singleSegmentLoading.value = true

  try {
    const requestData = {
      video_path: props.folderPath,
      frame_idx: props.selectedFrame.index,
      filename: props.selectedFrame.filename,
      obj_id: segmentationParams.value.obj_id,
      bbox: convertBboxToBackendFormat(props.bbox),
      conf_threshold: segmentationParams.value.conf_threshold
    }

    console.log('发送单帧分割请求:', requestData)

    const response = await api.segmentFrame(requestData)

    if (response.status === 'queued' && response.task_id) {
      ElMessage.success('单帧分割任务已提交，正在处理...')
      
      // 设置任务状态
      taskStatus.value = {
        active: true,
        title: '单帧分割进行中',
        type: 'info',
        description: '正在处理当前帧...',
        progress: 0,
        processedFrames: 0,
        taskId: response.task_id
      }

      // 启动任务状态监控
      startTaskPolling(response.task_id)
    } else {
      throw new Error('任务提交失败')
    }
  } catch (error) {
    console.error('单帧分割失败:', error)
    ElMessage.error(`分割失败: ${error.response?.data?.detail || error.message}`)
  } finally {
    singleSegmentLoading.value = false
  }
}

const handleBatchSegment = async () => {
  if (!props.selectedFrame || !isBboxValid.value || !props.folderPath) {
    ElMessage.error('请先选择帧图像、设置有效的框选区域并确保文件夹路径正确')
    return
  }

  try {
    await ElMessageBox.confirm(
      '这将处理当前文件夹中的所有帧图像，可能需要较长时间。是否继续？',
      '批量分割确认',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )

    batchSegmentLoading.value = true

    // 获取文件夹中的所有帧
    const folderResponse = await api.scanFolder(props.folderPath)
    if (!folderResponse.success) {
      throw new Error('无法扫描文件夹')
    }

    const allFrames = folderResponse.frames
    const frameIndices = allFrames.map(frame => frame.index)

    const requestData = {
      video_path: props.folderPath,
      filename: props.selectedFrame.filename,
      frame_indices: frameIndices,
      obj_ids: Array(frameIndices.length).fill(segmentationParams.value.obj_id),
      bboxes: Array(frameIndices.length).fill(convertBboxToBackendFormat(props.bbox)),
      conf_threshold: segmentationParams.value.conf_threshold
    }

    console.log('发送批量分割请求:', requestData)

    const response = await api.segmentFrames(requestData)

    if (response.status === 'queued' && response.task_id) {
      ElMessage.success(`批量分割任务已提交，共 ${frameIndices.length} 帧`)

      // 设置任务状态
      taskStatus.value = {
        active: true,
        title: '批量分割进行中',
        type: 'info',
        description: `正在处理 ${frameIndices.length} 帧图像...`,
        progress: 0,
        processedFrames: 0,
        totalFrames: frameIndices.length,
        taskId: response.task_id
      }

      // 启动任务状态监控
      startBatchTaskPolling(response.task_id, frameIndices)
    } else {
      throw new Error('批量任务提交失败')
    }
  } catch (error) {
    if (error !== 'cancel') {
      console.error('批量分割失败:', error)
      ElMessage.error(`批量分割失败: ${error.response?.data?.detail || error.message}`)
    }
  } finally {
    batchSegmentLoading.value = false
  }
}

const startTaskPolling = (taskId) => {  // 移除 type 参数
  const pollInterval = setInterval(async () => {
    try {
      const status = await api.getTaskStatus(taskId)
      
      if (status.status === 'done') {
        clearInterval(pollInterval)
        
        taskStatus.value = {
          ...taskStatus.value,
          title: '分割完成',
          type: 'success',
          description: '单帧分割任务已完成',
          progress: 100,
          processedFrames: 1
        }
        // 发射结果给父组件
        if (status.result) {
          const frameKey = Object.keys(status.result)[0]
          emit('segment-single', {
            frameIndex: props.selectedFrame.index,
            filename: props.selectedFrame.filename,
            imageData: status.result[frameKey],
            duration: 0
          })
        }
        
        ElMessage.success('分割任务完成')
      } else if (status.status === 'error') {
        clearInterval(pollInterval)
        
        taskStatus.value = {
          ...taskStatus.value,
          title: '分割失败',
          type: 'error',
          description: status.result || '处理过程中发生错误'
        }
        
        ElMessage.error(`分割失败: ${status.result}`)
      }
      // 对于 processing 状态，继续轮询
    } catch (error) {
      console.error('轮询任务状态失败:', error)
      clearInterval(pollInterval)
    }
  }, 1000)
}

const startBatchTaskPolling = (taskId, frameIndices) => {
  const pollInterval = setInterval(async () => {
    try {
      const status = await api.getTaskStatus(taskId)
      
      if (status.status === 'done') {
        clearInterval(pollInterval)
        taskStatus.value = {
          ...taskStatus.value,
          title: '批量分割完成',
          type: 'success',
          description: `成功处理 ${frameIndices.length} 帧图像`,
          progress: 100,
          processedFrames: frameIndices.length
        }

        // 发射批量结果给父组件
        if (status.result) {
          emit('segment-batch', status.result)
        }
        
        ElMessage.success('批量分割任务完成')
      } else if (status.status === 'error') {
        clearInterval(pollInterval)
        taskStatus.value = {
          ...taskStatus.value,
          title: '批量分割失败',
          type: 'error',
          description: status.result || '处理过程中发生错误'
        }
        ElMessage.error(`批量分割失败: ${status.result}`)
      } else if (status.status === 'processing') {
        // 更新进度
        const processedCount = Object.keys(status.frames || {}).length
        const progress = Math.round((processedCount / frameIndices.length) * 100)
        
        taskStatus.value = {
          ...taskStatus.value,
          progress: progress,
          processedFrames: processedCount,
          description: `已处理 ${processedCount}/${frameIndices.length} 帧`
        }
      }
    } catch (error) {
      console.error('轮询批量任务状态失败:', error)
      clearInterval(pollInterval)
    }
  }, 2000)
}

const handleCheckStatus = async () => {
  if (!taskStatus.value.taskId) return
  
  checkingStatus.value = true
  try {
    await api.getTaskStatus(taskStatus.value.taskId)
    ElMessage.success('状态更新成功')
  } catch (error) {
    ElMessage.error('获取任务状态失败')
  } finally {
    checkingStatus.value = false
  }
}

const handleResetSelection = () => {
  emit('reset-selection')
}
</script>


<style scoped lang="scss">
.control-panel {
  height: 100%;
}

.panel-card {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.card-header {
  font-weight: 600;
  color: #303133;
}

.selection-info {
  margin-bottom: 16px;
}

.filename {
  font-size: 12px;
  color: #606266;
}

.bbox-info {
  font-size: 12px;
  color: #e6a23c;
}

.empty-selection {
  margin-bottom: 16px;
}

.segmentation-params {
  margin-bottom: 20px;
}

.param-group {
  .el-form-item {
    margin-bottom: 16px;
  }
}

.action-buttons {
  margin-bottom: 20px;
}

.button-group {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.action-button {
  width: 100%;
  justify-content: flex-start;
}

.task-status {
  margin-bottom: 20px;
}

.status-content {
  .progress-section {
    margin-top: 12px;
  }
  
  .progress-info {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 8px;
    font-size: 14px;
    color: #606266;
  }
  
  .processed-frames {
    color: #909399;
    font-size: 12px;
  }
  
  .task-actions {
    margin-top: 12px;
    display: flex;
    gap: 8px;
    justify-content: flex-end;
  }
}

// 响应式设计
@media (max-width: 768px) {
  .button-group {
    flex-direction: column;
  }
  
  .action-button {
    width: 100%;
  }
}
</style>