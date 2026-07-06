import { createRouter, createWebHistory } from 'vue-router'
import { setupAuthGuard } from './guards'

// 布局组件
const AuthLayout = () => import('@/components/layout/AuthLayout.vue')
const MainLayout = () => import('@/components/layout/MainLayout.vue')

// 页面组件
const Login = () => import('@/views/Login.vue')
const Register = () => import('@/views/Register.vue')
const Dashboard = () => import('@/views/Dashboard.vue')
const Projects = () => import('@/views/Projects.vue')
const ProjectDetail = () => import('@/components/project/ProjectDetail.vue')
// const GenerationQueue = () => import('@/views/GenerationQueue.vue')
const GenerationSettings = () => import('@/views/GenerationSettings.vue')
const Publish = () => import('@/views/Publish.vue')
const APIKeys = () => import('@/views/APIKeys.vue')
const Settings = () => import('@/views/Settings.vue')
const CanvasList = () => import('@/views/canvas/CanvasList.vue')
const CanvasEditor = () => import('@/views/canvas/CanvasEditor.vue')
const TasksHistory = () => import('@/views/TasksHistory.vue')
const AssetsLibrary = () => import('@/views/AssetsLibrary.vue')
const WorksLibrary = () => import('@/views/WorksLibrary.vue')

const routes = [
  {
    path: '/',
    name: 'Home',
    redirect: '/dashboard'
  },
  {
    path: '/login',
    name: 'Login',
    component: AuthLayout,
    meta: { requiresGuest: true },
    children: [
      {
        path: '',
        name: 'LoginPage',
        component: Login,
        props: {
          title: '欢迎回来',
          subtitle: '登录您的账户继续使用AI内容生成平台'
        }
      }
    ]
  },
  {
    path: '/register',
    name: 'Register',
    component: AuthLayout,
    meta: { requiresGuest: true },
    children: [
      {
        path: '',
        name: 'RegisterPage',
        component: Register,
        props: {
          title: '创建账户',
          subtitle: '加入AICG平台，开始您的AI内容创作之旅'
        }
      }
    ]
  },
  {
    path: '/dashboard',
    name: 'Dashboard',
    component: MainLayout,
    meta: { requiresAuth: true },
    children: [
      {
        path: '',
        name: 'DashboardPage',
        component: Dashboard
      }
    ]
  },
  {
    path: '/projects',
    name: 'Projects',
    component: MainLayout,
    meta: { requiresAuth: true },
    children: [
      {
        path: '',
        name: 'ProjectsPage',
        component: Projects
      },
      {
        path: ':projectId',
        name: 'ProjectDetail',
        component: ProjectDetail,
        props: true
      },
      {
        path: ':projectId/studio',
        name: 'ContentStudio',
        component: () => import('@/views/studio/ContentStudio.vue'),
        props: true
      },
      {
        path: ':projectId/director',
        name: 'DirectorEngine',
        component: () => import('@/views/studio/DirectorEngine.vue'),
        props: true
      },
      {
        path: ':projectId/chapters/:chapterId/movie-studio',
        name: 'MovieStudio',
        component: () => import('@/views/studio/MovieStudio.vue'),
        meta: { title: '电影工作室' },
        props: true
      }
    ]
  },
  {
    path: '/canvas',
    name: 'Canvas',
    component: MainLayout,
    meta: { requiresAuth: true },
    children: [
      {
        path: '',
        name: 'CanvasList',
        component: CanvasList
      },
      {
        path: ':canvasId',
        name: 'CanvasEditor',
        component: CanvasEditor,
        props: true
      }
    ]
  },
  {
    path: '/generation',
    name: 'Generation',
    component: MainLayout,
    meta: { requiresAuth: true },
    children: [
      {
        path: '',
        name: 'GenerationPage',
        component: () => import('@/views/VideoTasks.vue')
      }
    ]
  },
  {
    path: '/tasks',
    name: 'TasksHistory',
    component: MainLayout,
    meta: { requiresAuth: true },
    children: [
      {
        path: '',
        name: 'TasksHistoryPage',
        component: TasksHistory
      }
    ]
  },
  {
    path: '/library',
    name: 'AssetsLibrary',
    component: MainLayout,
    meta: { requiresAuth: true },
    children: [
      {
        path: '',
        name: 'AssetsLibraryPage',
        component: AssetsLibrary
      }
    ]
  },
  {
    path: '/works',
    name: 'WorksLibrary',
    component: MainLayout,
    meta: { requiresAuth: true },
    children: [
      {
        path: '',
        name: 'WorksLibraryPage',
        component: WorksLibrary
      }
    ]
  },
  {
    path: '/generation/settings',
    name: 'GenerationSettings',
    component: MainLayout,
    meta: { requiresAuth: true },
    children: [
      {
        path: '',
        name: 'GenerationSettingsPage',
        component: GenerationSettings
      }
    ]
  },
  {
    path: '/bgm-management',
    name: 'BGMManagement',
    component: MainLayout,
    meta: { requiresAuth: true },
    children: [
      {
        path: '',
        name: 'BGMManagementPage',
        component: () => import('@/views/BGMManagement.vue')
      }
    ]
  },
  {
    path: '/bilibili-accounts',
    name: 'BilibiliAccounts',
    component: MainLayout,
    meta: { requiresAuth: true },
    children: [
      {
        path: '',
        name: 'BilibiliAccountsPage',
        component: () => import('@/views/BilibiliAccounts.vue')
      }
    ]
  },
  {
    path: '/publish',
    name: 'Publish',
    component: MainLayout,
    meta: { requiresAuth: true },
    children: [
      {
        path: '',
        name: 'PublishPage',
        component: Publish
      }
    ]
  },
  {
    path: '/api-keys',
    name: 'APIKeys',
    component: MainLayout,
    meta: { requiresAuth: true },
    children: [
      {
        path: '',
        name: 'APIKeysPage',
        component: APIKeys
      }
    ]
  },
  {
    path: '/settings',
    name: 'Settings',
    component: MainLayout,
    meta: { requiresAuth: true },
    children: [
      {
        path: '',
        name: 'SettingsPage',
        component: Settings
      }
    ]
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

// 设置路由守卫
setupAuthGuard(router)

export default router
