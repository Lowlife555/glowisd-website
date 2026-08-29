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
      args: 'config.wsgi:application --bind 127.0.0.1:8000 --workers 3 --timeout 120',
      interpreter: 'none',           // gunicorn 是 venv 里的可执行脚本，不要用 node 解释
      exec_mode: 'fork',
      autorestart: true,
      max_memory_restart: '300M',
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
