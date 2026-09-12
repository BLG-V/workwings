(function () {
  'use strict';

  var STORAGE_KEY = 'it-ticket-desk.tickets.v1';

  var STATUS = {
    pending: { label: '待处理', className: 'pending' },
    in_progress: { label: '处理中', className: 'processing' },
    done: { label: '已完成', className: 'done' }
  };

  var STATUS_ORDER = ['pending', 'in_progress', 'done'];
  var currentFilter = 'all';

  var tickets = [];
  var storageAvailable = true;

  var form = document.getElementById('ticket-form');
  var titleInput = document.getElementById('ticket-title');
  var noteInput = document.getElementById('ticket-note');
  var list = document.getElementById('ticket-list');
  var emptyState = document.getElementById('empty-state');
  var heroPending = document.getElementById('hero-pending');
  var panelCount = document.getElementById('ticket-count');
  var filterBar = document.getElementById('filter-bar');

  function statusClass(status) {
    var item = STATUS[status];
    return item ? item.className : 'pending';
  }

  function loadTickets() {
    try {
      var raw = localStorage.getItem(STORAGE_KEY);
      if (!raw) return [];
      var parsed = JSON.parse(raw);
      if (!Array.isArray(parsed)) return [];
      return parsed
        .filter(function (item) {
          return item && typeof item.id === 'string' && typeof item.title === 'string';
        })
        .map(function (item) {
          var title = String(item.title).trim().slice(0, 200);
          if (!title) return null;
          var status = STATUS_ORDER.indexOf(item.status) >= 0 ? item.status : 'pending';
          return {
            id: item.id,
            title: title,
            note: String(item.note || '').trim().slice(0, 500),
            status: status,
            createdAt: item.createdAt || new Date().toISOString()
          };
        })
        .filter(Boolean);
    } catch (err) {
      storageAvailable = false;
      console.warn('[内部工单台] localStorage 不可用，数据仅保留在本次页面会话中。', err);
      return [];
    }
  }

  function persist() {
    if (!storageAvailable) return;
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(tickets));
    } catch (err) {
      storageAvailable = false;
      console.warn('[内部工单台] 保存到 localStorage 失败，数据仅保留在本次页面会话中。', err);
    }
  }

  function newId() {
    return 'tk-' + Date.now().toString(36) + '-' + Math.random().toString(36).slice(2, 8);
  }

  function addTicket(title, note) {
    var trimmed = String(title || '').trim();
    if (!trimmed) return false;
    var ticket = {
      id: newId(),
      title: trimmed.slice(0, 200),
      note: String(note || '').trim().slice(0, 500),
      status: 'pending',
      createdAt: new Date().toISOString()
    };
    tickets.unshift(ticket);
    persist();
    currentFilter = 'all';
    render();
    return true;
  }

  function updateStatus(id, status) {
    if (STATUS_ORDER.indexOf(status) < 0) return;
    for (var i = 0; i < tickets.length; i++) {
      if (tickets[i].id === id) {
        tickets[i].status = status;
        persist();
        render();
        return;
      }
    }
  }

  function deleteTicket(id) {
    tickets = tickets.filter(function (ticket) {
      return ticket.id !== id;
    });
    persist();
    render();
  }

  function counts() {
    var result = { all: tickets.length, pending: 0, in_progress: 0, done: 0 };
    tickets.forEach(function (ticket) {
      if (result[ticket.status] !== undefined) {
        result[ticket.status] += 1;
      }
    });
    return result;
  }

  function visibleTickets() {
    if (currentFilter === 'all') return tickets;
    return tickets.filter(function (ticket) {
      return ticket.status === currentFilter;
    });
  }

  function formatTime(iso) {
    try {
      var date = new Date(iso);
      if (isNaN(date.getTime())) return String(iso);
      return date.toLocaleString();
    } catch (err) {
      return String(iso);
    }
  }

  function clearList() {
    if (!list) return;
    while (list.firstChild) {
      list.removeChild(list.firstChild);
    }
  }

  function buildStatusSelect(ticket) {
    var select = document.createElement('select');
    select.className = 'ticket-status';
    select.setAttribute('aria-label', '切换工单状态');
    STATUS_ORDER.forEach(function (key) {
      var option = document.createElement('option');
      option.value = key;
      option.textContent = STATUS[key].label;
      if (key === ticket.status) option.selected = true;
      select.appendChild(option);
    });
    select.addEventListener('change', function () {
      updateStatus(ticket.id, select.value);
    });
    return select;
  }

  function renderFilters() {
    if (!filterBar) return;
    var c = counts();
    var buttons = filterBar.querySelectorAll('[data-filter]');
    for (var i = 0; i < buttons.length; i++) {
      var btn = buttons[i];
      var key = btn.getAttribute('data-filter');
      btn.classList.toggle('active', key === currentFilter);
      var span = btn.querySelector('[data-filter-count]');
      if (span) span.textContent = String(c[key] || 0);
    }
  }

  function render() {
    if (!list) return;
    clearList();

    var c = counts();
    if (heroPending) heroPending.textContent = String(c.pending);
    if (panelCount) panelCount.textContent = '共 ' + c.all + ' 条 · 待处理 ' + c.pending + ' 条';
    renderFilters();

    var visible = visibleTickets();
    if (emptyState) {
      emptyState.textContent = c.all === 0 ? '还没有工单' : '没有符合条件的工单';
      emptyState.classList.toggle('hidden', visible.length > 0);
    }

    visible.forEach(function (ticket) {
      var css = statusClass(ticket.status);
      var li = document.createElement('li');
      li.className = 'ticket-item status-' + css;

      var main = document.createElement('div');
      main.className = 'ticket-main';

      var titleRow = document.createElement('div');
      titleRow.className = 'ticket-title-row';

      var title = document.createElement('h3');
      title.className = 'ticket-title';
      title.textContent = ticket.title;

      var badge = document.createElement('span');
      badge.className = 'ticket-badge badge-' + css;
      badge.textContent = STATUS[ticket.status].label;

      titleRow.appendChild(title);
      titleRow.appendChild(badge);
      main.appendChild(titleRow);

      if (ticket.note) {
        var note = document.createElement('p');
        note.className = 'ticket-note';
        note.textContent = ticket.note;
        main.appendChild(note);
      }

      var meta = document.createElement('p');
      meta.className = 'ticket-meta';
      meta.textContent = '创建于 ' + formatTime(ticket.createdAt);
      main.appendChild(meta);

      var actions = document.createElement('div');
      actions.className = 'ticket-actions';
      actions.appendChild(buildStatusSelect(ticket));

      var deleteBtn = document.createElement('button');
      deleteBtn.type = 'button';
      deleteBtn.className = 'delete-btn';
      deleteBtn.textContent = '删除';
      deleteBtn.setAttribute('aria-label', '删除工单：' + ticket.title);
      deleteBtn.addEventListener('click', function () {
        deleteTicket(ticket.id);
      });
      actions.appendChild(deleteBtn);

      li.appendChild(main);
      li.appendChild(actions);
      list.appendChild(li);
    });
  }

  function findFilterButton(target) {
    while (target && target !== filterBar) {
      if (target.getAttribute && target.getAttribute('data-filter')) return target;
      target = target.parentNode;
    }
    return null;
  }

  if (form) {
    form.addEventListener('submit', function (event) {
      event.preventDefault();
      var ok = addTicket(
        titleInput ? titleInput.value : '',
        noteInput ? noteInput.value : ''
      );
      if (ok) {
        if (titleInput) titleInput.value = '';
        if (noteInput) noteInput.value = '';
      }
      if (titleInput) titleInput.focus();
    });
  }

  if (filterBar) {
    filterBar.addEventListener('click', function (event) {
      var btn = findFilterButton(event.target);
      if (!btn) return;
      currentFilter = btn.getAttribute('data-filter') || 'all';
      render();
    });
  }

  tickets = loadTickets();
  render();
})();
