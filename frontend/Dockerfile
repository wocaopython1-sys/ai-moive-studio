# ============================================
# Stage 1: Builder - 构建阶段
# ============================================
FROM node:18-alpine AS builder

# 设置工作目录
WORKDIR /app

# 安装构建依赖 (用于编译原生模块)
RUN apk add --no-cache python3 make g++

# 复制package文件
COPY package*.json ./

# 安装所有依赖 (包括devDependencies,构建时需要)
RUN npm ci

# 复制源代码
COPY . .

# 构建生产版本
RUN npm run build

# ============================================
# Stage 2: Nginx - 运行阶段
# ============================================
FROM nginx:alpine

# 复制自定义nginx配置
COPY nginx.conf /etc/nginx/nginx.conf

# 从builder阶段复制构建产物
COPY --from=builder /app/dist /usr/share/nginx/html

# 创建nginx用户目录
RUN chown -R nginx:nginx /usr/share/nginx/html && \
    chmod -R 755 /usr/share/nginx/html

# 健康检查
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD wget --quiet --tries=1 --spider http://127.0.0.1:80/ || exit 1

# 暴露端口
EXPOSE 80

# 启动nginx
CMD ["nginx", "-g", "daemon off;"]
