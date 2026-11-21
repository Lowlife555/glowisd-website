// Glowisd — pm2 进程配置（用 gunicorn 跑 Django WSGI）
// 首次启动:  pm2 start deploy/ecosystem.config.cjs
// 日常部署:  pm2 restart glowisd --update-env
//
// 安全：SECRET_KEY 不再硬编码在此文件，改从服务器 /var/www/glowisd/.env 读取。
// .env 文件不进 git（.gitignore 已忽略），需在服务器手动创建一次：
//   echo "DJANGO_SECRET_KEY=<随机密钥>" > /var/www/glowisd/.env
//   echo "DJANGO_DEBUG=False" >> /var/www/glowisd/.env
//   chmod 600 /var/www/glowisd/.env
const fs = require('fs');

function loadServerEnv() {
  try {
    const content = fs.readFileSync('/var/www/glowisd/.env', 'utf8');
    const env = {};
    content.split(/\r?\n/).forEach((line) => {
      const m = line.match(/^([A-Z_][A-Z0-9_]*)=(.*)$/);
      if (m) env[m[1]] = m[2].trim();
    });
    return env;
  } catch (e) {
    return {};
  }
}

const serverEnv = loadServerEnv();

module.exports = {
  apps: [
    {
      name: 'glowisd',
      cwd: '/var/www/glowisd',
      script: 'venv/bin/gunicorn',
      // 并发：2 核 2G 机器上，1 个同步 worker 会把所有请求排成一条队（第 50 个访客要等前面 49 个走完）。
      // 3 worker × 3 gthread = 9 个并发槽位；本项目每次请求只有几十毫秒 CPU，够扛 50 人同时浏览。
      // max-requests：worker 处理一定请求数后自动重启，避免长期运行的内存缓慢上涨。
      args: 'config.wsgi:application --bind 127.0.0.1:8000 ' +
        '--workers 3 --threads 3 --worker-class gthread --timeout 60 --graceful-timeout 30 ' +
        '--keep-alive 5 --max-requests 1000 --max-requests-jitter 120',
      interpreter: 'none',           // gunicorn 是 venv 里的可执行脚本，不要用 node 解释
      exec_mode: 'fork',
      autorestart: true,
      max_memory_restart: '600M',   // 3 worker 合计约 300-400MB，留出余量避免误判重启
      env: {
        DJANGO_SETTINGS_MODULE: 'config.settings',
        // 让 gunicorn 脚本找到 venv 里的 python（shebang 已指向 venv，此行为保险）
        PATH: '/var/www/glowisd/venv/bin:' + process.env.PATH,
        DJANGO_SECRET_KEY: serverEnv.DJANGO_SECRET_KEY || '',
        DJANGO_DEBUG: serverEnv.DJANGO_DEBUG || 'False',
      },
    },
  ],
};
