// SafeDose Feedback - submits user feedback to /api/feedback.
// Feedback is stored on the server and never made public.

document.addEventListener('DOMContentLoaded', () => {
  const form = document.getElementById('feedbackForm');
  if (!form) return;

  const msgEl = document.getElementById('feedbackMsg');
  const submitBtn = document.getElementById('feedbackSubmitBtn');

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const message = document.getElementById('fbMessage').value.trim();
    if (!message) {
      showMsg('Please enter a message.', 'error');
      return;
    }

    submitBtn.disabled = true;
    submitBtn.textContent = 'Sending...';
    try {
      const resp = await fetch('/api/feedback', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: message,
          category: document.getElementById('fbCategory').value,
          name: document.getElementById('fbName').value.trim(),
          email: document.getElementById('fbEmail').value.trim()
        })
      });
      const data = await resp.json();
      if (resp.ok) {
        showMsg('Thank you! Your feedback was submitted.', 'success');
        form.reset();
      } else {
        showMsg(data.error || 'Could not submit feedback. Please try again.', 'error');
      }
    } catch (err) {
      showMsg('Network error. Please try again.', 'error');
    } finally {
      submitBtn.disabled = false;
      submitBtn.textContent = 'Send Feedback';
    }
  });

  function showMsg(text, type) {
    msgEl.textContent = text;
    msgEl.className = 'feedback-msg ' + (type === 'success' ? 'feedback-success' : 'feedback-error');
  }
});
