<template>
  <div class="canvas-viewer">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>帧预览与选择</span>
          <div class="selection-mode">
            <el-radio-group v-model="selectionMode" size="small">
              <el-radio-button label="point">点选模式</el-radio-button>
              <el-radio-button label="box">框选模式</el-radio-button>
            </el-radio-group>
          </div>
        </div>
      </template>

      <div class="canvas-container">
        <!-- 加载状态 -->
        <div v-if="loading" class="loading-state">
          <el-icon class="loading-icon"><Loading /></el-icon>
          <span>加载帧图像中...</span>
        </div>
        
        <!-- 空状态 -->
        <div v-else-if="!selectedFrame" class="empty-state">
          <el-icon class="empty-icon"><Picture /></el-icon>
          <span>请先选择一帧图像</span>
        </div>
        
        <!-- 错误状态 -->
        <div v-else-if="imageError" class="error-state">
          <el-icon class="error-icon"><Warning /></el-icon>
          <span>图像加载失败</span>
          <p class="error-tip">请检查文件路径和网络连接</p>
          <el-button type="primary" @click="retryLoadImage" size="small">
            重新加载
          </el-button>
        </div>
        
        <!-- 图像和画布容器 -->
        <div v-else class="image-container" ref="imageContainer">
          <img
            ref="imageEl"
            :src="currentImageUrl"
            :alt="`Frame ${selectedFrame?.index}`"
            class="frame-image"
            @load="handleImageLoad"
            @error="handleImageError"
          />
          <canvas
            ref="canvasEl"
            class="overlay-canvas"
            @mousedown="handleMouseDown"
            @mousemove="handleMouseMove"
            @mouseup="handleMouseUp"
            @mouseleave="handleMouseLeave"
          ></canvas>
        </div>
      </div>

      <!-- 坐标信息显示 -->
      <div v-if="selectedFrame && !imageError" class="coordinates-info">
        <el-descriptions :column="3" border size="small">
          <el-descriptions-item label="当前帧">
            {{ selectedFrame.index }} - {{ selectedFrame.filename }}
          </el-descriptions-item>
          <el-descriptions-item label="框选区域" :span="2">
            [x: {{ bbox[0]?.toFixed(0) }}, y: {{ bbox[1]?.toFixed(0) }}, width: {{ bbox[2]?.toFixed(0) }}, height: {{ bbox[3]?.toFixed(0) }}]
          </el-descriptions-item>
          <el-descriptions-item label="图像尺寸" :span="2" v-if="imageDimensions.width">
            {{ imageDimensions.width }} × {{ imageDimensions.height }} 像素
          </el-descriptions-item>
        </el-descriptions>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, watch, onMounted, defineProps, defineEmits, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import { api } from '../services/api'

const props = defineProps({
  selectedFrame: {
    type: Object,
    default: null
  },
  folderPath: {
    type: String,
    default: ''
  }
})

const emit = defineEmits(['selection-update'])

// 响应式数据
const imageEl = ref(null)
const canvasEl = ref(null)
const imageContainer = ref(null)
const ctx = ref(null)
const selectionMode = ref('box')
const isSelecting = ref(false)
const loading = ref(false)
const imageError = ref(false)
const currentImageUrl = ref('')

const startPoint = ref({ x: 0, y: 0 })
const endPoint = ref({ x: 0, y: 0 })
const bbox = ref([0, 0, 0, 0])
const imageDimensions = ref({ width: 0, height: 0 })
const displayDimensions = ref({ width: 0, height: 0 })
const scaleFactor = ref({ x: 1, y: 1 })

// 监听选中的帧变化
watch(() => props.selectedFrame, async (newFrame) => {
  if (newFrame) {
    await loadFrameImage(newFrame)
    resetSelection()
  } else {
    clearCanvas()
    currentImageUrl.value = ''
    imageError.value = false
  }
})

// 监听文件夹路径变化
watch(() => props.folderPath, () => {
  if (props.selectedFrame) {
    loadFrameImage(props.selectedFrame)
  }
})

