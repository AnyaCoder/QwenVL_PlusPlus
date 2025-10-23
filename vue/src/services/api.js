import axios from 'axios'

// 根据环境配置基础URL
const API_BASE = process.env.NODE_ENV === 'development' ? '/api' : 'http://localhost:8000'

const apiClient = axios.create({
  baseURL: API_BASE,
  timeout: 30000,
})

// 请求拦截器
apiClient.interceptors.request.use(config => config, error => Promise.reject(error))

// 响应拦截器
apiClient.interceptors.response.use(response => response.data, error => Promise.reject(error))

export const api = {
  // 扫描文件夹
  scanFolder: async (folderPath) => {
    return await apiClient.post('/scan_folder', { folder_path: folderPath })
  },

  // 获取单帧图像 URL
  getFrameImageUrl: (folderPath, filename) => {
    // 这里返回的 URL 可以直接绑定到 <img src="">
    // 前端 /api 会代理到 FastAPI 服务
    return `${API_BASE}/frame_image?folder_path=${encodeURIComponent(folderPath)}&filename=${encodeURIComponent(filename)}`
  },
  // 其他接口
  segmentFrame: async (data) => await apiClient.post('/segment_frame', data),
  segmentFrames: async (data) => await apiClient.post('/segment_frames', data),
  getTaskStatus: async (taskId) => await apiClient.get(`/task_status/${taskId}`)
}
