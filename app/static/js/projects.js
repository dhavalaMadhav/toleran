/**
 * Projects Page Interactions
 * Swiss Minimalism & Apple-Level Polish
 */

document.addEventListener('DOMContentLoaded', () => {
  const openBtn = document.getElementById('openNewProjectBtn');
  const openBtnEmpty = document.getElementById('openNewProjectBtnEmpty');
  const form = document.getElementById('createProjectForm');

  if (openBtn) openBtn.addEventListener('click', () => openModal('createProjectModal'));
  if (openBtnEmpty) openBtnEmpty.addEventListener('click', () => openModal('createProjectModal'));

  if (form) {
    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      const payload = {
        name: document.getElementById('projName').value.trim(),
        part_number: document.getElementById('projPartNo').value.trim() || null,
        revision: document.getElementById('projRevision').value.trim() || 'Rev A',
        description: document.getElementById('projDesc').value.trim() || null
      };

      try {
        const res = await fetch('/api/v1/projects', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (res.ok) {
          showToast('Project created successfully', 'success');
          closeModal('createProjectModal');
          setTimeout(() => location.reload(), 350);
        } else {
          showToast(data.message || 'Error creating project', 'error');
        }
      } catch (err) {
        showToast('Network error: ' + err.message, 'error');
      }
    });
  }
});

async function archiveProject(projectId) {
  if (!confirm('Are you sure you want to archive this engineering project?')) return;
  try {
    const res = await fetch(`/api/v1/projects/${projectId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status: 'archived' })
    });
    if (res.ok) {
      showToast('Project archived', 'info');
      setTimeout(() => location.reload(), 350);
    }
  } catch (e) {
    showToast('Failed to archive: ' + e.message, 'error');
  }
}
