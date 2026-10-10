import { defineConfig } from '@playwright/test';
export default defineConfig({testDir:'./e2e',timeout:60000,use:{baseURL:'http://127.0.0.1:5173',viewport:{width:1440,height:900},launchOptions:{executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',args:['--use-angle=swiftshader','--enable-unsafe-swiftshader']}},reporter:'list'});
