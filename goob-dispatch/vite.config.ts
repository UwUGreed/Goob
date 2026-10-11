import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';
export default defineConfig(({mode})=>({plugins:[react(),tailwindcss()],server:{proxy:{'/api':loadEnv(mode,process.cwd(),'').GOOB_BACKEND_URL||'http://127.0.0.1:8090'}}}));