// 加载帧图像
const loadFrameImage = async (frame) => {
  if (!props.folderPath) {
    ElMessage.error('请先选择文件夹路径')
    return
  }

  loading.value = true
  imageError.value = false

  try {
    const imageUrl = api.getFrameImageUrl(props.folderPath, frame.filename)
    console.log('Loading image URL:', imageUrl)
    
    currentImageUrl.value = imageUrl
    
    // 等待图像加载完成
    await new Promise((resolve, reject) => {
      const img = new Image()
      img.onload = () => {
        imageDimensions.value = {
          width: img.naturalWidth,
          height: img.naturalHeight
        }
        resolve()
      }
      img.onerror = () => {
        reject(new Error('图像加载失败'))
      }
      img.src = imageUrl
    })

    await nextTick()
    setupCanvas()

  } catch (error) {
    console.error('加载帧图像失败:', error)
    imageError.value = true
    ElMessage.error(`图像加载失败: ${frame.filename}`)
  } finally {
    loading.value = false
  }
}

// 设置Canvas，考虑图像缩放
const setupCanvas = () => {
  if (!imageEl.value || !canvasEl.value || !imageContainer.value) return
  
  const img = imageEl.value
  const canvas = canvasEl.value
  
  // 获取图像在页面上的实际显示尺寸
  const displayWidth = img.clientWidth
  const displayHeight = img.clientHeight
  
  displayDimensions.value = {
    width: displayWidth,
    height: displayHeight
  }
  
  // 计算缩放因子
  scaleFactor.value = {
    x: imageDimensions.value.width / displayWidth,
    y: imageDimensions.value.height / displayHeight
  }
  
  console.log('Image dimensions:', imageDimensions.value)
  console.log('Display dimensions:', displayDimensions.value)
  console.log('Scale factor:', scaleFactor.value)
  
  // 设置Canvas尺寸匹配图像显示尺寸
  canvas.width = displayWidth
  canvas.height = displayHeight
  
  // 获取2D上下文
  ctx.value = canvas.getContext('2d')
  clearCanvas()
}

// 清除Canvas
const clearCanvas = () => {
  if (ctx.value && canvasEl.value) {
    ctx.value.clearRect(0, 0, canvasEl.value.width, canvasEl.value.height)
  }
}

// 绘制选择区域
const drawSelection = () => {
  if (!ctx.value || !canvasEl.value) return

  clearCanvas()

  ctx.value.strokeStyle = '#e6a23c'
  ctx.value.lineWidth = 2
  ctx.value.setLineDash([])

  if (selectionMode.value === 'point') {
    const size = 10
    const x = startPoint.value.x
    const y = startPoint.value.y

    // 绘制十字准星
    ctx.value.beginPath()
    ctx.value.moveTo(x - size, y)
    ctx.value.lineTo(x + size, y)
    ctx.value.moveTo(x, y - size)
    ctx.value.lineTo(x, y + size)
    ctx.value.stroke()

    // 绘制矩形框
    ctx.value.strokeRect(
      x - size / 2,
      y - size / 2,
      size,
      size
    )
  } else {
    // 绘制框选矩形，确保坐标正确
    const [x, y, width, height] = bbox.value
    ctx.value.strokeRect(x, y, width, height)
    
    // 添加半透明填充
    ctx.value.fillStyle = 'rgba(230, 162, 60, 0.1)'
    ctx.value.fillRect(x, y, width, height)
  }
}

// 获取Canvas坐标，考虑滚动和偏移
const getCanvasCoordinates = (event) => {
  if (!canvasEl.value) return { x: 0, y: 0 }
  
  const rect = canvasEl.value.getBoundingClientRect()
  const x = event.clientX - rect.left
  const y = event.clientY - rect.top
  
  // 确保坐标在Canvas范围内
  return {
    x: Math.max(0, Math.min(x, canvasEl.value.width)),
    y: Math.max(0, Math.min(y, canvasEl.value.height))
  }
}

// 将显示坐标转换为原始图像坐标
const convertToImageCoordinates = (displayBbox) => {
  const [x, y, width, height] = displayBbox
  return [
    Math.round(x * scaleFactor.value.x),
    Math.round(y * scaleFactor.value.y),
    Math.round((x + width) * scaleFactor.value.x),
    Math.round((y + height) * scaleFactor.value.y)
  ]
}

// 鼠标事件处理
const handleMouseDown = (event) => {
  if (!props.selectedFrame || imageError.value) return

  const { x, y } = getCanvasCoordinates(event)
  isSelecting.value = true

  if (selectionMode.value === 'point') {
    startPoint.value = { x, y }
    endPoint.value = { x, y }
    updateBbox()
    drawSelection()
    emitSelection()
  } else {
    startPoint.value = { x, y }
    endPoint.value = { x, y }
  }
}

const handleMouseMove = (event) => {
  if (!isSelecting.value || selectionMode.value !== 'box') return

  const { x, y } = getCanvasCoordinates(event)
  endPoint.value = { x, y }
  updateBbox()
  drawSelection()
}

