window.AStockApp = (() => {
  const API_BASE = '/api/market';
  const NAV_ITEMS = [
    { key: 'home', href: '/', label: '首页' },
    { key: 'quote', href: '/quote', label: '行情中心' },
    { key: 'chart', href: '/chart', label: 'K 线图' },
    { key: 'screener', href: '/screener', label: '选股器' },
    { key: 'strategy', href: '/strategy', label: '战法选股' },
    { key: 'data', href: '/data', label: '数据中心' },
    { key: 'ops', href: '/ops', label: '系统维护' },
    { key: 'docs', href: '/docs', label: 'API 文档' },
  ];

  async function resolveStockCode(inputValue) {
    const q = String(inputValue || '').trim();
    if (!q) return '';
    if (/^\d{6}$/.test(q)) return q;
    const res = await fetch(`${API_BASE}/resolve_stock?q=${encodeURIComponent(q)}`);
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || '股票解析失败');
    return data.code;
  }

  function openChartByCode(code) {
    const c = String(code || '').trim();
    if (!c) return;
    window.location.assign(`/chart?code=${encodeURIComponent(c)}`);
  }

  function renderNavbar(activeKey) {
    const menu = document.querySelector('.navbar-menu');
    if (!menu) return;
    menu.innerHTML = NAV_ITEMS.map((item) => {
      const active = item.key === activeKey ? ' class="active"' : '';
      return `<a href="${item.href}"${active}>${item.label}</a>`;
    }).join('');
  }

  return {
    API_BASE,
    NAV_ITEMS,
    openChartByCode,
    renderNavbar,
    resolveStockCode,
  };
})();
