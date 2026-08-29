
  let currentWo = null;

  function filterTable() {
    const input = document.getElementById("searchInput");
    const filter = input.value.toLowerCase();
    const table = document.getElementById("woTable");
    const tr = table.getElementsByTagName("tr");
    let count = 0;

    for (let i = 1; i < tr.length; i++) {
      const tdTitle = tr[i].getElementsByTagName("td")[0];
      if (tdTitle) {
        const txtValue = tdTitle.textContent || tdTitle.innerText;
        if (txtValue.toLowerCase().indexOf(filter) > -1) {
          tr[i].style.display = "";
          count++;
        } else {
          tr[i].style.display = "none";
        }
      }
    }
    document.getElementById("wo-count").innerText = `${count} Work Orders`;
  }

  function openWoModal(id='', title='', desc='', priority='MEDIUM', status='CREATED', asset_id='', assignee_id='', deadline='') {
      document.getElementById('wo-modal').classList.remove('hidden');
      document.getElementById('wo-id').value = id;
      document.getElementById('wo-title').value = title;
      document.getElementById('wo-desc').value = desc !== 'None' ? desc : '';
      document.getElementById('wo-priority').value = priority;
      document.getElementById('wo-status').value = status;
      document.getElementById('wo-asset').value = asset_id;
      document.getElementById('wo-assignee').value = assignee_id;
      document.getElementById('wo-deadline').value = deadline !== 'None' ? deadline : '';
      
      document.getElementById('wo-modal-title').innerText = id ? 'Sửa Work Order' : 'Tạo Work Order';
      document.getElementById('wo-msg').classList.add('hidden');
  }

  function closeWoModal() {
      document.getElementById('wo-modal').classList.add('hidden');
      document.getElementById('wo-form').reset();
  }

  function saveWo() {
      const id = document.getElementById('wo-id').value;
      const data = {
          id: id,
          title: document.getElementById('wo-title').value,
          description: document.getElementById('wo-desc').value,
          priority: document.getElementById('wo-priority').value,
          status: document.getElementById('wo-status').value,
          asset_id: document.getElementById('wo-asset').value,
          assigned_to_id: document.getElementById('wo-assignee').value,
          deadline: document.getElementById('wo-deadline').value
      };
      
      const method = id ? 'PUT' : 'POST';
      const btn = document.getElementById('btn-save-wo');
      const msg = document.getElementById('wo-msg');
      btn.disabled = true;
      
      fetch('{% url "portal_work_orders" %}', {
          method: method,
          headers: {
              'Content-Type': 'application/json',
              'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
          },
          body: JSON.stringify(data)
      })
      .then(res => res.json())
      .then(resData => {
          if(resData.success) {
              window.location.reload();
          } else {
              msg.className = 'mb-4 p-3 rounded-lg text-sm bg-red-50 text-red-600 border border-red-200 font-medium';
              msg.innerText = resData.error || 'An error occurred';
              msg.classList.remove('hidden');
          }
      })
      .finally(() => {
          btn.disabled = false;
      });
  }

  function deleteWo(id, followUpCount) {
      if (followUpCount > 0) {
        alert("Work Order này có Follow-up. Bạn phải xóa các Follow-up trước khi xóa Work Order gốc.");
        return;
      }
      if(confirm('Bạn có chắc chắn muốn xóa Work Order này không?')) {
          fetch('{% url "portal_work_orders" %}', {
              method: 'DELETE',
              headers: {
                  'Content-Type': 'application/json',
                  'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
              },
              body: JSON.stringify({id: id})
          })
          .then(res => res.json())
          .then(data => {
              if(data.success) {
                  window.location.reload();
              } else {
                  alert(data.error);
              }
          });
      }
  }

  function updateStatus(id, status) {
    fetch('{% url "portal_work_orders" %}', {
        method: 'PUT',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
        },
        body: JSON.stringify({id: id, status: status})
    })
    .then(res => res.json())
    .then(data => {
        if(data.success) {
            window.location.reload();
        } else {
            alert(data.error);
        }
    });
  }

  function openAssignModal(id, currentAssignee) {
      document.getElementById('assign-wo-id').value = id;
      document.getElementById('assign-user').value = currentAssignee;
      document.getElementById('assign-modal').classList.remove('hidden');
  }

  function closeAssignModal() {
      document.getElementById('assign-modal').classList.add('hidden');
  }

  function submitAssign() {
      const id = document.getElementById('assign-wo-id').value;
      const assigned_to_id = document.getElementById('assign-user').value;
      
      // Update assigned_to_id by fetching the existing data (for parity, partial put)
      fetch('{% url "portal_work_orders" %}', {
          method: 'PUT',
          headers: {
              'Content-Type': 'application/json',
              'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
          },
          body: JSON.stringify({id: id, assigned_to_id: assigned_to_id})
      })
      .then(res => res.json())
      .then(data => {
          if(data.success) {
              window.location.reload();
          } else {
              alert(data.error);
          }
      });
  }

  // Checklists logic
  function openWoDetailModal(id, title, desc, priority, status, asset_id, asset_name, assignee_id, assignee_name, deadline, checklists) {
      currentWo = { id, title, desc, priority, status, asset_id, assignee_id, deadline };
      document.getElementById('wo-detail-modal').classList.remove('hidden');
      
      const woTag = `#${id.substring(0,8)}`;
      document.getElementById('detail-title').innerHTML = `<i class="ph-fill ph-clipboard-text text-primary"></i> Work Order ${woTag}`;
      document.getElementById('detail-title-large').innerText = title;
      document.getElementById('detail-desc').innerText = desc !== 'None' && desc !== '' ? desc : 'Không có mô tả.';
      document.getElementById('detail-status').innerText = status;
      
      const pColor = priority === 'CRITICAL' ? 'bg-fuchsia-50 text-fuchsia-600 border-fuchsia-200' :
                     priority === 'HIGH' ? 'bg-red-50 text-red-600 border-red-200' :
                     priority === 'MEDIUM' ? 'bg-orange-50 text-orange-600 border-orange-200' :
                     'bg-green-50 text-green-600 border-green-200';
      document.getElementById('detail-priority').className = `px-3 py-1 border rounded-full text-xs font-bold uppercase tracking-wider ${pColor}`;
      document.getElementById('detail-priority').innerText = priority;
      
      document.getElementById('detail-asset-name').innerText = asset_id ? asset_name : 'Không có';
      document.getElementById('detail-assignee-name').innerText = assignee_id ? assignee_name : 'Chưa phân công';
      document.getElementById('detail-deadline').innerText = deadline && deadline !== 'None' ? deadline : 'Chưa thiết lập';
      
      renderChecklists(id, checklists);
  }

  function closeWoDetailModal() {
      document.getElementById('wo-detail-modal').classList.add('hidden');
      currentWo = null;
  }
  
  function editCurrentWo() {
      closeWoDetailModal();
      openWoModal(currentWo.id, currentWo.title, currentWo.desc, currentWo.priority, currentWo.status, currentWo.asset_id, currentWo.assignee_id, currentWo.deadline);
  }

  function renderChecklists(wo_id, checklists) {
      const container = document.getElementById('detail-checklists');
      container.innerHTML = '';
      if(!checklists || checklists.length === 0) {
          container.innerHTML = '<p class="text-sm text-neutral-500 p-4 text-center font-medium">Chưa có checklist nào.</p>';
          return;
      }
      checklists.forEach(item => {
          const isChecked = item.is_completed ? 'checked' : '';
          const textClass = item.is_completed ? 'line-through text-neutral-400' : 'text-neutral-700 font-medium';
          container.innerHTML += `
            <label class="flex items-center gap-3 p-3 rounded-xl cursor-pointer hover:bg-neutral-50 transition-colors group">
              <input type="checkbox" class="w-5 h-5 text-primary rounded border-neutral-300 focus:ring-primary transition-all" ${isChecked} onchange="toggleChecklist('${item.id}', this.checked)">
              <span class="text-sm ${textClass} group-hover:text-primary transition-colors flex-1">${item.item_name}</span>
              <button onclick="deleteChecklist('${item.id}', event)" class="w-8 h-8 flex items-center justify-center text-neutral-400 hover:text-danger rounded-lg hover:bg-red-50 opacity-0 group-hover:opacity-100 transition-all">
                <i class="ph-bold ph-trash"></i>
              </button>
            </label>
          `;
      });
  }

  function toggleChecklist(itemId, isCompleted) {
      fetch('{% url "portal_work_orders" %}', {
          method: 'POST',
          headers: {
              'Content-Type': 'application/json',
              'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
          },
          body: JSON.stringify({action: 'toggle_checklist', item_id: itemId, is_completed: isCompleted})
      })
      .then(() => window.location.reload());
  }

  function deleteChecklist(itemId, event) {
      event.stopPropagation();
      event.preventDefault();
      fetch('{% url "portal_work_orders" %}', {
          method: 'DELETE',
          headers: {
              'Content-Type': 'application/json',
              'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
          },
          body: JSON.stringify({action: 'delete_checklist', item_id: itemId})
      })
      .then(() => window.location.reload());
  }

  function addChecklistItem() {
      const name = document.getElementById('new-checklist-item').value;
      if(!name || !currentWo) return;
      
      fetch('{% url "portal_work_orders" %}', {
          method: 'POST',
          headers: {
              'Content-Type': 'application/json',
              'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
          },
          body: JSON.stringify({action: 'add_checklist', work_order_id: currentWo.id, item_name: name})
      })
      .then(res => res.json())
      .then(data => {
          if(data.success) {
              window.location.reload(); 
          }
      });
  }
