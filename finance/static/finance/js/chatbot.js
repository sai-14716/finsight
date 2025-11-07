// Minimal chatbot client for FinSIGHT
(function(){
    function getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                // Does this cookie string begin with the name we want?
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }

    // Start a new session and render the initial message into the specified message container
    async function startAIChat(targetContainerId = 'aiOverlayMessages') {
        const csrftoken = getCookie('csrftoken');
        const res = await fetch('/api/ai/chat/start/', {
            method: 'POST',
            headers: {'Content-Type': 'application/json', 'X-CSRFToken': csrftoken},
            credentials: 'same-origin'
        });
        const data = await res.json();
        if (data.session_id) {
            window.aiChatSession = data.session_id;
            appendMessageTo(targetContainerId, 'assistant', data.initial || '');
        } else if (data.error) {
            appendMessageTo(targetContainerId, 'assistant', 'Error: ' + data.error);
        }
    }

    async function sendAIMessage(text, targetContainerId = 'aiOverlayMessages') {
        if (!window.aiChatSession) {
            await startAIChat(targetContainerId);
        }
        appendMessageTo(targetContainerId, 'user', text);
        const csrftoken = getCookie('csrftoken');
        const res = await fetch(`/api/ai/chat/${window.aiChatSession}/message/`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json', 'X-CSRFToken': csrftoken},
            credentials: 'same-origin',
            body: JSON.stringify({message: text})
        });
        const data = await res.json();
        if (data.response) appendMessageTo(targetContainerId, 'assistant', data.response);
        else if (data.error) appendMessageTo(targetContainerId, 'assistant', 'Error: ' + data.error);
    }

    function appendMessageTo(containerId, role, text) {
        const container = document.getElementById(containerId);
        if (!container) return;
        // remove empty placeholder if present
        const empty = container.querySelector('.ai-chat-empty');
        if (empty) empty.remove();
        const el = document.createElement('div');
        el.className = role === 'user' ? 'chat-user message' : 'chat-assistant message';
        const inner = document.createElement('div');
        inner.className = 'message-bubble';
        inner.innerHTML = text.replace(/\n/g, '<br>');
        el.appendChild(inner);
        container.appendChild(el);
        el.scrollIntoView({ behavior: 'smooth', block: 'end' });
    }

    document.addEventListener('DOMContentLoaded', function(){
        const sendBtn = document.getElementById('aiSendBtn');
        const input = document.getElementById('aiChatInput');
        const newBtn = document.getElementById('aiNewSessionBtn');

        if (newBtn) newBtn.addEventListener('click', function(){
            // open overlay and start session there
            openOverlay();
            window.aiChatSession = null;
            const msgs = document.getElementById('aiOverlayMessages');
            if (msgs) msgs.innerHTML = '';
            startAIChat('aiOverlayMessages');
        });

        const closeBtn = document.getElementById('aiCloseBtn');
        if (closeBtn) closeBtn.addEventListener('click', function(){
            const widget = document.getElementById('aiChatWidget');
            if (widget) widget.style.display = 'none';
        });

        // overlay controls
        const overlay = document.getElementById('aiChatOverlay');
        const overlayCloseLeft = document.getElementById('aiOverlayCloseLeft');
        const overlayNew = document.getElementById('aiOverlayNewSession');
        const overlaySend = document.getElementById('aiOverlaySend');
        const overlayInput = document.getElementById('aiOverlayInput');
        const overlayForm = document.getElementById('aiOverlayForm');

        function openOverlay(){
            if (overlay){ overlay.setAttribute('aria-hidden','false'); overlay.style.display='flex'; }
            // focus input
            setTimeout(()=>{ if (overlayInput) overlayInput.focus(); }, 200);
        }
        function closeOverlay(){
            if (overlay){ overlay.setAttribute('aria-hidden','true'); overlay.style.display='none'; }
            // clear session when closed
            window.aiChatSession = null;
        }

        // attach overlay controls
        if (overlayCloseLeft) overlayCloseLeft.addEventListener('click', closeOverlay);
        if (overlayNew) overlayNew.addEventListener('click', function(){
            // new session from overlay
            window.aiChatSession = null;
            const msgs = document.getElementById('aiOverlayMessages'); if (msgs) msgs.innerHTML = '';
            startAIChat('aiOverlayMessages');
        });
        if (overlaySend && overlayInput) overlaySend.addEventListener('click', async function(){
            const t = overlayInput.value.trim(); if (!t) return; overlayInput.value=''; await sendAIMessage(t, 'aiOverlayMessages');
        });
        if (overlayForm && overlayInput) overlayForm.addEventListener('submit', async function(e){ e.preventDefault(); const t = overlayInput.value.trim(); if (!t) return; overlayInput.value=''; await sendAIMessage(t, 'aiOverlayMessages'); });

        if (sendBtn && input) sendBtn.addEventListener('click', async function(){
            const t = input.value.trim();
            if (!t) return;
            input.value = '';
            await sendAIMessage(t);
        });

        if (input) input.addEventListener('keydown', function(e){
            if (e.key === 'Enter') {
                e.preventDefault();
                sendBtn.click();
            }
        });

        // Sessions are started only when the user clicks 'New Session'
    });

    // expose functions for debugging
    window.startAIChat = startAIChat;
    window.sendAIMessage = sendAIMessage;
})();
