import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { Brand } from './app/Brand'

createRoot(document.getElementById('root')!).render(<StrictMode><Brand /></StrictMode>)
