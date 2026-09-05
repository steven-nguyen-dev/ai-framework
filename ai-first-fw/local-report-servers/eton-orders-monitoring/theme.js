/**
 * Unified Local Theme JavaScript Toolkit (theme.js)
 * Reusable visualization and interaction widgets for Local Test & Report Servers.
 */

const LocalTheme = {
  /**
   * Render a Dual-Zone Velocity Chart (Upper Trend Line + Lower Grouped Bars)
   * Guaranteed zero vertical overlap, zero external dependencies.
   */
  renderVelocityChart(containerId, options = {}) {
    const container = document.getElementById(containerId);
    if (!container) return;

    const {
      trends = [],
      maxBarVal = 500,
      minNet = 10,
      maxNet = 70
    } = options;

    if (!trends || trends.length === 0) {
      container.innerHTML = '<p class="text-xs font-mono text-slate-400 p-4">No trend data available.</p>';
      return;
    }

    const gridColor = '#1e293b';
    const baselineColor = '#334155';
    const openBarColor = '#10b981';
    const openTextColor = '#34d399';
    const mergeBarColor = '#64748b';
    const mergeTextColor = '#94a3b8';
    const monthTextColor = '#cbd5e1';
    const netLineColor = '#ef4444';
    const netTextColor = '#fca5a5';
    const pointBorderColor = '#020617';

    const num = trends.length;
    const svgPoints = [];
    const startX = 25;
    const endX = 975;
    const usableW = endX - startX;

    trends.forEach((t, i) => {
      const x = startX + ((i + 0.5) / num) * usableW;
      const netNorm = (t.netOverflow - minNet) / Math.max(maxNet - minNet, 1);
      const y = 58 - (netNorm * 42); // Upper corridor
      svgPoints.push({ x, y, net: t.netOverflow });
    });

    const polyline = svgPoints.map(p => `${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' ');

    let html = '<div class="relative w-full h-full flex items-center justify-between">';
    html += `
      <svg class="w-full h-full" viewBox="0 0 1000 205" preserveAspectRatio="none">
        <line x1="15" y1="74" x2="985" y2="74" stroke="${gridColor}" stroke-width="1" stroke-dasharray="4,4" />
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

      const openH = Math.min((t.opened / maxBarVal) * 84, 84);
      const mergeH = Math.min((t.merged / maxBarVal) * 84, 84);

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
   * Render a progress distribution widget (Assignee Load, PR Age Tiers, Diff Tiers)
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

    let html = '<div class="space-y-1 overflow-y-auto max-h-[112px] pr-1">';
    items.forEach(item => {
      const count = item.count ?? item.value ?? 0;
      const pct = Math.round((count / maxVal) * 100);
      const color = item.color || (item.alert ? 'bg-red-600' : 'bg-emerald-500');
      const textColor = item.alert ? 'text-red-400 font-bold' : 'text-slate-300 font-medium';

      html += `
        <div>
          <div class="flex justify-between text-[11px] font-mono mb-0.5">
            <span class="truncate max-w-[140px] text-slate-200 font-medium">${item.name || item.label}</span>
            <span class="${textColor}">${count}${item.suffix || ''}</span>
          </div>
          <div class="w-full bg-slate-800 rounded-full ${barHeight} overflow-hidden">
            <div class="${color} ${barHeight} rounded-full" style="width: ${pct}%;"></div>
          </div>
        </div>
      `;
    });
    html += '</div>';
    container.innerHTML = html;
  }
};

window.LocalTheme = LocalTheme;
