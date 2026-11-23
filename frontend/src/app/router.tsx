import { lazy } from 'react'
import { createBrowserRouter } from 'react-router'
import { RouterProvider } from 'react-router/dom'
import { GuestLayout, NotFound, RouteError, WorkspaceLayout } from './Layouts'

const Login = lazy(() => import('@/features/auth/AuthPages').then(module => ({ default: module.LoginPage })))
const Register = lazy(() => import('@/features/auth/AuthPages').then(module => ({ default: module.RegisterPage })))
const Forgot = lazy(() => import('@/features/auth/AuthPages').then(module => ({ default: module.ForgotPage })))
const Reset = lazy(() => import('@/features/auth/AuthPages').then(module => ({ default: module.ResetPage })))
const Verify = lazy(() => import('@/features/auth/AuthPages').then(module => ({ default: module.VerifyPage })))
const Dashboard = lazy(() => import('@/features/dashboard/DashboardPage'))
const Transactions = lazy(() => import('@/features/transactions/TransactionsPage'))
const Categories = lazy(() => import('@/features/categories/CategoriesPage'))
const Profile = lazy(() => import('@/features/profile/ProfilePage'))

const router = createBrowserRouter([
  {
    element: <GuestLayout />,
    errorElement: <RouteError />,
    children: [
      { path: '/login', element: <Login /> },
      { path: '/register', element: <Register /> },
      { path: '/forgot-password', element: <Forgot /> },
      { path: '/reset-password', element: <Reset /> },
      { path: '/verify-email', element: <Verify /> },
      { path: '*', element: <NotFound /> },
    ],
  },
  {
    element: <WorkspaceLayout />,
    errorElement: <RouteError />,
    children: [
      { path: '/', element: <Dashboard /> },
      { path: '/transactions', element: <Transactions /> },
      { path: '/categories', element: <Categories /> },
      { path: '/profile', element: <Profile /> },
    ],
  },
])

export function AppRouter() {
  return <RouterProvider router={router} />
}
