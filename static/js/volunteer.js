// ===== Socket.IO (safely guarded — won't crash charts/map if CDN fails) =====
if (typeof io !== 'undefined') {
  try {
    var socket = io();

    socket.on('new_request', function(data) {
      // Show a toast-style notification
      var toast = document.createElement('div');
      toast.style.cssText = 'position:fixed;top:24px;right:24px;z-index:9999;background:linear-gradient(135deg,#1e293b,#0f172a);border:1px solid rgba(239,68,68,0.3);border-radius:16px;padding:20px 24px;color:#f1f5f9;font-family:Outfit,sans-serif;box-shadow:0 20px 60px rgba(0,0,0,0.5);animation:slideInRight 0.4s ease;max-width:360px;';
      toast.innerHTML =
        '<div style="display:flex;align-items:center;gap:10px;margin-bottom:8px;">' +
        '<span style="font-size:20px;">🚨</span>' +
        '<strong style="font-size:15px;">New Emergency!</strong>' +
        '</div>' +
        '<div style="font-size:13px;color:#94a3b8;">' +
        data.category + ' — Priority: ' + data.priority + '<br>' +
        '📍 ' + (data.address || 'Nearby') +
        '</div>';
      document.body.appendChild(toast);
      setTimeout(function() {
        toast.style.opacity = '0';
        toast.style.transform = 'translateX(100px)';
        toast.style.transition = 'all 0.4s ease';
        setTimeout(function() { toast.remove(); }, 400);
      }, 5000);
    });

    console.log('[HelpHive] Socket.IO connected');
  } catch (e) {
    console.warn('[HelpHive] Socket.IO init failed (non-blocking):', e);
  }
} else {
  console.warn('[HelpHive] Socket.IO CDN not loaded — real-time notifications disabled');
}
// Add toast animation CSS (always injected — used by Socket.IO toast notifications)
var toastStyle = document.createElement('style');
toastStyle.textContent = '@keyframes slideInRight { from { opacity: 0; transform: translateX(100px); } to { opacity: 1; transform: translateX(0); } }';
document.head.appendChild(toastStyle);

// ===== Animated Number Counters =====
function animateCounters() {
  const counters = document.querySelectorAll('.stat-value[data-count]');
  counters.forEach(counter => {
    const target = parseInt(counter.dataset.count) || 0;
    const duration = 1200;
    const startTime = performance.now();

    function update(currentTime) {
      const elapsed = currentTime - startTime;
      const progress = Math.min(elapsed / duration, 1);
      // Ease out cubic
      const eased = 1 - Math.pow(1 - progress, 3);
      counter.textContent = Math.floor(target * eased);
      if (progress < 1) {
        requestAnimationFrame(update);
      } else {
        counter.textContent = target;
      }
    }
    requestAnimationFrame(update);
  });
}

// ===== Safe Data Parser =====
// Parse embedded JSON safely so a failure doesn't crash the entire page
function safeParseJSON(elementId, fallback) {
  try {
    var el = document.getElementById(elementId);
    if (!el) return fallback;
    return JSON.parse(el.textContent);
  } catch (e) {
    console.warn('[HelpHive] Failed to parse data from #' + elementId + ':', e);
    return fallback;
  }
}

// ===== Live Clock =====
function updateClock() {
  var el = document.querySelector('#liveTime span');
  if (el) {
    var now = new Date();
    var time = now.toLocaleTimeString('en-US', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: true
    });
    var date = now.toLocaleDateString('en-US', {
      weekday: 'short',
      day: 'numeric',
      month: 'short',
      year: 'numeric'
    });
    el.textContent = date + '  •  ' + time;
  }
}

// ===== Chart.js — Status Doughnut =====
function initStatusChart() {
  const ctx = document.getElementById('statusChart');
  if (!ctx) return;

  const pending = statusCounts.Pending || 0;
  const accepted = statusCounts.Accepted || 0;
  const completed = statusCounts.Completed || 0;
  const total = pending + accepted + completed;

  new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: ['Pending', 'Accepted', 'Completed'],
      datasets: [{
        data: total > 0 ? [pending, accepted, completed] : [1],
        backgroundColor: total > 0
          ? ['#f59e0b', '#3b82f6', '#22c55e']
          : ['rgba(255,255,255,0.06)'],
        borderColor: total > 0
          ? ['rgba(245,158,11,0.3)', 'rgba(59,130,246,0.3)', 'rgba(34,197,94,0.3)']
          : ['rgba(255,255,255,0.08)'],
        borderWidth: 2,
        hoverOffset: 8,
        spacing: 4,
        borderRadius: 6
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      cutout: '68%',
      plugins: {
        legend: {
          position: 'bottom',
          labels: {
            color: '#94a3b8',
            font: { family: 'Outfit', size: 13, weight: 500 },
            padding: 20,
            usePointStyle: true,
            pointStyleWidth: 10
          }
        },
        tooltip: {
          backgroundColor: '#1e293b',
          titleColor: '#f1f5f9',
          bodyColor: '#94a3b8',
          borderColor: 'rgba(255,255,255,0.08)',
          borderWidth: 1,
          cornerRadius: 12,
          padding: 14,
          titleFont: { family: 'Outfit', weight: 600 },
          bodyFont: { family: 'Outfit' },
          displayColors: true
        }
      },
      animation: {
        animateRotate: true,
        duration: 1200,
        easing: 'easeOutQuart'
      }
    }
  });
}

