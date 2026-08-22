/**
 * Report Theme JavaScript Toolkit (report-theme.js)
 * Reusable visualization and interaction widgets for Dark & Light developer dashboards
 */

const ReportTheme = {
  /**
   * Theme Initialization & Toggle
   */
  initTheme(storageKey = 'report-theme') {
    const saved = localStorage.getItem(storageKey);
    if (saved === 'light') {
      document.documentElement.classList.remove('dark');
    } else {
      document.documentElement.classList.add('dark');
    }
  },

  toggleTheme(storageKey = 'report-theme', onToggleCallback = null) {
    const html = document.documentElement;
    const isDark = html.classList.contains('dark');
    if (isDark) {
      html.classList.remove('dark');
      localStorage.setItem(storageKey, 'light');
    } else {
      html.classList.add('dark');
      localStorage.setItem(storageKey, 'dark');
    }
    if (onToggleCallback && typeof onToggleCallback === 'function') {
      onToggleCallback(!isDark);
    }
  },

  /**
   * Render a Dual-Zone Velocity Chart with Dynamic Headroom Scaling
   * Guaranteed zero vertical overlap, zero top clipping, zero external dependencies.
   */
  renderVelocityChart(containerId, options = {}) {
    const container = document.getElementById(containerId);
    if (!container) return;

    const {
      trends = []
    } = options;

    if (!trends || trends.length === 0) {
      container.innerHTML = '<p class="text-xs font-mono text-slate-400 p-4">No trend data available.</p>';
      return;
    }

    // Dynamic Headroom Scaling
    const allNets = trends.map(t => t.netOverflow ?? 0);
    const rawMinNet = Math.min(...allNets);
    const rawMaxNet = Math.max(...allNets);
    const minNet = Math.min(0, rawMinNet);
    const maxNet = Math.max(Math.ceil(rawMaxNet * 1.25), 20); // 25% headroom to prevent top clipping

    const allBarVals = trends.flatMap(t => [t.opened || 0, t.merged || 0]);
    const rawMaxBar = Math.max(...allBarVals, 100);
    const maxVal = Math.ceil((rawMaxBar * 1.15) / 50) * 50; // 15% headroom rounded to 50

    const isDark = document.documentElement.classList.contains('dark');
    const gridColor = isDark ? '#1e293b' : '#e2e8f0';
    const baselineColor = isDark ? '#334155' : '#cbd5e1';
    
    const openBarColor = isDark ? '#14b8a6' : '#0d9488';
    const openTextColor = isDark ? '#2dd4bf' : '#0f766e';
    
    const mergeBarColor = isDark ? '#64748b' : '#475569'; // High contrast Slate-600 in Light
    const mergeTextColor = isDark ? '#94a3b8' : '#334155';
    
    const monthTextColor = isDark ? '#cbd5e1' : '#334155';
    const netLineColor = isDark ? '#ef4444' : '#dc2626';
    const netTextColor = isDark ? '#fca5a5' : '#b91c1c';
    const pointBorderColor = isDark ? '#020617' : '#ffffff';

    const num = trends.length;
    const svgPoints = [];
    const startX = 25;
    const endX = 975;
    const usableW = endX - startX;

    // Upper Corridor: strictly safe y range [22, 56]
    trends.forEach((t, i) => {
      const x = startX + ((i + 0.5) / num) * usableW;
      const netNorm = (t.netOverflow - minNet) / Math.max(maxNet - minNet, 1);
      const y = 56 - (netNorm * 34);
      svgPoints.push({ x, y, net: t.netOverflow });
    });

    const polyline = svgPoints.map(p => `${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' ');

    let html = '<div class="relative w-full h-full flex items-center justify-between">';
    html += `
      <svg class="w-full h-full" viewBox="0 0 1000 205" preserveAspectRatio="none">
        <line x1="15" y1="68" x2="985" y2="68" stroke="${gridColor}" stroke-width="1" stroke-dasharray="4,4" />
        <line x1="15" y1="172" x2="985" y2="172" stroke="${baselineColor}" stroke-width="1.2" />

        <polyline points="${polyline}" fill="none" stroke="${netLineColor}" stroke-width="2.5" stroke-dasharray="6,4" />
    `;

    svgPoints.forEach(p => {
      const sign = p.net >= 0 ? '+' : '';
      html += `
        <circle cx="${p.x.toFixed(1)}" cy="${p.y.toFixed(1)}" r="4" fill="${netLineColor}" stroke="${pointBorderColor}" stroke-width="1.5" />
        <text x="${p.x.toFixed(1)}" y="${(p.y - 6).toFixed(1)}" fill="${netTextColor}" font-size="10.5" font-family="JetBrains Mono, monospace" font-weight="bold" text-anchor="middle">
          ${sign}${p.net}
        </text>
      `;
    });

    // Lower Zone: Grouped Dual Bars
    trends.forEach((t, i) => {
      const x = startX + ((i + 0.5) / num) * usableW;
      const barW = 16;
      const gap = 3.5;

      const openH = Math.min((t.opened / maxVal) * 78, 78);
      const mergeH = Math.min((t.merged / maxVal) * 78, 78);

      const openX = x - barW - (gap / 2);
      const mergeX = x + (gap / 2);
      const openY = 172 - openH;
      const mergeY = 172 - mergeH;

      html += `
        <!-- Opened Bar -->
        <text x="${openX + barW/2}" y="${openY - 3}" fill="${openTextColor}" font-size="9" font-family="JetBrains Mono, monospace" font-weight="bold" text-anchor="middle">${t.opened}</text>
        <rect x="${openX}" y="${openY}" width="${barW}" height="${openH}" fill="${openBarColor}" rx="2.5" ry="2.5" />

        <!-- Merged Bar -->
        <text x="${mergeX + barW/2}" y="${mergeY - 3}" fill="${mergeTextColor}" font-size="9" font-family="JetBrains Mono, monospace" font-weight="bold" text-anchor="middle">${t.merged}</text>
        <rect x="${mergeX}" y="${mergeY}" width="${barW}" height="${mergeH}" fill="${mergeBarColor}" rx="2.5" ry="2.5" />

        <!-- Month Label -->
        <text x="${x}" y="193" fill="${monthTextColor}" font-size="10" font-family="JetBrains Mono, monospace" font-weight="600" text-anchor="middle">${t.label || t.month}</text>
      `;
    });

    html += '</svg></div>';
    container.innerHTML = html;
  },

  /**
   * Render a progress distribution widget (Reviewer Load, Complexity Tiers)
   */
  renderProgressList(containerId, items, options = {}) {
    const container = document.getElementById(containerId);
    if (!container) return;

    if (!items || items.length === 0) {
      container.innerHTML = '<p class="text-xs font-mono text-slate-400">No items.</p>';
      return;
    }

    const { maxLimit, barHeight = 'h-1' } = options;
    const maxVal = maxLimit || Math.max(...items.map(i => i.count || i.value || 0), 1);

    let html = '<div class="space-y-1 overflow-y-auto max-h-[130px] pr-1">';
    items.forEach(item => {
      const count = item.count ?? item.value ?? 0;
      const pct = Math.round((count / maxVal) * 100);
      const color = item.color || (item.alert ? 'bg-red-600' : 'bg-teal-500');
      const textColor = item.alert ? 'text-red-600 dark:text-red-400 font-bold' : 'text-slate-700 dark:text-slate-300 font-medium';

      html += `
        <div>
          <div class="flex justify-between text-[11px] font-mono mb-0.5">
            <span class="truncate max-w-[140px] text-slate-800 dark:text-slate-200 font-medium">${item.name || item.label}</span>
            <span class="${textColor}">${count}${item.suffix || ''}</span>
          </div>
          <div class="w-full bg-slate-100 dark:bg-slate-800 rounded-full ${barHeight} overflow-hidden">
            <div class="${color} ${barHeight} rounded-full" style="width: ${pct}%;"></div>
          </div>
        </div>
      `;
    });
    html += '</div>';
    container.innerHTML = html;
  },

  /**
   * Render a vertical histogram widget (PR Age Bins, Latency Bins)
   */
  renderHistogram(containerId, bins) {
    const container = document.getElementById(containerId);
    if (!container) return;

    const maxCount = Math.max(...bins.map(b => b.count || 0), 1);

    let html = '<div class="flex items-end justify-between gap-2 w-full h-[40px] pb-1 border-b border-slate-200 dark:border-slate-800">';
    bins.forEach(item => {
      const heightPct = Math.max(Math.round(((item.count || 0) / maxCount) * 100), 10);
      const bg = item.bg || 'bg-teal-500';
      html += `
        <div class="flex-1 flex flex-col items-center justify-end h-full">
          <span class="text-[10px] font-mono font-bold text-slate-800 dark:text-slate-100 mb-0.5">${item.count || 0}</span>
          <div class="w-full ${bg} rounded-t-sm" style="height: ${heightPct}%;"></div>
        </div>
      `;
    });
    html += '</div>';

    html += '<div class="flex justify-between gap-2 w-full mt-0.5 text-center">';
    bins.forEach(item => {
      html += `<div class="flex-1 text-[10px] font-mono text-slate-500 dark:text-slate-400 font-medium">${item.label}</div>`;
    });
    html += '</div>';

    container.innerHTML = html;
  }
};

window.ReportTheme = ReportTheme;
