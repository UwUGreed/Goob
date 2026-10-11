import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';
import { dispatchApi } from './server/local';
export default defineConfig(({mode})=>({plugins:[react(),tailwindcss(),dispatchApi(loadEnv(mode,process.cwd(),''))],server:{proxy:{'^/api/(?!config(?:$|\\?)|dispatch(?:$|\\?)|routes(?:$|\\?)|scribe-token(?:$|\\?))': 'http://127.0.0.1:8081'}}}));
