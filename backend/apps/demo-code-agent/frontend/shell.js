(function () {
  'use strict';

  window.MAWP_NAV = window.MAWP_NAV || [
    {
      path: 'index.html',
      page: 'tickets',
      title: '工单台',
      desc: '创建 · 流转 · 删除',
      tag: 'App'
    },
    {
      path: 'status.html',
      page: 'status',
      title: '交付状态',
      desc: '验收 · 人工确认',
      tag: 'Delivery'
    }
  ];

  function escapeHtml(str) {
    return String(str).replace(/[&<>"']/g, function (c) {
      return {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#39;'
      }[c];
    });
  }

  function currentPage() {
    return (document.body && document.body.getAttribute('data-page')) || '';
  }

  function brandName() {
    return (document.body && document.body.getAttribute('data-brand')) || '内部工单台';
  }

  function render() {
    var page = currentPage();
    var brand = brandName();

    var brandNodes = document.querySelectorAll('[data-shell-brand]');
    for (var i = 0; i < brandNodes.length; i++) {
      brandNodes[i].textContent = brand;
    }

    var nav = document.getElementById('lz-nav');
    if (nav) {
      var html = '';
      for (var j = 0; j < window.MAWP_NAV.length; j++) {
        var item = window.MAWP_NAV[j];
        var active = item.page === page ? ' active' : '';
        html += '<a class="lz-nav-link' + active + '" href="' + escapeHtml(item.path) + '" data-page="' + escapeHtml(item.page) + '">'
          + '<span class="lz-nav-link-title">' + escapeHtml(item.title) + '</span>'
          + '<span class="lz-nav-link-desc">' + escapeHtml(item.desc) + '</span>'
          + '</a>';
      }
      nav.innerHTML = html;
    }

    var topTitle = document.getElementById('lz-topbar-title');
    if (topTitle) {
      var current = null;
      for (var k = 0; k < window.MAWP_NAV.length; k++) {
        if (window.MAWP_NAV[k].page === page) {
          current = window.MAWP_NAV[k];
          break;
        }
      }
      topTitle.textContent = current ? current.title : brand;
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', render);
  } else {
    render();
  }
})();
