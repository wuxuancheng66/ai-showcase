(() => {
  const nav = document.querySelector('[data-nav]');
  const toggle = document.querySelector('[data-nav-toggle]');
  const currentPath = window.location.pathname;

  document.querySelectorAll('.nav__link').forEach((link) => {
    const href = new URL(link.href, window.location.origin).pathname;
    const active = href === '/' ? currentPath === '/' : currentPath.startsWith(href);
    if (active) link.setAttribute('aria-current', 'page');
  });

  if (nav && toggle) {
    const close = () => {
      nav.dataset.open = 'false';
      toggle.setAttribute('aria-expanded', 'false');
      const label = toggle.querySelector('.sr-only');
      if (label) label.textContent = '打开导航';
    };
    toggle.addEventListener('click', () => {
      const open = nav.dataset.open !== 'true';
      nav.dataset.open = String(open);
      toggle.setAttribute('aria-expanded', String(open));
      const label = toggle.querySelector('.sr-only');
      if (label) label.textContent = open ? '关闭导航' : '打开导航';
    });
    nav.addEventListener('click', (event) => {
      if (event.target.closest('a')) close();
    });
    window.addEventListener('resize', () => {
      if (window.matchMedia('(min-width: 76rem)').matches) close();
    });
    document.addEventListener('keydown', (event) => {
      if (event.key === 'Escape') close();
    });
  }

  document.querySelectorAll('[data-open-agent]').forEach((button) => {
    button.addEventListener('click', async () => {
      const original = button.textContent;
      button.disabled = true;
      button.textContent = '正在打开…';
      const controller = new AbortController();
      const timeoutId = window.setTimeout(() => controller.abort(), 8000);
      try {
        const response = await fetch('/api/v1/agents/' + encodeURIComponent(button.dataset.openAgent) + '/open', {
          method: 'POST',
          signal: controller.signal,
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || '打开失败');
        if (data.mode === 'url') {
          window.open(data.url, '_blank', 'noopener');
          button.textContent = '已打开';
        } else if (data.mode === 'command') {
          let copied = false;
          if (navigator.clipboard?.writeText) {
            copied = await Promise.race([
              navigator.clipboard.writeText(data.command).then(() => true).catch(() => false),
              new Promise((resolve) => window.setTimeout(() => resolve(false), 1500)),
            ]);
          }
          button.disabled = false;
          button.title = data.command;
          if (copied) {
            button.textContent = '命令已复制';
          } else {
            window.prompt('浏览器未允许自动复制，请手动复制启动命令：', data.command);
            button.textContent = '命令已显示';
          }
        } else if (data.mode === 'queued') {
          button.textContent = '启动指令已发送';
        } else {
          window.location.href = data.detail_url || '/agents';
        }
      } catch (error) {
        button.textContent = original;
        button.disabled = false;
        button.title = error.message;
        window.alert(error.name === 'AbortError' ? '请求超时，请稍后重试。' : error.message);
      } finally {
        window.clearTimeout(timeoutId);
        button.disabled = false;
      }
    });
  });

  document.querySelectorAll('form[data-confirm]').forEach((form) => {
    form.addEventListener('submit', (event) => {
      if (!window.confirm(form.dataset.confirm)) {
        event.preventDefault();
        event.stopImmediatePropagation();
      }
    });
  });

  document.querySelectorAll('form[data-busy]').forEach((form) => {
    form.addEventListener('submit', () => {
      const button = form.querySelector('button[type="submit"], button:not([type])');
      if (!button) return;
      button.disabled = true;
      button.dataset.state = 'loading';
      button.textContent = button.dataset.busyLabel || '正在处理…';
    });
  });
})();
