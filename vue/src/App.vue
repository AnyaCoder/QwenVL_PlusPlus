<template>
  <div id="app">
    <el-container class="app-container">
      <el-header class="app-header">
        <h1>视频帧分割工具</h1>
        <div class="header-info">
          <el-tag type="success" v-if="connected">已连接</el-tag>
          <el-tag type="danger" v-else>未连接</el-tag>
        </div>
      </el-header>

      <el-main class="app-main">
        <el-row :gutter="20" class="main-row">
          <el-col :span="8" class="left-panel">
            <FrameSelector
              v-model:folder-path="folderPath"
              @frame-selected="handleFrameSelected"
              @folder-update="handleFolderUpdate"
            />
          </el-col>

          <el-col :span="16" class="right-panel">
            <el-row :gutter="20" class="right-row">
              <!-- 左侧：CanvasViewer + 结果展示 -->
              <el-col :span="16" class="canvas-results-container">
                <!-- CanvasViewer 只占用必要高度 -->
                <div class="canvas-wrapper">
                  <CanvasViewer
                    :selected-frame="selectedFrame"
                    :folder-path="folderPath"
                    @selection-update="handleSelectionUpdate"
                  />
                </div>
                <!-- ResultsGallery 占用剩余高度 -->
                <div class="results-wrapper">
                  <ResultsGallery
                    :results="segmentationResults"
                    @remove-result="handleRemoveResult"
                    @view-result="handleViewResult"
                    @download-result="handleDownloadResult"
                    @clear-all="handleClearAllResults"
                  />
                </div>
              </el-col>
              
              <!-- 右侧：ControlPanel -->
              <el-col :span="8">
                <ControlPanel
                  :selected-frame="selectedFrame"
                  :bboxes="currentBbox"
                  :obj-ids="currentObjIds"
                  :folder-path="folderPath"
                  @reset-selection="handleResetSelection"
                  @segment-single="handleSegmentSingle"
                  @segment-batch="handleSegmentBatch"
                />
              </el-col>
            </el-row>
          </el-col>
        </el-row>
      </el-main>
    </el-container>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import FrameSelector from './components/FrameSelector.vue'
import CanvasViewer from './components/CanvasViewer.vue'
import ControlPanel from './components/ControlPanel.vue'
import ResultsGallery from './components/ResultsGallery.vue'

const folderPath = ref('../videos/output_0_mp4')
const selectedFrame = ref(null)
const currentBbox = ref([0, 0, 0, 0])
const connected = ref(true)
const segmentationResults = ref([])
const currentObjIds = ref([])

const handleFrameSelected = (frame) => {
  selectedFrame.value = frame
}

const handleFolderUpdate = (newPath) => {
  folderPath.value = newPath
  console.log('文件夹路径更新:', newPath)
}

const handleSelectionUpdate = (selectionData) => {
  currentBbox.value = selectionData.bboxes || [] // 改为数组
  currentObjIds.value = selectionData.obj_ids || [] // 新增
}

const handleResetSelection = () => {
  selectedFrame.value = null
  currentBbox.value = [0, 0, 0, 0]
}

const handleSegmentSingle = (result) => {
  console.log("handleSegmentSingle 接收到结果:", {
    result,
    hasImageData: !!result.imageData,
    imageDataLength: result.imageData ? result.imageData.length : 0
  })
  segmentationResults.value.unshift({
    id: Date.now() + Math.random(),
    frameIndex: result.frameIndex,
    filename: result.filename,
    status: 'success',
    timestamp: new Date().toLocaleTimeString(),
    imageData: result.imageData,
    duration: result.duration || 0
  })
}

const handleSegmentBatch = (results) => {
  Object.entries(results).forEach(([frameIdx, imageData]) => {
    segmentationResults.value.unshift({
      id: Date.now() + Math.random(),
      frameIndex: parseInt(frameIdx),
      filename: `frame_${frameIdx.padStart(5, '0')}.jpg`,
      status: 'success',
      timestamp: new Date().toLocaleTimeString(),
      imageData: imageData,
      duration: 0
    })
  })
}

const handleRemoveResult = (index) => {
  segmentationResults.value.splice(index, 1)
}
const handleClearAllResults = () => {
  segmentationResults.value = []
}
const handleViewResult = (result) => {
  console.log('查看结果:', result)
}

const handleDownloadResult = (result) => {
  try {
    const link = document.createElement('a')
    link.href = `data:image/jpeg;base64,${result.imageData}`
    link.download = `segmentation_result_frame_${result.frameIndex}.jpg`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
  } catch (error) {
    console.error('下载失败:', error)
  }
}
</script>

<style lang="scss">
#app {
  height: 100vh;
  background-color: #f5f7fa;
}

.app-container {
  height: 100%;
}

.app-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background-color: #fff;
  border-bottom: 1px solid #e4e7ed;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);

  h1 {
    margin: 0;
    color: #303133;
    font-size: 24px;
  }
}

.app-main {
  padding: 20px;
  height: calc(100% - 60px);
}

.main-row {
  height: 100%;
}

.left-panel,
.right-panel {
  height: 100%;
}

.right-row {
  height: 100%;
}

.canvas-results-container {
  display: flex;
  flex-direction: column;
  height: 100%;
  gap: 20px; /* 添加间距 */
}

.canvas-wrapper {
  flex-shrink: 0; /* 不收缩 */
  min-height: 400px; /* 最小高度 */
  max-height: 60vh; /* 最大高度 */
}

.results-wrapper {
  flex: 1; /* 占用剩余空间 */
  min-height: 200px; /* 最小高度 */
  overflow: hidden; /* 防止溢出 */
}

.el-card {
  height: 100%;
  display: flex;
  flex-direction: column;

  .el-card__body {
    flex: 1;
    display: flex;
    flex-direction: column;
  }
}
</style>