// ===== Chart.js — Priority Bar Chart =====
function initPriorityChart() {
  const ctx = document.getElementById('priorityChart');
  if (!ctx) return;

  new Chart(ctx, {
    type: 'bar',
    data: {
      labels: ['High', 'Medium', 'Low'],
      datasets: [{
        label: 'Requests',
        data: [
          priorityCounts.High || 0,
          priorityCounts.Medium || 0,
          priorityCounts.Low || 0
        ],
        backgroundColor: [
          'rgba(239, 68, 68, 0.7)',
          'rgba(245, 158, 11, 0.7)',
          'rgba(34, 197, 94, 0.7)'
        ],
        borderColor: [
          '#ef4444',
          '#f59e0b',
          '#22c55e'
        ],
        borderWidth: 2,
        borderRadius: 10,
        borderSkipped: false,
        barThickness: 48
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        y: {
          beginAtZero: true,
          ticks: {
            color: '#64748b',
            font: { family: 'Outfit', size: 12 },
            stepSize: 1
          },
          grid: {
            color: 'rgba(255,255,255,0.04)',
            drawBorder: false
          },
          border: { display: false }
        },
        x: {
          ticks: {
            color: '#94a3b8',
            font: { family: 'Outfit', size: 13, weight: 500 }
          },
          grid: { display: false },
          border: { display: false }
        }
      },
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: '#1e293b',
          titleColor: '#f1f5f9',
          bodyColor: '#94a3b8',
          borderColor: 'rgba(255,255,255,0.08)',
          borderWidth: 1,
          cornerRadius: 12,
          padding: 14,
          titleFont: { family: 'Outfit', weight: 600 },
          bodyFont: { family: 'Outfit' }
        }
      },
      animation: {
        duration: 1000,
        easing: 'easeOutQuart'
      }
    }
  });
}

// ===== Leaflet Map =====
function initMap() {
  var mapEl = document.getElementById('map');
  if (!mapEl) return;

  // Check if volunteer coordinates exist (not null/undefined)
  // Note: 0 is a valid coordinate, so we can't use !volunteerLat
  var hasCoords = (volunteerLat !== null && volunteerLat !== undefined &&
    volunteerLon !== null && volunteerLon !== undefined &&
    volunteerLat !== '' && volunteerLon !== '');

  // Default to center of India if no coordinates
  var centerLat = hasCoords ? parseFloat(volunteerLat) : 20.5937;
  var centerLon = hasCoords ? parseFloat(volunteerLon) : 78.9629;
  var zoomLevel = hasCoords ? 14 : 5;

  // Guard against NaN
  if (isNaN(centerLat) || isNaN(centerLon)) {
    centerLat = 20.5937;
    centerLon = 78.9629;
    zoomLevel = 5;
    hasCoords = false;
  }

  var map = L.map('map').setView([centerLat, centerLon], zoomLevel);

  L.tileLayer(
    'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png',
    {
      maxZoom: 19,
      attribution: '© OpenStreetMap © CartoDB'
    }
  ).addTo(map);

  // Volunteer marker (only if we have real coordinates)
  if (hasCoords) {
    var volunteerIcon = L.divIcon({
      html: '<div style="background:linear-gradient(135deg,#9333ea,#14b8a6);width:20px;height:20px;border-radius:50%;border:3px solid white;box-shadow:0 2px 10px rgba(147,51,234,0.5);"></div>',
      iconSize: [20, 20],
      className: ''
    });

    L.marker([centerLat, centerLon], { icon: volunteerIcon })
      .addTo(map)
      .bindPopup('<strong style="font-family:Outfit;">📍 You are here</strong>');
  }

  // Request markers
  if (requestData && requestData.length > 0) {
    var bounds = hasCoords ? [L.latLng(centerLat, centerLon)] : [];

    requestData.forEach(function (req) {
      var lat = parseFloat(req.lat);
      var lon = parseFloat(req.lon);
      if (isNaN(lat) || isNaN(lon)) return;

      var requestIcon = L.divIcon({
        html: '<div style="background:#ef4444;width:14px;height:14px;border-radius:50%;border:2px solid rgba(255,255,255,0.8);box-shadow:0 0 12px rgba(239,68,68,0.6);animation:pulse-dot 2s infinite;"></div>',
        iconSize: [14, 14],
        className: ''
      });

      L.marker([lat, lon], { icon: requestIcon })
        .addTo(map)
        .bindPopup(
          '<div style="font-family:Outfit;font-size:13px;">' +
          '<strong>' + req.category + '</strong><br>' +
          req.address + '<br>' +
          '<span style="color:#94a3b8;">' + req.distance + ' KM Away</span>' +
          '</div>'
        );

      bounds.push(L.latLng(lat, lon));
    });

    // Auto-fit map to show all markers
    if (bounds.length > 1) {
      map.fitBounds(L.latLngBounds(bounds), { padding: [40, 40] });
    }
  }

  // Fix map size — call multiple times to cover the CSS animation delay (0.35s delay + 0.6s duration)
  // Using both interval and explicit timeouts for reliability
  setTimeout(function () { map.invalidateSize(); }, 400);
  setTimeout(function () { map.invalidateSize(); }, 800);
  setTimeout(function () { map.invalidateSize(); }, 1100);
  setTimeout(function () { map.invalidateSize(); }, 1600);
  // Also poll every 200ms for the first 2 seconds in case of slow renders
  var refreshCount = 0;
  var refreshInterval = setInterval(function () {
    map.invalidateSize();
    refreshCount++;
    if (refreshCount >= 10) clearInterval(refreshInterval);
  }, 200);
}

