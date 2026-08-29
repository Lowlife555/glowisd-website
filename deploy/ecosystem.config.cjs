// Glowisd — pm2 进程配置（用 gunicorn 跑 Django WSGI）
// 首次启动:  pm2 start deploy/ecosystem.config.cjs
// 日常部署:  pm2 restart glowisd --update-env
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
        DJANGO_SECRET_KEY: 'rm7s^$=p+gcvz-=i9s*uzj%xpw5sqy*h(+1(^_v3ghwjrn9+8s',
        DJANGO_DEBUG: 'False',
      },
    },
  ],
};
