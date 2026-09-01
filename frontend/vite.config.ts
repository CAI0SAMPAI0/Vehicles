import { defineConfig } from 'vite';
import { resolve } from 'path';

export default defineConfig({
  root: '.',
  envPrefix: ['VITE_', 'NEXT_', 'NEXT_PUBLIC_'],
  define: {
    'process.env.NEXT_API_BASE_URL': JSON.stringify(process.env.NEXT_API_BASE_URL || process.env.NEXT_PUBLIC_API_BASE_URL || process.env.VITE_API_URL || ''),
    'process.env.NEXT_PUBLIC_API_BASE_URL': JSON.stringify(process.env.NEXT_PUBLIC_API_BASE_URL || process.env.NEXT_API_BASE_URL || process.env.VITE_API_URL || ''),
  },
  build: {
    outDir: 'dist',
    rollupOptions: {
      input: {
        main: resolve(__dirname, 'index.html'),
        cars: resolve(__dirname, 'cars/index.html'),
        login: resolve(__dirname, 'login/index.html'),
        register: resolve(__dirname, 'register/index.html'),
        new_car: resolve(__dirname, 'new_car/index.html'),
        car_detail: resolve(__dirname, 'car_detail/index.html'),
      },
    },
  },
});