// ===== Sidebar Toggle (mobile) =====
function initSidebar() {
  const toggle = document.getElementById('sidebarToggle');
  const sidebar = document.getElementById('sidebar');
  const overlay = document.getElementById('sidebarOverlay');

  if (toggle && sidebar && overlay) {
    toggle.addEventListener('click', () => {
      sidebar.classList.toggle('open');
      overlay.classList.toggle('active');
    });
    overlay.addEventListener('click', () => {
      sidebar.classList.remove('open');
      overlay.classList.remove('active');
    });
  }

  // Smooth scroll for nav items
  document.querySelectorAll('.nav-item[href^="#"]').forEach(link => {
    link.addEventListener('click', (e) => {
      const href = link.getAttribute('href');
      if (href && href !== '#') {
        e.preventDefault();
        const target = document.querySelector(href);
        if (target) {
          target.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
      }
      // Close mobile sidebar
      if (sidebar) sidebar.classList.remove('open');
      if (overlay) overlay.classList.remove('active');
    });
  });
}

// ===== Init Everything =====
window.addEventListener('load', function () {
  // Start clock immediately — this should never fail
  try {
    updateClock();
    setInterval(updateClock, 1000);
  } catch (e) {
    console.error('[HelpHive] Clock init failed:', e);
  }

  // Parse data safely using global variables set by inline script,
  // with safe fallbacks if the inline script failed
  if (typeof volunteerLat === 'undefined') volunteerLat = null;
  if (typeof volunteerLon === 'undefined') volunteerLon = null;
  if (typeof requestData === 'undefined') requestData = [];
  if (typeof statusCounts === 'undefined') statusCounts = { Pending: 0, Accepted: 0, Completed: 0 };
  if (typeof priorityCounts === 'undefined') priorityCounts = { High: 0, Medium: 0, Low: 0 };
  if (typeof categoryCounts === 'undefined') categoryCounts = {};

  // Init counters and sidebar immediately (not affected by opacity/animation)
  try { animateCounters(); } catch (e) { console.error('[HelpHive] Counter animation failed:', e); }
  try { initSidebar(); } catch (e) { console.error('[HelpHive] Sidebar init failed:', e); }

  // Charts need to init AFTER the animation-delay (0.25s) + animation-duration (0.6s) completes
  // We use 1000ms to be safe, so Chart.js gets the correct container dimensions
  setTimeout(function () {
    try { initStatusChart(); } catch (e) { console.error('[HelpHive] Status chart failed:', e); }
    try { initPriorityChart(); } catch (e) { console.error('[HelpHive] Priority chart failed:', e); }
  }, 1000);

  // Map init also deferred — animation-delay is 0.35s + 0.6s duration = ~1s
  setTimeout(function () {
    try { initMap(); } catch (e) { console.error('[HelpHive] Map init failed:', e); }
  }, 1000);
});

// Auto-refresh every 60 seconds (30s was too aggressive)
setInterval(function () {
  location.reload();
}, 60000);