const handleMouseUp = () => {
  if (!isSelecting.value) return

  isSelecting.value = false

  if (selectionMode.value === 'box') {
    // 确保宽度和高度为正数
    const startX = Math.min(startPoint.value.x, endPoint.value.x)
    const startY = Math.min(startPoint.value.y, endPoint.value.y)
    const endX = Math.max(startPoint.value.x, endPoint.value.x)
    const endY = Math.max(startPoint.value.y, endPoint.value.y)

    startPoint.value = { x: startX, y: startY }
    endPoint.value = { x: endX, y: endY }
    updateBbox()
    drawSelection()
    emitSelection()
  }
}

const handleMouseLeave = () => {
  if (isSelecting.value) {
    handleMouseUp()
  }
}

// 更新边界框
const updateBbox = () => {
  if (selectionMode.value === 'point') {
    const size = 10
    bbox.value = [
      Math.max(0, startPoint.value.x - size / 2),
      Math.max(0, startPoint.value.y - size / 2),
      size,
      size
    ]
  } else {
    const startX = Math.min(startPoint.value.x, endPoint.value.x)
    const startY = Math.min(startPoint.value.y, endPoint.value.y)
    const endX = Math.max(startPoint.value.x, endPoint.value.x)
    const endY = Math.max(startPoint.value.y, endPoint.value.y)
    
    bbox.value = [
      startX,
      startY,
      endX - startX,  // width
      endY - startY   // height
    ]
  }
}

// 发射选择事件
const emitSelection = () => {
  const imageBbox = convertToImageCoordinates(bbox.value)
  console.log('Display bbox:', bbox.value)
  console.log('Image bbox:', imageBbox)
  emit('selection-update', imageBbox)
}

// 重置选择
const resetSelection = () => {
  startPoint.value = { x: 0, y: 0 }
  endPoint.value = { x: 0, y: 0 }
  bbox.value = [0, 0, 0, 0]
  clearCanvas()
  emit('selection-update', [0, 0, 0, 0])
}

// 图像加载事件
const handleImageLoad = () => {
  console.log('图像加载成功')
  setupCanvas()
}

const handleImageError = () => {
  console.error('图像加载失败')
  imageError.value = true
  loading.value = false
}

// 监听选择模式变化
watch(selectionMode, () => {
  resetSelection()
})

onMounted(() => {
  // 初始设置
  if (canvasEl.value) {
    ctx.value = canvasEl.value.getContext('2d')
    clearCanvas()
  }
})
</script>

<style scoped lang="scss">
.canvas-viewer {
  height: 100%; /* 让 CanvasViewer 填充父容器 */
}

.canvas-card {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-shrink: 0; /* 头部不收缩 */
}

.canvas-container {
  flex: 1; /* 画布容器占用剩余空间 */
  border: 1px solid #e4e7ed;
  border-radius: 4px;
  overflow: hidden;
  background: #f5f7fa;
  min-height: 300px;
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;

  .image-container {
    position: relative;
    display: inline-block;
    max-width: 100%;
    max-height: 100%; /* 限制最大高度 */
  }

  .frame-image {
    display: block;
    max-width: 100%;
    max-height: 100%; /* 限制图像最大高度 */
    object-fit: contain;
  }

  .overlay-canvas {
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    cursor: crosshair;
  }
}

.loading-state,
.empty-state,
.error-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: #909399;
  padding: 40px;
  text-align: center;
  
  .loading-icon {
    font-size: 32px;
    margin-bottom: 12px;
    animation: spin 1s linear infinite;
  }
  
  .empty-icon,
  .error-icon {
    font-size: 32px;
    margin-bottom: 12px;
  }

  .error-tip {
    font-size: 14px;
    margin: 8px 0 16px 0;
    color: #c0c4cc;
  }
}

@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}

.coordinates-info {
  margin-top: 16px;
  flex-shrink: 0; /* 坐标信息不收缩 */
}

// 新增：结果画廊样式
.results-gallery {
  margin-top: 20px;
}

.gallery-container {
  display: flex;
  gap: 16px;
  overflow-x: auto;
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
  .card-header {
    flex-direction: column;
    gap: 8px;
    align-items: flex-start;
  }
  
  .selection-mode {
    width: 100%;
    justify-content: flex-start;
  }
  
  .gallery-container {
    gap: 12px;
  }
  
  .result-card {
    width: 180px;
  }
}
</style>